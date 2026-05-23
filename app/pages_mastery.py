"""Mastery page: read-only stats, recent attempts, and a prereq chip list.

No Gemini calls. All DB reads are cached for 60s to avoid hammering Atlas.
"""
from collections import Counter

import streamlit as st

import db
import mastery

# (background, foreground) per mastery level for the metric cards.
_LEVEL_STYLE = {
    "weak": ("#d62728", "#ffffff"),
    "developing": ("#ff7f0e", "#1a1a1a"),
    "solid": ("#2ca02c", "#ffffff"),
    "untested": ("#6c757d", "#ffffff"),
}


@st.cache_data(ttl=60)
def _level_counts() -> dict:
    counts = {"weak": 0, "developing": 0, "solid": 0, "untested": 0}
    for c in db.get_collection().find({}, {"_id": 1}):
        level = mastery.compute_mastery(c["_id"])["mastery_level"]
        counts[level] = counts.get(level, 0) + 1
    return counts


@st.cache_data(ttl=60)
def _due_count() -> int:
    return len(mastery.get_review_candidates(limit=1000))


@st.cache_data(ttl=60)
def _recent_events(n: int = 10) -> list[dict]:
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


def _level_card(col, label: str, value: int, level: str) -> None:
    bg, fg = _LEVEL_STYLE[level]
    col.markdown(
        f"<div class='hc-card' style='background:{bg};color:{fg};text-align:center'>"
        f"<div style='font-size:2rem;font-weight:800'>{value}</div>"
        f"<div style='font-size:0.8rem;text-transform:uppercase;letter-spacing:0.06em'>{label}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_mastery_page() -> None:
    st.header("Mastery overview")

    due = _due_count()
    hero_l, hero_r = st.columns([3, 1])
    with hero_l:
        st.markdown(
            f"<div class='hc-card' style='background:#1f2a37;color:#e8eaed'>"
            f"<div style='font-size:1.4rem;font-weight:700'>{due} concept(s) due for review today</div>"
            f"<div class='hc-tagline'>Spaced repetition keeps weak and stale concepts fresh.</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with hero_r:
        st.write("")
        if st.button("Start review", type="primary", use_container_width=True):
            st.session_state["_goto"] = "Daily Review"
            st.rerun()

    st.write("")
    counts = _level_counts()
    cols = st.columns(4)
    _level_card(cols[0], "Weak", counts["weak"], "weak")
    _level_card(cols[1], "Developing", counts["developing"], "developing")
    _level_card(cols[2], "Solid", counts["solid"], "solid")
    _level_card(cols[3], "Untested", counts["untested"], "untested")

    st.subheader("Recent activity")
    rows = _recent_events(10)
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("No quiz attempts recorded yet.")

    st.subheader("Top prerequisites")
    top = _top_prereqs(10)
    if top:
        st.markdown(
            "".join(f"<span class='hc-chip'>{name} ({cnt})</span>" for name, cnt in top),
            unsafe_allow_html=True,
        )
    else:
        st.info("No prerequisites recorded yet.")
