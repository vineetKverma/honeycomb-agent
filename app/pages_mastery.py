"""Mastery page: read-only stats, recent attempts, and a prereq tag cloud.

No Gemini calls. All DB reads are cached for 60s to avoid hammering Atlas.
"""
from collections import Counter

import streamlit as st

import db
import mastery


@st.cache_data(ttl=60)
def _level_counts() -> dict:
    counts = {"weak": 0, "developing": 0, "solid": 0, "untested": 0}
    for c in db.get_collection().find({}, {"_id": 1}):
        level = mastery.compute_mastery(c["_id"])["mastery_level"]
        counts[level] = counts.get(level, 0) + 1
    return counts


@st.cache_data(ttl=60)
def _recent_events(n: int = 20) -> list[dict]:
    docs = (
        db.get_mastery_collection()
        .find({}, {"_id": 0, "concept_name": 1, "score": 1, "timestamp": 1})
        .sort("timestamp", -1)
        .limit(n)
    )
    rows = []
    for d in docs:
        ts = d.get("timestamp")
        rows.append(
            {
                "Concept": d.get("concept_name", ""),
                "Score": d.get("score"),
                "When (UTC)": ts.strftime("%Y-%m-%d %H:%M") if ts else "",
            }
        )
    return rows


@st.cache_data(ttl=60)
def _top_prereqs(n: int = 10) -> list[tuple[str, int]]:
    counter: Counter = Counter()
    for c in db.get_collection().find({}, {"_id": 0, "prerequisites": 1}):
        for pre in c.get("prerequisites", []):
            if pre.strip():
                counter[pre.strip()] += 1
    return counter.most_common(n)


def render_mastery_page() -> None:
    st.header("Mastery overview")

    counts = _level_counts()
    total = sum(counts.values())
    cols = st.columns(5)
    cols[0].metric("Total concepts", total)
    cols[1].metric("Weak", counts["weak"])
    cols[2].metric("Developing", counts["developing"])
    cols[3].metric("Solid", counts["solid"])
    cols[4].metric("Untested", counts["untested"])

    st.subheader("Recent quiz attempts")
    rows = _recent_events(20)
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("No quiz attempts recorded yet.")

    st.subheader("Top prerequisites")
    top = _top_prereqs(10)
    if top:
        st.markdown("  ".join(f"`{name}` x{cnt}" for name, cnt in top))
    else:
        st.info("No prerequisites recorded yet.")
