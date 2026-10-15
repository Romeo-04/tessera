"""One-off: which formulary drugs each mapped class covers -> data/class_members.json.

Reads scripts/class_map.py, asks NLM RxClass for the members of each class, and
maps every member to the formulary's ingredient code. RxClass lists members at
the precise-ingredient level ("lisinopril anhydrous"), while the formulary and
the interaction table are keyed by ingredient ("lisinopril"), so a member is
only kept if its ingredient is one we carry.

Free and offline-reproducible: no model is called. The output is committed so
the class expansion a reviewer checks is the one the table was built from.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import httpx

try:
    from scripts.class_map import CLASS_MAP
except ImportError:  # run as `python scripts/build_class_members.py`
    from class_map import CLASS_MAP

ROOT = Path(__file__).resolve().parents[1]
FORMULARY = ROOT / "data" / "formulary.csv"
OUT = ROOT / "data" / "class_members.json"
RXCLASS = "https://rxnav.nlm.nih.gov/REST/rxclass"
# DailyMed's own pharmacologic-class indexing: the same source the labels come from.
RELA = {"EPC": "has_epc", "MOA": "has_moa"}


def members_by_class(entries, find_class, class_members, ingredients, formulary,
                     not_carried=lambda name: None) -> dict[str, list[str]]:
    """{class key: sorted formulary codes}, from `formulary` {ingredient: code}.

    Exits if an RxClass class name is not found, because a silently empty class
    would quietly drop real warnings. A written-out ingredient we do not carry
    is reported to `not_carried` and skipped - expected for a short formulary.
    """
    carried = set(formulary.values())
    out: dict[str, list[str]] = {}
    for entry in entries:
        codes: set[str] = set()
        for name in entry.get("ingredients", []):
            if name in formulary:
                codes.add(formulary[name])
            else:
                not_carried(name)
        for name, ctype in entry.get("rxclass", []):
            class_id = find_class(name, ctype)
            if class_id is None:
                sys.exit(f"RxClass has no {ctype} class named {name!r} ({entry['key']});"
                         " fix scripts/class_map.py")
            for rxcui in class_members(class_id, ctype):
                codes.update(c for c in ingredients(rxcui) if c in carried)
        codes -= {formulary[n] for n in entry.get("exclude", []) if n in formulary}
        out[entry["key"]] = sorted(codes)
    return out


def _find_class(name: str, ctype: str) -> str | None:
    r = httpx.get(f"{RXCLASS}/class/byName.json",
                  params={"className": name, "classTypes": ctype}, timeout=30)
    r.raise_for_status()
    found = (r.json().get("rxclassMinConceptList") or {}).get("rxclassMinConcept") or []
    exact = [c["classId"] for c in found if c["className"].lower() == name.lower()]
    return exact[0] if exact else None


def _class_members(class_id: str, ctype: str) -> list[str]:
    r = httpx.get(f"{RXCLASS}/classMembers.json",
                  params={"classId": class_id, "relaSource": "DAILYMED", "rela": RELA[ctype]},
                  timeout=30)
    r.raise_for_status()
    group = (r.json().get("drugMemberGroup") or {}).get("drugMember") or []
    return [m["minConcept"]["rxcui"] for m in group]


def main() -> int:
    from tessera.sources.rxnorm import ingredients_of

    formulary = {r["ingredient"].lower(): r["rxcui"]
                 for r in csv.DictReader(FORMULARY.open(encoding="utf-8"))}
    not_carried: set[str] = set()

    def ingredients(rxcui: str) -> list[str]:
        try:
            return [code for code, _ in ingredients_of(f"RXCUI:{rxcui}")]
        except httpx.HTTPError:
            print(f"  ingredient lookup failed for {rxcui}; skipped")
            return []

    out = members_by_class(CLASS_MAP, _find_class, _class_members, ingredients, formulary,
                           not_carried.add)
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    for key, codes in out.items():
        print(f"{key:28} {len(codes):3} formulary drugs")
    empty = [k for k, v in out.items() if not v]
    if empty:
        print(f"\nEMPTY (no formulary drug in the class): {', '.join(empty)}")
    if not_carried:
        print(f"listed but not in the formulary: {', '.join(sorted(not_carried))}")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
