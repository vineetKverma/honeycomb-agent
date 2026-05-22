import sys
from pathlib import Path

# Allow running as `python scripts/check_vector_search.py` from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from embed import embed_concept
from db import vector_search

TEST_CONCEPT = {
    "name": "Neural Network",
    "definition": "A computational model inspired by the human brain.",
}


def main() -> int:
    print(f"[check] Embedding test concept: {TEST_CONCEPT['name']!r}")
    embedding = embed_concept(TEST_CONCEPT)
    print(f"[check] Embedding dimensions: {len(embedding)}")

    results = vector_search(embedding, limit=3)
    print(f"[check] Candidates returned: {len(results)}")
    for i, r in enumerate(results, 1):
        print(f"  {i}. {r.get('name', '?')}  score={r['_score']:.4f}")

    if not results:
        print("[check] FAIL: no candidates returned.")
        print("[check] Verify the Atlas search index exists and is in Active status.")
        return 1

    print("[check] OK: vector search is returning results.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
