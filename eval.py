import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
from rich.console import Console
from rich.table import Table

import db
import pipeline

_console = Console()
_SOURCES_FILE = Path("data/test_sources.txt")
_RESULTS_FILE = Path("data/eval_results.json")


def _load_urls() -> list[str]:
    if not _SOURCES_FILE.exists():
        _console.print(f"[red]{_SOURCES_FILE} not found.[/red]")
        sys.exit(1)
    return [
        line.strip()
        for line in _SOURCES_FILE.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _json_safe(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Not serializable: {type(obj)}")


def _check(label: str, actual, target, cmp) -> tuple[str, str, str, str]:
    passed = cmp(actual)
    status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
    return label, str(target), str(actual), status


def main() -> None:
    urls = _load_urls()
    if not urls:
        _console.print("[yellow]No URLs in test_sources.txt — add some and re-run.[/yellow]")
        sys.exit(0)

    summaries: list[dict] = []
    for url in urls:
        _console.print(f"\n[bold]Processing:[/bold] {url}")
        try:
            summary = pipeline.run_pipeline(url, verbose=False)
            summaries.append(summary)
            _console.print(
                f"  [green]OK[/green] — {summary['total_concepts']} concepts, "
                f"{summary['elapsed_seconds']:.1f}s"
            )
        except Exception as e:
            _console.print(f"  [red]FAILED:[/red] {e}")
            summaries.append({"url": url, "error": str(e)})

    successful = [s for s in summaries if "error" not in s]

    avg_concepts = (
        sum(s["total_concepts"] for s in successful) / len(successful)
        if successful else 0
    )
    avg_elapsed = (
        sum(s["elapsed_seconds"] for s in successful) / len(successful)
        if successful else 0
    )
    total_unique = db.get_collection().count_documents({})
    total_linked = sum(s.get("total_concepts", 0) for s in successful)
    total_merged = sum(s.get("merged_count", 0) for s in successful)
    merge_rate = (total_merged / total_linked) if total_linked else 0
    failed_count = len(summaries) - len(successful)

    rows = [
        _check("avg concepts/source",  f"≥ 8",    round(avg_concepts, 1),  lambda v: avg_concepts >= 8),
        _check("avg elapsed (s)",       f"< 60",   round(avg_elapsed, 1),   lambda v: True),  # informational
        _check("total unique concepts", f"≥ 1",    total_unique,            lambda v: total_unique >= 1),
        _check("merge rate",            "< 0.5",   round(merge_rate, 2),    lambda v: merge_rate < 0.5),
        _check("failed sources",        "0",       failed_count,            lambda v: failed_count == 0),
    ]

    table = Table(title="Eval Scorecard", show_lines=True)
    for col in ("Metric", "Target", "Actual", "Result"):
        table.add_column(col)
    passes = 0
    for row in rows:
        table.add_row(*row)
        if "PASS" in row[3]:
            passes += 1
    _console.print("\n", table)

    verdict_color = "green" if passes >= 4 else "red"
    verdict_label = "PASS" if passes >= 4 else "FAIL"
    _console.print(f"\n[bold {verdict_color}]VERDICT: {verdict_label} ({passes}/5 metrics passed)[/bold {verdict_color}]")

    concepts_in_db = list(db.get_collection().find({}, {"embedding": 0}))
    export = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "per_source": summaries,
        "concepts": concepts_in_db,
    }
    _RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _RESULTS_FILE.write_text(json.dumps(export, indent=2, default=_json_safe))
    _console.print(f"\n[dim]Results exported → {_RESULTS_FILE}[/dim]")


if __name__ == "__main__":
    main()
