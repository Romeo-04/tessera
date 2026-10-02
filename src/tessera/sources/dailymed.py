from __future__ import annotations

from dataclasses import dataclass

import httpx
from lxml import etree

BASE = "https://dailymed.nlm.nih.gov/dailymed/services/v2"
WEB = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}"
TIMEOUT = httpx.Timeout(30.0)

# The only sections we ingest. Everything else is noise we would never cite.
CITED_SECTIONS: dict[str, str] = {
    "34073-7": "Drug Interactions",
    "43685-7": "Warnings and Precautions",
    "34070-3": "Contraindications",
}


@dataclass(frozen=True)
class RawSection:
    setid: str
    loinc: str
    section: str
    text: str
    source_url: str


def setids_for_rxcui(rxcui: str, pagesize: int = 5) -> list[str]:
    bare = rxcui.removeprefix("RXCUI:")
    r = httpx.get(
        f"{BASE}/spls.json",
        params={"rxcui": bare, "pagesize": pagesize},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return [d["setid"] for d in r.json().get("data", [])]


def fetch_spl_xml(setid: str) -> bytes:
    r = httpx.get(f"{BASE}/spls/{setid}.xml", timeout=TIMEOUT)
    r.raise_for_status()
    return r.content


def parse_sections(xml: bytes, setid: str) -> list[RawSection]:
    """Pull only the cited sections, each with a resolvable public URL.

    A section with no readable text is dropped rather than emitted empty.
    Downstream must be able to tell "this label documents no interactions"
    from "we have no data for this label" — absence of evidence must never
    reach the index as evidence of safety.
    """
    try:
        root = etree.fromstring(xml)
    except etree.XMLSyntaxError:
        return []

    out: list[RawSection] = []
    seen: set[str] = set()
    for code_el in root.iter("{urn:hl7-org:v3}code"):
        loinc = code_el.get("code")
        if loinc not in CITED_SECTIONS or loinc in seen:
            continue
        section_el = code_el.getparent()
        if section_el is None:
            continue
        text = " ".join(
            t.strip() for t in section_el.itertext() if t and t.strip()
        ).strip()
        if not text:
            continue
        seen.add(loinc)
        out.append(
            RawSection(
                setid=setid,
                loinc=loinc,
                section=CITED_SECTIONS[loinc],
                text=text,
                source_url=WEB.format(setid=setid),
            )
        )
    return out
