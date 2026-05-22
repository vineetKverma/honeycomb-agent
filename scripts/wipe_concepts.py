import sys
from pathlib import Path

# Allow running as `python scripts/wipe_concepts.py` from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import get_collection


def main() -> int:
    # delete_many({}) clears all documents but PRESERVES the collection and its
    # associated Atlas vector search index. Do NOT drop the collection instead.
    result = get_collection().delete_many({})
    deleted = result.deleted_count

    if deleted == 0:
        print("[wipe] WARNING: collection was already empty (0 documents deleted).")
    else:
        print(f"[wipe] Deleted {deleted} document(s). Collection and search index preserved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
