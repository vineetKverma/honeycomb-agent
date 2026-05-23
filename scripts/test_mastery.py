"""Pure-Python integration test for mastery tracking (NO Gemini calls, zero quota).

Seeds backdated quiz events on existing concepts, then verifies compute_mastery
classification and get_review_candidates prioritization. ASCII-only output.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow running as `python scripts/test_mastery.py` from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
import mastery

# Backdate seeded events far enough that every level is "due for review"
# (weak/developing need >=1 day, solid needs >=7), so the due logic is exercised.
_BACKDATE = datetime.now(timezone.utc) - timedelta(days=8)


def _find(name: str):
    return db.get_collection().find_one({"name_lower": name.lower().strip()})


def _seed(name: str, score: int):
    doc = _find(name)
    if doc is None:
        print(f"[skip] concept '{name}' not found in graph; cannot seed.")
        return None
    mastery.record_event(
        doc["_id"], doc["name"], score, f"(test answer for {name})", [], timestamp=_BACKDATE
    )
    info = mastery.compute_mastery(doc["_id"])
    print(f"[seed] {doc['name']:<22} score={score} -> level={info['mastery_level']} due={info['due_for_review']}")
    return doc["name"]


def main() -> int:
    db.ensure_indexes()

    print("=== Seeding mastery events (backdated 8 days) ===")
    weak1 = _seed("Neural Network", 2)
    solid = _seed("Backpropagation", 4) or _seed("Sigmoid Function", 4)
    weak2 = _seed("Derivative", 1)

    print("\n=== get_review_candidates(limit=5) ===")
    candidates = mastery.get_review_candidates(limit=5)
    for i, c in enumerate(candidates, 1):
        m = c["mastery_info"]
        print(
            f"{i}. {c['name']:<22} level={m['mastery_level']:<11} "
            f"avg={m['rolling_avg']} days={m['days_since_last_review']} due={m['due_for_review']}"
        )

    print("\n=== Checks ===")
    ok = True

    # 1. Every returned candidate must be due_for_review.
    if candidates and all(c["mastery_info"]["due_for_review"] for c in candidates):
        print("[pass] all candidates are due_for_review")
    elif not candidates:
        print("[warn] no candidates returned (is the graph empty?)")
    else:
        print("[FAIL] a candidate is not due_for_review")
        ok = False

    # 2. Candidates must be priority-sorted: no 'solid' before any 'weak'.
    order = [c["mastery_info"]["mastery_level"] for c in candidates]
    rank = {"weak": 0, "developing": 1, "untested": 2, "solid": 3}
    if order == sorted(order, key=lambda lvl: rank.get(lvl, 99)):
        print("[pass] candidates are priority-sorted (weak before solid)")
    else:
        print(f"[FAIL] candidate order not by priority: {order}")
        ok = False

    # 3. Seeded weak concepts classify as weak; the solid one classifies as solid.
    for nm in (weak1, weak2):
        if nm:
            lvl = mastery.compute_mastery(_find(nm)["_id"])["mastery_level"]
            print(f"[{'pass' if lvl == 'weak' else 'FAIL'}] '{nm}' level={lvl} (expected weak)")
            ok = ok and lvl == "weak"
    if solid:
        lvl = mastery.compute_mastery(_find(solid)["_id"])["mastery_level"]
        print(f"[{'pass' if lvl == 'solid' else 'FAIL'}] '{solid}' level={lvl} (expected solid)")
        ok = ok and lvl == "solid"

    print("\n[done] all checks passed" if ok else "\n[done] SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
