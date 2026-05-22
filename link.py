import difflib
import re
import time
from datetime import datetime, timezone

from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from rich.console import Console

import db
import embed

_console = Console()


def _normalize_concept_name(name: str) -> str:
    """Lowercase, strip parens content, remove common qualifier suffixes,
    sort words to handle reordering. Falls back to the parens-stripped name
    when aggressive stripping would erase everything meaningful."""
    raw_lower = name.lower().strip()
    # Always strip parens content first: "Neuron (Artificial)" -> "neuron"
    no_parens = re.sub(r"\s*\([^)]*\)\s*", " ", raw_lower)
    no_parens = " ".join(no_parens.split())
    # Try aggressive normalization (strip common boilerplate suffixes)
    n = re.sub(r"\b(neural network[s]?|of a neuron|in a neural network|of neural networks?)\b", "", no_parens)
    n = " ".join(n.split())
    # Fallback if aggressive stripping erased everything meaningful
    # (e.g. the name itself IS the boilerplate, like "Neural Network")
    if len(n) < 3:
        n = no_parens
    # Sort words alphabetically so "neural network learning" == "learning neural network"
    return " ".join(sorted(n.split())) if n else ""


def _names_likely_match(a: str, b: str) -> bool:
    na = _normalize_concept_name(a)
    nb = _normalize_concept_name(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    return difflib.SequenceMatcher(None, na, nb).ratio() >= 0.6


def link_or_create(concept: dict, source_meta: dict, threshold: float = 0.95) -> tuple[str, ObjectId]:
    embedding = embed.embed_concept(concept)
    candidates = db.vector_search(embedding, limit=3)

    print(
        f"[link] '{concept['name']}' -> top candidate: '{candidates[0]['name']}' score={candidates[0]['_score']:.4f}"
        if candidates
        else f"[link] '{concept['name']}' -> NO candidates returned"
    )

    top = candidates[0] if candidates else None
    decision = "created"
    if top is not None:
        raw_a, raw_b = concept["name"], top.get("name", "")
        norm_a, norm_b = _normalize_concept_name(raw_a), _normalize_concept_name(raw_b)
        name_match = _names_likely_match(raw_a, raw_b)
        print(f"[link] '{raw_a}' -> '{raw_b}' | norm: '{norm_a}' vs '{norm_b}' | match={name_match}")
        if top["_score"] >= threshold:
            decision = "merged" if name_match else "name-sim-blocked"

    print(f"[link]   decision: {decision} (threshold={threshold})")

    if decision == "merged":
        db.get_collection().update_one(
            {"_id": top["_id"]},
            {
                "$addToSet": {"sources": {"$each": [source_meta]}},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
        )
        return ("merged", top["_id"])

    doc = {
        "name": concept["name"],
        "name_lower": concept["name"].lower().strip(),
        "definition": concept["definition"],
        "prerequisites": concept.get("prerequisites", []),
        "embedding": embedding,
        "sources": [source_meta],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    try:
        result = db.get_collection().insert_one(doc)
        return ("created", result.inserted_id)
    except DuplicateKeyError:
        existing = db.get_collection().find_one({"name_lower": doc["name_lower"]})
        db.get_collection().update_one(
            {"_id": existing["_id"]},
            {
                "$addToSet": {"sources": {"$each": [source_meta]}},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
        )
        return ("merged", existing["_id"])


if __name__ == "__main__":
    db.ensure_indexes()

    backprop = {
        "name": "Backpropagation",
        "definition": "An algorithm for computing gradients in a neural network by propagating errors backward through layers.",
        "prerequisites": ["chain rule", "gradient descent"],
    }
    source1 = {"url": "https://test.example/lecture1", "title": "Test source", "timestamp": datetime.now(timezone.utc).isoformat()}
    source2 = {"url": "https://test.example/lecture2", "title": "Test source 2", "timestamp": datetime.now(timezone.utc).isoformat()}
    stir_fry = {
        "name": "Stir-frying",
        "definition": "A Chinese cooking technique using high heat and a small amount of oil.",
        "prerequisites": [],
    }
    source3 = {"url": "https://test.example/cooking101", "title": "Cooking source", "timestamp": datetime.now(timezone.utc).isoformat()}

    action, oid = link_or_create(backprop, source1)
    _console.print(f"[bold]Run 1[/bold] → [cyan]{action}[/cyan]  _id={oid}")

    _console.print("[dim]Waiting 3s for Atlas index propagation…[/dim]")
    time.sleep(3)

    action, oid = link_or_create(backprop, source2)
    _console.print(f"[bold]Run 2[/bold] (same concept, new source) → [cyan]{action}[/cyan]  _id={oid}")

    action, oid = link_or_create(stir_fry, source3)
    _console.print(f"[bold]Run 3[/bold] (unrelated concept)        → [cyan]{action}[/cyan]  _id={oid}")
