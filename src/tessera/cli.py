from __future__ import annotations

import csv
import json
from pathlib import Path

import typer

from tessera.config import get_settings
from tessera.corpus.index import EvidenceIndex
from tessera.errors import RateLimitedError, TesseraError, UpstreamError
from tessera.pipeline import run_session
from tessera.resolve import InteractionTable
from tessera.router import Router

app = typer.Typer(
    help="Tessera — citation-grounded medication safety", add_completion=False
)

STATUS_LINE = {
    "ok": "Checked every medication we could identify.",
    "partial": "Checked what we could. This result is incomplete — see the notes.",
    "analysis_incomplete": "Found interactions we could not fully explain. "
                           "This result is incomplete — please ask a pharmacist.",
    "insufficient_drugs": "Not enough identified medications to check interactions.",
    "no_drugs_detected": "Could not read any medication labels.",
}

DISCLAIMER = (
    "Tessera surfaces documented information and cites it. It is not medical "
    "advice and never recommends a dose change. Talk to a pharmacist or prescriber."
)


def _load_corpus(settings):
    """Load the four built artifacts. Raises FileNotFoundError if absent."""
    index = EvidenceIndex.load(settings.data_dir / "index")
    table = InteractionTable.load(settings.data_dir / "interactions.csv")

    with (settings.data_dir / "formulary.csv").open(encoding="utf-8") as fh:
        formulary = {r["rxcui"] for r in csv.DictReader(fh)}

    # Which drugs we actually hold label evidence for — a strict subset of the
    # formulary, and the difference is what "recognised but unchecked" means.
    covered: set[str] = set()
    sections = settings.data_dir / "spl" / "sections.jsonl"
    if sections.exists():
        for line in sections.read_text(encoding="utf-8").splitlines():
            if line.strip():
                covered.add(json.loads(line)["rxcui"])

    return index, table, formulary, covered


@app.command()
def check(photos: list[Path] = typer.Argument(..., help="Label photographs")) -> None:
    """Read medication labels and report cited interaction risks."""
    settings = get_settings()

    try:
        index, table, formulary, covered = _load_corpus(settings)
    except FileNotFoundError as exc:
        typer.echo(f"Missing a built data file: {exc}")
        typer.echo(
            "Build the corpus first:\n"
            "  python scripts/build_formulary.py\n"
            "  python scripts/fetch_spl.py\n"
            "  python scripts/build_interactions.py\n"
            "  python scripts/build_index.py"
        )
        raise typer.Exit(code=2)

    router = Router()

    try:
        result = run_session(
            list(photos), index, table, router, formulary,
            covered_rxcuis=covered or None,
        )
    except RateLimitedError:
        typer.echo(
            "The model service is rate-limiting us right now, so this check did "
            "not complete. Nothing below should be read as a result. Try again "
            "in a minute."
        )
        raise typer.Exit(code=3)
    except UpstreamError as exc:
        typer.echo(
            f"The model service failed, so this check did not complete: {exc}\n"
            "No result is shown, because a partial list would look like a "
            "complete one."
        )
        raise typer.Exit(code=3)
    except TesseraError as exc:
        typer.echo(f"Tessera stopped: {exc}")
        raise typer.Exit(code=4)

    typer.echo("")
    typer.echo(STATUS_LINE.get(result.status, result.status))
    for note in result.notes:
        typer.echo(f"  - {note}")

    for req in result.needs_confirmation:
        typer.echo(f"\nWhich of these is '{req.raw_name}'?")
        for i, opt in enumerate(req.options, 1):
            typer.echo(f"   {i}. {opt.display_name}  [{opt.rxcui}]")

    if not result.risks:
        typer.echo("\nNo documented interactions to report.")
    for i, r in enumerate(result.risks, 1):
        typer.echo(f"\n{i}. [{r.severity.upper()}] {r.subject_label} + {r.object_label}")
        typer.echo(f"   {r.mechanism}")
        typer.echo(f"   action: {r.action}")
        typer.echo(f"   source: {r.source_url}")

    calls = router.calls()
    cost = sum(c.cost_usd for c in calls)
    typer.echo(f"\nsession cost: ${cost:.4f} over {len(calls)} model calls")
    typer.echo(f"\n{DISCLAIMER}")


if __name__ == "__main__":
    app()
