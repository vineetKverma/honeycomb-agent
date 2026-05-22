import sys
from pathlib import Path

# Allow running as `python scripts/dump_prereqs.py` from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import get_collection

docs = list(get_collection().find({}, {"name": 1, "prerequisites": 1, "_id": 0}).sort("name", 1))
print(f"Total concepts: {len(docs)}")

with_prereqs = 0
for doc in docs:
    prereqs = doc.get("prerequisites") or []
    if prereqs:
        with_prereqs += 1
    prereq_str = ", ".join(prereqs) if prereqs else "(none)"
    print(f"{doc.get('name', '?'):<50} | {prereq_str}")

print(f"\nTotal: {len(docs)} | with prereqs: {with_prereqs} | no prereqs: {len(docs) - with_prereqs}")
