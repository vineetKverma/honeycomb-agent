import time
import sys
from google import genai
from google.genai import types
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

import config
from gemini_utils import call_with_retry

_client = genai.Client(api_key=config.GEMINI_API_KEY)
_console = Console()

SYSTEM_PROMPT = """You are a knowledge graph builder. Extract atomic learning concepts from the transcript.

Rules:
- Return a MINIMUM of 8 concepts, more if the content warrants it.
- Each concept must be ATOMIC and SPECIFIC.
  Good: "backpropagation", "softmax activation", "cross-entropy loss"
  Bad: "machine learning", "neural networks in general", "the math behind AI"
- Each definition must be 1-2 sentences and fully self-contained — a learner must understand the concept without any surrounding context.
- Prerequisites must be concept-like phrases (short noun phrases), NOT full sentences. They will be used to link nodes in a knowledge graph.
- DO NOT include meta-concepts such as "the speaker explains X" or "this video covers Y".
"""


class Concept(BaseModel):
    name: str
    definition: str
    prerequisites: list[str]


class ExtractionResult(BaseModel):
    concepts: list[Concept]


def _call_gemini(text: str) -> list[Concept]:
    response = call_with_retry(
        _client.models.generate_content,
        model="gemini-2.5-flash",
        contents=text,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=ExtractionResult,
        ),
    )
    return ExtractionResult.model_validate_json(response.text).concepts


def _chunk(text: str, max_chars: int = 25000) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks, paragraphs, current = [], text.split("\n\n"), ""
    for para in paragraphs:
        if len(current) + len(para) + 2 > max_chars and current:
            chunks.append(current.strip())
            current = para
        else:
            current = (current + "\n\n" + para) if current else para
    if current.strip():
        chunks.append(current.strip())
    # fall back to hard splits if paragraph splitting produced no useful boundaries
    if len(chunks) == 1 and len(chunks[0]) > max_chars:
        chunks = [text[i : i + max_chars] for i in range(0, len(text), max_chars)]
    return chunks


def extract_concepts(text: str, source_meta: dict) -> list[dict]:
    chunks = _chunk(text) if len(text) > 30000 else [text]
    seen: dict[str, Concept] = {}
    for chunk in chunks:
        for concept in _call_gemini(chunk):
            key = concept.name.strip().lower()
            if key not in seen:
                seen[key] = concept
    return [c.model_dump() for c in seen.values()]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        _console.print("Usage: python extract.py <youtube_url>")
        sys.exit(1)

    from ingest import fetch_youtube_transcript

    url = sys.argv[1]
    _console.print(f"[bold]Fetching transcript…[/bold] {url}")
    transcript, meta = fetch_youtube_transcript(url)
    _console.print(f"Transcript: {len(transcript):,} chars | {meta['segment_count']} segments | {meta['duration_seconds']:.0f}s")

    _console.print("[bold]Extracting concepts via Gemini…[/bold]")
    t0 = time.perf_counter()
    concepts = extract_concepts(transcript, meta)
    elapsed = time.perf_counter() - t0

    table = Table(title=f"Extracted Concepts ({len(concepts)} total, {elapsed:.1f}s)", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Concept", style="bold cyan", min_width=24)
    table.add_column("Prerequisites", style="yellow", min_width=20)
    table.add_column("Definition", min_width=40)

    for i, c in enumerate(concepts, 1):
        prereqs = ", ".join(c["prerequisites"]) or "—"
        definition = c["definition"][:60] + ("…" if len(c["definition"]) > 60 else "")
        table.add_row(str(i), c["name"], prereqs, definition)

    _console.print(table)
    _console.print(f"[green]Done.[/green] {len(concepts)} concepts in {elapsed:.1f}s")
