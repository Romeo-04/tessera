from __future__ import annotations

import csv
from pathlib import Path

import typer

from tessera.config import get_settings
from tessera.corpus.index import EvidenceIndex
from tessera.pipeline import run_session
from tessera.resolve import InteractionTable
from tessera.router import Router

app = typer.Typer(help="Tessera — citation-grounded medication safety", add_completion=False)

STATUS_LINE = {
    "ok": "Checked every medication we could identify.",
    "partial": "Checked what we could — see the notes, this result is incomplete.",
    "insufficient_drugs": "Not enough identified medications to check interactions.",
}


@app.command()
def check(
    photos: list[Path] = typer.Argument(..., help="Label photographs"),
) -> None:
    """Read medication labels and report cited interaction risks."""
    s = get_settings()
    index = EvidenceIndex.load(s.data_dir / "index")
    table = InteractionTable.load(s.data_dir / "interactions.csv")
    with (s.data_dir / "formulary.csv").open(encoding="utf-8") as fh:
        formulary = {r["rxcui"] for r in csv.DictReader(fh)}
    router = Router()

    result = run_session(list(photos), index, table, router, formulary)

    typer.echo("")
    typer.echo(STATUS_LINE.get(result.status, result.status))
    for note in result.notes:
        typer.echo(f"  - {note}")

    if not result.risks:
        typer.echo("\nNo documented interactions to report.")
    for i, r in enumerate(result.risks, 1):
        typer.echo(f"\n{i}. [{r.severity.upper()}] {r.subject} + {r.object}")
        typer.echo(f"   {r.mechanism}")
        typer.echo(f"   action: {r.action}")
        typer.echo(f"   source: {r.source_url}")

    calls = router.calls()
    cost = sum(c.cost_usd for c in calls)
    typer.echo(f"\nsession cost: ${cost:.4f} over {len(calls)} model calls")
    typer.echo(
        "\nTessera surfaces documented information and cites it. It does not "
        "give medical advice. Talk to a pharmacist or prescriber."
    )


if __name__ == "__main__":
    app()
