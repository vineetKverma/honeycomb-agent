"""Mastery tracking and spaced-repetition review (pure Python, no Gemini calls).

Mastery is computed from an append-only event log (mastery_events), not stored
as a mutable aggregate: every quiz attempt is one immutable event, and the
mastery level is derived from the rolling window of recent scores.
"""
from datetime import datetime, timezone

from bson import ObjectId

import db

_ROLLING_WINDOW = 5
_USER_ANSWER_MAX = 200
# mastery_level review priority (lower = reviewed first)
_PRIORITY = {"weak": 0, "developing": 1, "untested": 2, "solid": 3}


def record_event(
    concept_id: ObjectId,
    concept_name: str,
    score: int,
    user_answer: str,
    missed_points: list[str],
    timestamp: datetime | None = None,
) -> ObjectId:
    """Append one quiz outcome to mastery_events; returns the new event _id.

    `timestamp` defaults to now (UTC) and is exposed only so tests can backdate
    events -- production callers should omit it.
    """
    doc = {
        "concept_id": concept_id,
        "concept_name": concept_name,
        "score": int(score),
        "user_answer_excerpt": (user_answer or "")[:_USER_ANSWER_MAX],
        "missed_points": missed_points or [],
        "timestamp": timestamp or datetime.now(timezone.utc),
    }
    return db.get_mastery_collection().insert_one(doc).inserted_id


def _as_utc(dt: datetime) -> datetime:
    # pymongo returns naive (UTC) datetimes unless the client is tz_aware.
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def compute_mastery(concept_id: ObjectId) -> dict:
    """Derive mastery state for one concept from its event log."""
    events = list(
        db.get_mastery_collection().find({"concept_id": concept_id}).sort("timestamp", -1)
    )
    if not events:
        return {
            "concept_id": str(concept_id),
            "attempts": 0,
            "latest_score": None,
            "rolling_avg": 0.0,
            "days_since_last_review": None,
            "mastery_level": "untested",
            "due_for_review": True,
        }

    recent = events[:_ROLLING_WINDOW]
    rolling_avg = sum(e["score"] for e in recent) / len(recent)
    days_since = (datetime.now(timezone.utc) - _as_utc(events[0]["timestamp"])).days

    if rolling_avg < 2.5:
        level = "weak"
    elif rolling_avg < 4.0:
        level = "developing"
    else:
        level = "solid"

    due = (level in {"weak", "developing"} and days_since >= 1) or (
        level == "solid" and days_since >= 7
    )

    return {
        "concept_id": str(concept_id),
        "attempts": len(events),
        "latest_score": events[0]["score"],
        "rolling_avg": round(rolling_avg, 2),
        "days_since_last_review": days_since,
        "mastery_level": level,
        "due_for_review": due,
    }


def _overdue_key(info: dict) -> float:
    days = info["days_since_last_review"]
    return float("inf") if days is None else days


def get_review_candidates(limit: int = 5) -> list[dict]:
    """Return up to `limit` concepts due for review, highest priority first.

    Priority tiers: weak -> developing -> untested -> solid; within a tier the
    most overdue (largest days_since_last_review) comes first.
    """
    candidates = []
    for concept in db.get_collection().find({}, {"name": 1, "definition": 1}):
        info = compute_mastery(concept["_id"])
        if not info["due_for_review"]:
            continue
        candidates.append(
            {
                "name": concept.get("name", ""),
                "definition": concept.get("definition", ""),
                "mastery_info": info,
            }
        )

    candidates.sort(
        key=lambda c: (
            _PRIORITY.get(c["mastery_info"]["mastery_level"], 99),
            -_overdue_key(c["mastery_info"]),
        )
    )
    return candidates[:limit]
