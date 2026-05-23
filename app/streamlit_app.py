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


@st.cache_data(ttl=60)
def _total_concepts() -> int:
    return db.get_collection().count_documents({})


def main() -> None:
    st.sidebar.title("Honeycomb")
    page = st.sidebar.radio("Navigate", ["Ingest", "Graph", "Daily Review", "Mastery"])

    head, count = st.columns([4, 1])
    with head:
        st.title("Honeycomb")
        st.caption("Turn YouTube transcripts into a self-linking knowledge graph.")
    with count:
        try:
            st.metric("Concepts", _total_concepts())
        except Exception as e:  # noqa: BLE001 - surface DB issues in the UI, don't crash
            st.metric("Concepts", "?")
            st.caption(f"DB error: {e}")

    st.divider()

    pages = {
        "Ingest": render_ingest_page,
        "Graph": render_graph_page,
        "Daily Review": render_review_page,
        "Mastery": render_mastery_page,
    }
    pages[page]()


if __name__ == "__main__":
    main()
