"""Graph page: concepts as nodes, prerequisite links as edges, colored by domain."""
from collections import Counter

import streamlit as st
from streamlit_agraph import Config, Edge, Node, agraph

import db

_PALETTE = ["#e6550d", "#3182bd", "#31a354", "#756bb1", "#d6616b"]
_NEUTRAL = "#888888"  # node not in any domain anchor's component
_ORPHAN = "#444444"   # node with no edges at all


@st.cache_data(ttl=60)
def _load_concepts() -> list[dict]:
    docs = db.get_collection().find(
        {}, {"name": 1, "definition": 1, "prerequisites": 1, "_id": 0}
    )
    return [
        {
            "name": d.get("name", ""),
            "definition": d.get("definition", ""),
            "prerequisites": d.get("prerequisites", []),
        }
        for d in docs
        if d.get("name")
    ]


def _build_edges(concepts, by_lower):
    edges = []
    for c in concepts:
        for pre in c.get("prerequisites", []):
            src = by_lower.get(pre.lower().strip())
            if src and src != c["name"]:
                edges.append((src, c["name"]))
    return edges


def _components(names, edges):
    adj = {n: set() for n in names}
    for s, t in edges:
        adj[s].add(t)
        adj[t].add(s)
    comp, cid = {}, 0
    for n in names:
        if n in comp:
            continue
        stack, comp[n] = [n], cid
        while stack:
            for nb in adj[stack.pop()]:
                if nb not in comp:
                    comp[nb] = cid
                    stack.append(nb)
        cid += 1
    return comp, adj


def _anchor_colors(concepts, by_lower, comp):
    """Top-5 prereq strings that name a real concept become domain anchors;
    each anchor's connected component gets a distinct palette color."""
    counter: Counter = Counter()
    for c in concepts:
        for pre in c.get("prerequisites", []):
            key = pre.lower().strip()
            if key in by_lower:
                counter[by_lower[key]] += 1
    anchors = [name for name, _ in counter.most_common(5)]
    comp_color = {}
    for i, anchor in enumerate(anchors):
        comp_color.setdefault(comp[anchor], _PALETTE[i % len(_PALETTE)])
    return anchors, comp_color


def render_graph_page() -> None:
    st.header("Knowledge graph")
    concepts = _load_concepts()
    if not concepts:
        st.info("No concepts yet. Ingest a source first.")
        return

    names = [c["name"] for c in concepts]
    by_lower = {c["name"].lower(): c["name"] for c in concepts}
    edges = _build_edges(concepts, by_lower)
    comp, adj = _components(names, edges)
    anchors, comp_color = _anchor_colors(concepts, by_lower, comp)

    focus = st.selectbox("Focus domain", ["All"] + anchors)

    orphans = sum(1 for n in names if not adj[n])
    c1, c2, c3 = st.columns(3)
    c1.metric("Nodes", len(names))
    c2.metric("Edges", len(edges))
    c3.metric("Orphans", orphans)

    if focus == "All":
        visible = set(names)
    else:
        visible = {n for n in names if comp[n] == comp[focus]}

    nodes = []
    for n in names:
        if n not in visible:
            continue
        if not adj[n]:
            nodes.append(Node(id=n, label=n, size=15, color=_ORPHAN))
        else:
            nodes.append(Node(id=n, label=n, size=25, color=comp_color.get(comp[n], _NEUTRAL)))
    vis_edges = [Edge(source=s, target=t) for s, t in edges if s in visible and t in visible]

    config = Config(
        width=1200,
        height=600,
        directed=True,
        physics=True,
        hierarchical=False,
        nodeHighlightBehavior=True,
        highlightColor="#F7A7A6",
    )
    clicked = agraph(nodes=nodes, edges=vis_edges, config=config)

    if clicked:
        doc = next((c for c in concepts if c["name"] == clicked), None)
        if doc:
            prereqs = ", ".join(doc.get("prerequisites", [])) or "(none)"
            st.info(
                f"**{doc['name']}**\n\n{doc.get('definition', '')}\n\n**Prerequisites:** {prereqs}"
            )
