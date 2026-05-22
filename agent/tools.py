"""Honeycomb agent tools.

Each function below is a plain Python callable with a Google-style docstring.
ADK auto-wraps plain functions passed in an Agent's `tools=[...]` list into
FunctionTool instances, and reads the docstring (Args/Returns) plus the type
hints to generate the tool schema sent to the model.

All return values are plain JSON-serializable dicts/lists -- no ObjectId or
datetime objects leak out, since ADK serializes tool results for the model.
"""
import db
import embed
import pipeline
import quiz

_MAX_DEFINITION_CHARS = 200


def _find_concept(concept_name: str) -> dict | None:
    """Case-insensitive lookup of one concept by name, embedding stripped."""
    name_lower = concept_name.lower().strip()
    return db.get_collection().find_one({"name_lower": name_lower}, {"embedding": 0})


def ingest_learning_source(url: str) -> dict:
    """Ingest a learning source: fetch its transcript, extract atomic concepts, and link
    them into the user's knowledge graph (creating new concept nodes or merging into
    existing ones).

    Args:
        url: The URL of the learning source to ingest (currently a YouTube video URL).

    Returns:
        A dict with:
            created: list of concept names that were newly added to the graph.
            merged: list of concept names that merged into existing concepts.
            elapsed_seconds: total wall-clock time for the pipeline, in seconds.
            url: the source URL that was ingested.
    """
    summary = pipeline.run_pipeline(url, verbose=False)
    return {
        "created": summary["created_names"],
        "merged": summary["merged_names"],
        "elapsed_seconds": summary["elapsed_seconds"],
        "url": summary["url"],
    }


def quiz_concept(concept_name: str) -> dict:
    """Generate one understanding-focused quiz question for a concept in the user's graph.

    Args:
        concept_name: The name of the concept to quiz on (matched case-insensitively).

    Returns:
        A dict with:
            concept: the canonical concept name as stored in the graph.
            question: the quiz question text.
            expected_outline: list of points a strong answer should cover. Pass this,
                unchanged, into grade_my_answer along with the question.

    Raises:
        ValueError: if no concept with that name exists in the graph.
    """
    doc = _find_concept(concept_name)
    if doc is None:
        raise ValueError(
            f"No concept named '{concept_name}' is in your graph yet. "
            "Ingest a source about it first, or check the spelling."
        )
    generated = quiz.generate_quiz(doc)
    return {
        "concept": doc["name"],
        "question": generated["question"],
        "expected_outline": generated["expected_answer_outline"],
    }


def grade_my_answer(
    concept_name: str, question: str, expected_outline: list[str], user_answer: str
) -> dict:
    """Grade the user's free-text answer to a quiz question, fairly and encouragingly.

    Args:
        concept_name: The concept the question was about (for context).
        question: The exact quiz question that was asked.
        expected_outline: The expected_outline returned by quiz_concept, unchanged.
        user_answer: The user's free-text answer to grade.

    Returns:
        A dict with:
            score: integer 0-5 (5 = covers all outline points with accurate reasoning).
            feedback: one or two encouraging sentences.
            missed_points: list of outline points the user did not address.
    """
    result = quiz.grade_answer(question, expected_outline, user_answer)
    return {
        "score": result["score"],
        "feedback": result["feedback"],
        "missed_points": result["missed_points"],
    }


def list_my_concepts(domain_hint: str = "") -> list[dict]:
    """List concepts already in the user's knowledge graph, optionally filtered by topic.

    Args:
        domain_hint: Optional topic to search for (e.g. "neural networks"). If provided,
            returns concepts semantically closest to it via vector search. If empty,
            returns a broad sample of concepts in the graph.

    Returns:
        A list of dicts, each with:
            name: the concept name.
            definition: a brief definition (truncated for readability).
    """
    if domain_hint.strip():
        embedding = embed.embed_text(domain_hint.strip())
        docs = db.vector_search(embedding, limit=10)
    else:
        docs = list(
            db.get_collection().find({}, {"name": 1, "definition": 1, "_id": 0}).limit(50)
        )

    out = []
    for doc in docs:
        definition = doc.get("definition", "")
        if len(definition) > _MAX_DEFINITION_CHARS:
            definition = definition[: _MAX_DEFINITION_CHARS - 3] + "..."
        out.append({"name": doc.get("name", ""), "definition": definition})
    return out


def get_concept_details(concept_name: str) -> dict:
    """Fetch the full record for one concept in the user's graph.

    Args:
        concept_name: The name of the concept to look up (matched case-insensitively).

    Returns:
        A dict with:
            name: the concept name.
            definition: the full definition.
            prerequisites: list of prerequisite concept names.
            sources: list of source records (url, video_id, ingested_at) the concept
                was learned from.

    Raises:
        ValueError: if no concept with that name exists in the graph.
    """
    doc = _find_concept(concept_name)
    if doc is None:
        raise ValueError(
            f"No concept named '{concept_name}' is in your graph yet."
        )
    return {
        "name": doc.get("name", ""),
        "definition": doc.get("definition", ""),
        "prerequisites": doc.get("prerequisites", []),
        "sources": doc.get("sources", []),
    }
