"""Graph page: the knowledge-graph hero. Nodes colored by MASTERY level.

Left column = the graph; right column = a detail panel for the selected node.
Clicking a node selects it; a selectbox is the reliable fallback selector.
No Gemini calls -- mastery is read via mastery.compute_mastery (cached 30s).
"""
from bson import ObjectId

import streamlit as st
from streamlit_agraph import Config, Edge, Node, agraph

import db
import mastery

_COLOR = {"weak": "#ef4444", "developing": "#f59e0b", "solid": "#10b981", "untested": "#6b7280"}
_SIZE = {"weak": 30, "developing": 25, "solid": 25, "untested": 15}
_LEVELS = ["weak", "developing", "solid", "untested"]


@st.cache_data(ttl=30)
def _load_graph_data() -> list[dict]:
    """All concepts plus their (expensive) mastery level. Cached to spare Atlas."""
    rows = []
    for d in db.get_collection().find({}, {"name": 1, "definition": 1, "prerequisites": 1}):
        info = mastery.compute_mastery(d["_id"])
        rows.append(
            {
                "id": str(d["_id"]),
                "name": d.get("name", ""),
                "definition": d.get("definition", ""),
                "prerequisites": d.get("prerequisites", []),
                "level": info["mastery_level"],
                "days": info["days_since_last_review"],
            }
        )
    return rows


def _legend(total: int) -> None:
    dots = "".join(
        f"<span style='display:inline-block;width:11px;height:11px;border-radius:50%;"
        f"background:{_COLOR[lv]};margin:0 5px 0 14px'></span>"
        f"<span style='color:#cbd5e1;font-size:0.85rem'>{lv.capitalize()}</span>"
        for lv in _LEVELS
    )
    st.markdown(
        f"<div class='hc-card' style='padding:8px 12px'>{dots}"
        f"<span style='float:right;color:#9aa0a6;font-size:0.85rem'>{total} concepts</span></div>",
        unsafe_allow_html=True,
    )


def render_graph_page() -> None:
    concepts = _load_graph_data()
    if not concepts:
        st.info("No concepts yet. Ingest a source first.")
        return

    _legend(len(concepts))

    f1, f2 = st.columns(2)
    levels = f1.multiselect("Show mastery levels", _LEVELS, default=_LEVELS)
    search = f2.text_input("Search concepts", value="").strip().lower()

    by_lower = {c["name"].lower(): c for c in concepts}
    visible = {
        c["name"]
        for c in concepts
        if c["level"] in levels and (not search or search in c["name"].lower())
    }

    edges_raw = []
    for c in concepts:
        for pre in c.get("prerequisites", []):
            src = by_lower.get(pre.lower().strip())
            if src and src["name"] != c["name"]:
                edges_raw.append((src["name"], c["name"]))

    left, right = st.columns([3, 1])
    with left:
        nodes = [
            Node(
                id=c["name"],
                label=c["name"],
                color=_COLOR[c["level"]],
                size=_SIZE[c["level"]],
                font={"color": "#ffffff", "size": 12},
            )
            for c in concepts
            if c["name"] in visible
        ]
        edges = [
            Edge(source=s, target=t, color="#444444", width=1)
            for s, t in edges_raw
            if s in visible and t in visible
        ]
        config = Config(
            height=700,
            width=900,
            directed=True,
            physics=True,
            hierarchical=False,
            nodeHighlightBehavior=True,
            highlightColor="#ffffff",
        )
        clicked = agraph(nodes=nodes, edges=edges, config=config)

    with right:
        _render_panel(concepts, by_lower, clicked)


def _render_panel(concepts: list[dict], by_lower: dict, clicked) -> None:
    names = sorted(c["name"] for c in concepts)
    # A click sets the selectbox value BEFORE the widget is instantiated, so the
    # click and the fallback selectbox share one source of truth.
    if clicked and clicked in names:
        st.session_state["graph_pick"] = clicked
    picked = st.selectbox("Inspect concept", ["-"] + names, key="graph_pick")

    if picked == "-":
        st.subheader("Concept details")
        st.caption("Click a node (or pick one) to inspect it.")
        return

    c = by_lower[picked.lower()]
    color = _COLOR[c["level"]]
    st.markdown(f"### {c['name']}")
    st.markdown(
        f"<span style='background:{color};color:#0a0a0a;padding:2px 10px;border-radius:10px;"
        f"font-weight:700;font-size:0.8rem'>{c['level'].upper()}</span>",
        unsafe_allow_html=True,
    )
    st.write(c["definition"])
    if c.get("prerequisites"):
        st.markdown(
            "".join(f"<span class='hc-chip'>{p}</span>" for p in c["prerequisites"]),
            unsafe_allow_html=True,
        )
    days = c["days"]
    st.caption("Never quizzed" if days is None else f"Last reviewed: {days} day(s) ago")

    b1, b2 = st.columns(2)
    if b1.button("Quiz me on this", key="g_quiz", type="primary"):
        st.session_state["review_focus"] = c["name"]
        st.session_state["_goto"] = "Daily Review"
        st.rerun()
    if b2.button("Show full history", key="g_hist"):
        st.session_state["g_hist_open"] = not st.session_state.get("g_hist_open", False)
    if st.session_state.get("g_hist_open"):
        _render_history(c["id"])


def _render_history(concept_id: str) -> None:
    events = list(
        db.get_mastery_collection()
        .find({"concept_id": ObjectId(concept_id)}, {"_id": 0, "score": 1, "timestamp": 1})
        .sort("timestamp", -1)
    )
    if not events:
        st.caption("No quiz history yet.")
        return
    for e in events:
        ts = e.get("timestamp")
        when = ts.strftime("%Y-%m-%d %H:%M") if ts else "?"
        st.write(f"- {when} -- score {e.get('score')}/5")
