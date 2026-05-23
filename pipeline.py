import sys
import time
from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table

import extract
import ingest
import link

_console = Console()


def run_pipeline(url: str, verbose: bool = True, progress_callback=None) -> dict:
    def log(msg: str) -> None:
        if verbose:
            _console.print(msg)

    def progress(frac: float, label: str) -> None:
        # Optional UI hook (e.g. a Streamlit progress bar); no-op by default.
        if progress_callback:
            progress_callback(frac, label)

    t0 = time.perf_counter()

    progress(0.1, "Fetching transcript")
    log(f"[bold]Fetching transcript…[/bold] {url}")
    text, meta = ingest.fetch_youtube_transcript(url)
    log(f"  {len(text):,} chars | {meta['segment_count']} segments | {meta['duration_seconds']:.0f}s")

    progress(0.4, "Extracting concepts")
    log("[bold]Extracting concepts…[/bold]")
    concepts = extract.extract_concepts(text, meta)
    log(f"  {len(concepts)} concepts extracted")

    source_meta = {
        "url": meta["url"],
        "video_id": meta["video_id"],
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }

    created_names: list[str] = []
    merged_names: list[str] = []
    progress(0.7, "Linking concepts")
    log("[bold]Linking concepts to knowledge graph…[/bold]")
    for concept in concepts:
        action, oid = link.link_or_create(concept, source_meta)
        if action == "created":
            created_names.append(concept["name"])
        else:
            merged_names.append(concept["name"])
        log(f"  [{action}] {concept['name']}  [dim]({oid})[/dim]")

    elapsed = time.perf_counter() - t0
    summary = {
        "url": url,
        "video_id": meta["video_id"],
        "transcript_chars": len(text),
        "total_concepts": len(concepts),
        "created_count": len(created_names),
        "merged_count": len(merged_names),
        "created_names": created_names,
        "merged_names": merged_names,
        "concept_names": [c["name"] for c in concepts],
        "elapsed_seconds": round(elapsed, 2),
    }

    progress(1.0, "Done")
    if verbose:
        _list_fields = {"created_names", "merged_names", "concept_names"}
        table = Table(title="Pipeline summary", show_header=True)
        table.add_column("Metric")
        table.add_column("Value", style="cyan")
        for k, v in summary.items():
            if k not in _list_fields:
                table.add_row(k, str(v))
        _console.print(table)

    return summary


if __name__ == "__main__":
    if len(sys.argv) < 2:
        _console.print("Usage: python pipeline.py <youtube_url>")
        sys.exit(1)
    run_pipeline(sys.argv[1])
