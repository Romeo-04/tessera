"""One-off: download and parse the cited SPL sections for every formulary drug.

Writes data/spl/sections.jsonl (gitignored — large and rebuildable).
Needs no API key; DailyMed is a free public service.
"""
import csv
import json
import sys
import time
from pathlib import Path

from tessera.sources.dailymed import fetch_spl_xml, parse_sections, setids_for_rxcui

ROOT = Path(__file__).resolve().parents[1]
FORMULARY = ROOT / "data" / "formulary.csv"
OUT_DIR = ROOT / "data" / "spl"


def already_fetched(out: Path) -> set[str]:
    """RXCUIs already present in the output, so a re-run resumes.

    This job makes ~700 network round-trips and takes roughly 25 minutes. It
    was originally written with mode "w", which threw all of it away on the
    first interruption. Lines are self-contained JSON, so a partial file is
    valid input to this check.
    """
    if not out.exists():
        return set()
    done: set[str] = set()
    for line in out.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            done.add(json.loads(line)["rxcui"])
        except (json.JSONDecodeError, KeyError):
            continue  # a torn final line; that drug is simply refetched
    return done


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "sections.jsonl"
    with FORMULARY.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    done = already_fetched(out)
    if done:
        print(f"resuming: {len(done)} drugs already fetched, "
              f"{len(rows) - len(done)} to go\n", flush=True)
    rows = [r for r in rows if r["rxcui"] not in done]

    written = 0
    no_sections: list[str] = []
    no_label: list[str] = []

    with out.open("a", encoding="utf-8") as fh:
        for i, row in enumerate(rows, 1):
            rxcui, ingredient = row["rxcui"], row["ingredient"]
            try:
                setids = setids_for_rxcui(rxcui, pagesize=1)
            except Exception as exc:
                print(f"[{i}/{len(rows)}] {ingredient}: lookup failed ({exc})", flush=True)
                no_label.append(ingredient)
                continue

            if not setids:
                no_label.append(ingredient)
                print(f"[{i}/{len(rows)}] {ingredient}: no label", flush=True)
                continue

            setid = setids[0]
            try:
                sections = parse_sections(fetch_spl_xml(setid), setid)
            except Exception as exc:
                print(f"[{i}/{len(rows)}] {ingredient}: fetch failed ({exc})", flush=True)
                continue

            if not sections:
                no_sections.append(ingredient)

            for s in sections:
                fh.write(json.dumps({
                    "rxcui": rxcui, "ingredient": ingredient, "setid": s.setid,
                    "loinc": s.loinc, "section": s.section, "text": s.text,
                    "source_url": s.source_url,
                }) + "\n")
                written += 1

            print(f"[{i}/{len(rows)}] {ingredient}: {len(sections)} sections", flush=True)
            time.sleep(0.1)

    print(f"\nwrote {written} sections to {out}")
    print(f"no label found ({len(no_label)}): {no_label}")
    print(f"label but no cited sections ({len(no_sections)}): {no_sections}")
    print("\nThose two lists are drugs Tessera cannot check. The pipeline must "
          "report them as excluded, never silently omit them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
