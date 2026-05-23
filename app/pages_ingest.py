"""Ingest page: run the pipeline on a URL and show what changed in the graph."""
import streamlit as st

import pipeline

_DEFAULT_URL = "https://www.youtube.com/watch?v=aircAruvnKk"  # 3Blue1Brown neural nets


def render_ingest_page() -> None:
    st.header("Ingest a learning source")
    url = st.text_input("YouTube URL", value=_DEFAULT_URL)

    if st.button("Ingest", type="primary"):
        if not url.strip():
            st.warning("Please enter a URL.")
        else:
            try:
                with st.spinner("Fetching transcript, extracting concepts, linking to graph..."):
                    st.session_state["last_ingest"] = pipeline.run_pipeline(
                        url.strip(), verbose=False
                    )
            except Exception as e:  # noqa: BLE001 - show the real reason to the user
                st.session_state.pop("last_ingest", None)
                st.error(f"Ingest failed: {e}")

    summary = st.session_state.get("last_ingest")
    if summary:
        _render_summary(summary)


def _render_summary(summary: dict) -> None:
    st.success(f"Ingested {summary['url']}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Concepts extracted", summary["total_concepts"])
    c2.metric("New", summary["created_count"])
    c3.metric("Merged", summary["merged_count"])
    c4.metric("Elapsed (s)", summary["elapsed_seconds"])

    st.subheader("Concepts")
    created = set(summary.get("created_names", []))
    for name in summary.get("concept_names", []):
        badge = ":green-badge[NEW]" if name in created else ":blue-badge[MERGED]"
        st.markdown(f"{badge} {name}")
