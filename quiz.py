import sys
from google import genai
from google.genai import types
from pydantic import BaseModel
from rich.console import Console
from rich.prompt import Prompt

import config
import db
from gemini_utils import call_with_retry

_client = genai.Client(api_key=config.GEMINI_API_KEY)
_console = Console()


class QuizQuestion(BaseModel):
    question: str
    expected_answer_outline: list[str]


class GradeResult(BaseModel):
    score: int
    feedback: str
    missed_points: list[str]


_QUIZ_SYSTEM = """You are a technical educator generating quiz questions for a knowledge graph.

Rules:
- Question must test UNDERSTANDING, not recall. Avoid "What is X?" style.
  Prefer: "Explain why X works", "When would you use X instead of Y", "What happens if X is missing".
- The question must be entirely self-contained — never reference "the video", "the lecture", or any external context.
- expected_answer_outline: 3-5 specific, concrete points a strong answer would cover.
"""

_GRADE_SYSTEM = """You are a fair and encouraging technical tutor grading a student's answer.

Rules:
- Score 0-5: 5 = covers all outline points with accurate reasoning; 0 = entirely wrong or empty.
- Be FAIR, not harsh — reward partial and approximate understanding.
- Feedback must be 1-2 sentences: mention what the student got right BEFORE what they missed.
- missed_points should be drawn verbatim or as a close paraphrase from the expected outline.
"""


def generate_quiz(concept: dict) -> dict:
    prompt = f"Concept: {concept['name']}\nDefinition: {concept['definition']}"
    response = call_with_retry(
        _client.models.generate_content,
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_QUIZ_SYSTEM,
            response_mime_type="application/json",
            response_schema=QuizQuestion,
        ),
    )
    return QuizQuestion.model_validate_json(response.text).model_dump()


def grade_answer(question: str, expected_outline: list[str], user_answer: str) -> dict:
    prompt = (
        f"Question: {question}\n\n"
        f"Expected outline:\n" + "\n".join(f"- {p}" for p in expected_outline) +
        f"\n\nStudent answer: {user_answer}"
    )
    response = call_with_retry(
        _client.models.generate_content,
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_GRADE_SYSTEM,
            response_mime_type="application/json",
            response_schema=GradeResult,
        ),
    )
    return GradeResult.model_validate_json(response.text).model_dump()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        _console.print("Usage: python quiz.py <concept name>")
        sys.exit(1)

    name_lower = " ".join(sys.argv[1:]).lower().strip()
    concept = db.get_collection().find_one({"name_lower": name_lower}, {"embedding": 0})
    if not concept:
        _console.print(f"[red]Concept '{name_lower}' not found in database.[/red]")
        sys.exit(1)

    _console.print(f"\n[bold cyan]Concept:[/bold cyan] {concept['name']}")
    _console.print(f"[dim]{concept['definition']}[/dim]\n")

    _console.print("[bold]Generating quiz question…[/bold]")
    quiz = generate_quiz(concept)

    _console.print(f"\n[bold yellow]Question:[/bold yellow] {quiz['question']}\n")
    _console.print("[dim]Expected outline (hidden during quiz):[/dim]")
    for point in quiz["expected_answer_outline"]:
        _console.print(f"  [dim]• {point}[/dim]")

    answer = Prompt.ask("\n[bold green]Your answer[/bold green]")

    _console.print("\n[bold]Grading…[/bold]")
    result = grade_answer(quiz["question"], quiz["expected_answer_outline"], answer)

    score = result["score"]
    stars = "★" * score + "☆" * (5 - score)
    color = "green" if score >= 4 else "yellow" if score >= 2 else "red"
    _console.print(f"\n[bold {color}]Score: {score}/5  {stars}[/bold {color}]")
    _console.print(f"[bold]Feedback:[/bold] {result['feedback']}")
    if result["missed_points"]:
        _console.print("\n[bold]Missed points:[/bold]")
        for p in result["missed_points"]:
            _console.print(f"  [red]• {p}[/red]")
    else:
        _console.print("\n[green]All points covered![/green]")
