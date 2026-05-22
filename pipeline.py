import sys
import time
from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table

import extract
import ingest
import link

_console = Console()


def run_pipeline(url: str, verbose: bool = True) -> dict:
    def log(msg: str) -> None:
        if verbose:
            _console.print(msg)

    t0 = time.perf_counter()

    log(f"[bold]Fetching transcript…[/bold] {url}")
    text, meta = ingest.fetch_youtube_transcript(url)
    log(f"  {len(text):,} chars | {meta['segment_count']} segments | {meta['duration_seconds']:.0f}s")

    log("[bold]Extracting concepts…[/bold]")
    concepts = extract.extract_concepts(text, meta)
    log(f"  {len(concepts)} concepts extracted")

    source_meta = {
        "url": meta["url"],
        "video_id": meta["video_id"],
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }

    created_count = merged_count = 0
    log("[bold]Linking concepts to knowledge graph…[/bold]")
    for concept in concepts:
        action, oid = link.link_or_create(concept, source_meta)
        if action == "created":
            created_count += 1
        else:
            merged_count += 1
        log(f"  [{action}] {concept['name']}  [dim]({oid})[/dim]")

    elapsed = time.perf_counter() - t0
    summary = {
        "url": url,
        "video_id": meta["video_id"],
        "transcript_chars": len(text),
        "total_concepts": len(concepts),
        "created_count": created_count,
        "merged_count": merged_count,
        "concept_names": [c["name"] for c in concepts],
        "elapsed_seconds": round(elapsed, 2),
    }

    if verbose:
        table = Table(title="Pipeline summary", show_header=True)
        table.add_column("Metric")
        table.add_column("Value", style="cyan")
        for k, v in summary.items():
            if k != "concept_names":
                table.add_row(k, str(v))
        _console.print(table)

    return summary


if __name__ == "__main__":
    if len(sys.argv) < 2:
        _console.print("Usage: python pipeline.py <youtube_url>")
        sys.exit(1)
    run_pipeline(sys.argv[1])
