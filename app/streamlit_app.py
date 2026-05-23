"""Honeycomb Streamlit app -- single entry point with custom sidebar nav.

We deliberately do NOT use Streamlit's pages/ folder so we control the sidebar
nav and dispatch ourselves. Each page is a render_*() function in its own module.
"""
import sys
from pathlib import Path

import streamlit as st

# Make root modules (pipeline, db, mastery, quiz, ...) importable under `streamlit run`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
from app.pages_graph import render_graph_page
from app.pages_ingest import render_ingest_page
from app.pages_mastery import render_mastery_page
from app.pages_review import render_review_page

st.set_page_config(page_title="Honeycomb", layout="wide", initial_sidebar_state="expanded")

# Graph is the landing page so the hero is the first thing users see.
NAV_OPTIONS = ["Graph", "Ingest", "Daily Review", "Mastery"]

_CSS = """
<style>
#MainMenu, header, footer {visibility: hidden;}
.stApp { background: linear-gradient(180deg, #0a0a0a 0%, #1a1a1a 100%); }
.hc-card { border: 1px solid rgba(250,250,250,0.12); border-radius: 12px; padding: 14px;
           background: rgba(255,255,255,0.02); }
[data-testid="stMetricValue"] { font-size: 2rem; }
.hc-title { font-size: 2.5rem; font-weight: 800; line-height: 1.1; margin: 0; }
.hc-tagline { color: #9aa0a6; font-size: 0.95rem; margin-top: 2px; }
.hc-count { text-align: right; }
.hc-count .n { font-size: 2.2rem; font-weight: 800; color: #f5b301; line-height: 1.1; }
.hc-count .l { color: #9aa0a6; font-size: 0.8rem; letter-spacing: 0.06em; }
.hc-chip { display:inline-block; padding:4px 10px; margin:3px; border-radius:14px;
           background:#2b2f36; color:#e8eaed; font-size:0.85rem; }
section[data-testid="stSidebar"] { background: #0d0d0d; }
section[data-testid="stSidebar"] .stRadio label { padding: 4px 6px; border-radius: 8px; }
</style>
"""


@st.cache_data(ttl=60)
def _total_concepts() -> int:
    return db.get_collection().count_documents({})


def main() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

    # Programmatic page switch (e.g. graph "Quiz me on this"): set the radio's
    # session value BEFORE the widget is instantiated -- Streamlit forbids
    # changing a widget's state after it is created in the same run.
    if "_goto" in st.session_state:
        st.session_state["nav"] = st.session_state.pop("_goto")

    st.sidebar.title("Honeycomb")
    st.sidebar.caption("Your evolving learning graph")
    page = st.sidebar.radio("Navigate", NAV_OPTIONS, key="nav")

    head, count = st.columns([4, 1])
    with head:
        st.markdown(
            "<p class='hc-title'>Honeycomb</p>"
            "<p class='hc-tagline'>Turn YouTube transcripts into a self-linking knowledge graph.</p>",
            unsafe_allow_html=True,
        )
    with count:
        try:
            total = _total_concepts()
        except Exception:  # noqa: BLE001 - surface DB issues without crashing the app
            total = "?"
        st.markdown(
            f"<div class='hc-card hc-count'><div class='n'>{total}</div>"
            f"<div class='l'>CONCEPTS</div></div>",
            unsafe_allow_html=True,
        )

    st.divider()

    {
        "Graph": render_graph_page,
        "Ingest": render_ingest_page,
        "Daily Review": render_review_page,
        "Mastery": render_mastery_page,
    }[page]()


if __name__ == "__main__":
    main()
