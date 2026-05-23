"""Graph page: render concepts as nodes and prerequisite links as edges."""
import streamlit as st
from streamlit_agraph import Config, Edge, Node, agraph

import db


@st.cache_data(ttl=60)
def _load_concepts() -> list[dict]:
    docs = db.get_collection().find({}, {"name": 1, "prerequisites": 1, "_id": 0})
    return [
        {"name": d.get("name", ""), "prerequisites": d.get("prerequisites", [])}
        for d in docs
        if d.get("name")
    ]


def render_graph_page() -> None:
    st.header("Knowledge graph")
    concepts = _load_concepts()
    if not concepts:
        st.info("No concepts yet. Ingest a source first.")
        return

    name_filter = st.text_input("Filter nodes by name (substring)", value="").strip().lower()

    # Edges: prereq -> concept, but only when the prereq names an existing concept.
    by_lower = {c["name"].lower(): c["name"] for c in concepts}
    edges_raw: list[tuple[str, str]] = []
    for c in concepts:
        for pre in c.get("prerequisites", []):
            src = by_lower.get(pre.lower().strip())
            if src and src != c["name"]:
                edges_raw.append((src, c["name"]))

    # Degree over the FULL graph (stats are not affected by the view filter).
    degree = {c["name"]: 0 for c in concepts}
    for s, t in edges_raw:
        degree[s] += 1
        degree[t] += 1
    orphans = sum(1 for d in degree.values() if d == 0)

    c1, c2, c3 = st.columns(3)
    c1.metric("Nodes", len(concepts))
    c2.metric("Edges", len(edges_raw))
    c3.metric("Orphans", orphans)

    # Apply the filter to the rendered view only.
    visible = {c["name"] for c in concepts if (name_filter in c["name"].lower() or not name_filter)}
    if not visible:
        st.info("No nodes match the filter.")
        return

    nodes = [Node(id=n, label=n, size=25) for n in visible]
    edges = [Edge(source=s, target=t) for s, t in edges_raw if s in visible and t in visible]
    config = Config(
        width=1000,
        height=600,
        directed=True,
        physics=True,
        nodeHighlightBehavior=True,
        highlightColor="#F7A7A6",
    )
    agraph(nodes=nodes, edges=edges, config=config)
