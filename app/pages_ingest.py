"""Ingest page: run the pipeline on a URL and show what changed in the graph."""
import streamlit as st

import pipeline

# Sample sources (our test_sources.txt set) for one-click prefill.
_SAMPLES = {
    "Neural nets (3B1B)": "https://www.youtube.com/watch?v=aircAruvnKk",
    "Calculus (3B1B)": "https://www.youtube.com/watch?v=WUvTyaaNkzM",
    "French Revolution": "https://www.youtube.com/watch?v=lTTvKwCylFY",
    "Existentialism": "https://www.youtube.com/watch?v=YaDvRdLMkHs",
    "Algorithms (MIT)": "https://www.youtube.com/watch?v=HtSuA80QTyo",
}


def render_ingest_page() -> None:
    st.header("Ingest a learning source")

    if "ingest_url" not in st.session_state:
        st.session_state["ingest_url"] = next(iter(_SAMPLES.values()))

    st.caption("Sample sources:")
    cols = st.columns(len(_SAMPLES))
    for col, (label, url) in zip(cols, _SAMPLES.items()):
        # Buttons render before the text_input below, so setting the session
        # value here updates the input on the same run (no rerun needed).
        if col.button(label, key=f"sample_{label}", use_container_width=True):
            st.session_state["ingest_url"] = url

    url = st.text_input("YouTube URL", key="ingest_url")

    if st.button("Ingest", type="primary"):
        _run_ingest(url)

    summary = st.session_state.get("last_ingest")
    if summary:
        st.subheader("Last ingest")
        _render_summary(summary)


def _run_ingest(url: str) -> None:
    if not url.strip():
        st.warning("Please enter a URL.")
        return
    bar = st.progress(0.0, text="Starting...")
    try:
        summary = pipeline.run_pipeline(
            url.strip(),
            verbose=False,
            progress_callback=lambda frac, label: bar.progress(frac, text=label),
        )
        bar.empty()
        st.session_state["last_ingest"] = summary
    except Exception as e:  # noqa: BLE001 - show the real reason to the user
        bar.empty()
        st.session_state.pop("last_ingest", None)
        st.error(f"Ingest failed: {e}")


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
