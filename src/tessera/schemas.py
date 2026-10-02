from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

RXCUI_RE = re.compile(r"^RXCUI:\d+$")

# Below this top-1 confidence we ask the user instead of guessing.
CONFIRM_THRESHOLD = 0.75


class DrugRecord(BaseModel):
    """What Omni read off one label. Device-side only — never leaves."""

    raw_name: str
    strength: str | None = None
    form: str | None = None
    directions: str | None = None


class Candidate(BaseModel):
    rxcui: str
    display_name: str
    score: float


class NormalizedDrug(BaseModel):
    record: DrugRecord
    rxcui: str | None
    display_name: str | None
    confidence: float
    candidates: list[Candidate] = Field(default_factory=list)
    in_formulary: bool = True

    @property
    def needs_confirmation(self) -> bool:
        return self.rxcui is None or self.confidence < CONFIRM_THRESHOLD


class CodeSet(BaseModel):
    """The ONLY payload permitted to cross the Privacy Gate."""

    codes: list[str]

    @field_validator("codes")
    @classmethod
    def _only_rxcui(cls, v: list[str]) -> list[str]:
        for c in v:
            if not RXCUI_RE.match(c):
                raise ValueError(f"not an RXCUI code: {c!r}")
        return v


class EvidenceSpan(BaseModel):
    span_id: str
    setid: str
    section: str
    text: str
    source_url: str


class InteractionAssertion(BaseModel):
    subject_rxcui: str
    object_rxcui: str
    severity: Literal["contraindicated", "warning", "monitor"]
    span_id: str


class RankedRisk(BaseModel):
    subject: str
    object: str
    severity: Literal["contraindicated", "warning", "monitor"]
    mechanism: str
    span_id: str
    source_url: str
    action: str


class SessionResult(BaseModel):
    risks: list[RankedRisk]
    excluded_drugs: list[str] = Field(default_factory=list)
    status: Literal["ok", "insufficient_drugs", "partial"] = "ok"
    notes: list[str] = Field(default_factory=list)
