from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# \A..\Z and [0-9], not ^..$ and \d: "$" accepts a trailing newline and "\d"
# accepts any Unicode digit. Neither belongs in the only payload that may leave.
RXCUI_RE = re.compile(r"\ARXCUI:[0-9]+\Z")

# Below this top-1 confidence we ask the user instead of guessing.
CONFIRM_THRESHOLD = 0.75


class DrugRecord(BaseModel):
    """What the vision model read off one label. Device-side only — never leaves."""

    raw_name: str
    strength: str | None = None
    form: str | None = None
    directions: str | None = None


class Candidate(BaseModel):
    rxcui: str
    display_name: str
    # Relative to the best candidate in the same response: the top is 1.0.
    # Good for "is the winner clearly ahead?", useless as match quality.
    score: float
    # The source's own unbounded score, carried because `score` is 1.0 for the
    # top candidate by construction and so cannot say whether ANY match is good.
    raw_score: float | None = None


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
    # The class phrase as the label wrote it ("ACE inhibitors") when the label
    # warned about the object's class rather than naming it. None means the
    # label names the object drug itself.
    via_class: str | None = None

    @field_validator("via_class", mode="before")
    @classmethod
    def _blank_is_named(cls, v):
        return v or None


class RankedRisk(BaseModel):
    subject: str
    object: str
    # Attached on the device AFTER the server returns, from the local code ->
    # name map. The names never crossed the gate; they are re-joined on the
    # side that already had them. None when we cannot name the code locally -
    # an unnamed code is better than an invented name.
    subject_name: str | None = None
    object_name: str | None = None
    severity: Literal["contraindicated", "warning", "monitor"]
    mechanism: str
    span_id: str
    source_url: str
    action: str
    # The cited label text itself. Public FDA text, so it may travel; it lets
    # the reader check the sentence above against its source in place.
    quote: str | None = None
    # Set when the label warns about the object's class ("ACE inhibitors")
    # rather than naming it, so the reader is told why the quote does not
    # mention their drug by name.
    via_class: str | None = None

    @property
    def subject_label(self) -> str:
        return self.subject_name or self.subject

    @property
    def object_label(self) -> str:
        return self.object_name or self.object


class ConfirmationRequest(BaseModel):
    """A drug we refused to identify, and the options we could not choose between.

    Abstaining is only useful if the caller can actually ask, so the options
    travel with the refusal instead of being discarded at the boundary.
    """

    raw_name: str
    options: list[Candidate]


class SessionResult(BaseModel):
    risks: list[RankedRisk]
    excluded_drugs: list[str] = Field(default_factory=list)
    # In the formulary, but we hold no label evidence for them. Distinct from
    # excluded: we recognise the drug, we just cannot speak to it.
    unchecked_drugs: list[str] = Field(default_factory=list)
    needs_confirmation: list[ConfirmationRequest] = Field(default_factory=list)
    # Ordered by how badly the user is misled if the status is wrong:
    #   no_drugs_detected    - we could not read the photographs at all
    #   insufficient_drugs   - fewer than two drugs identified; nothing to pair
    #   analysis_incomplete  - interactions were found but could not be explained
    #   partial              - some drugs are outside scope or lack evidence
    #   ok                   - everything identified was checked
    status: Literal[
        "ok", "partial", "analysis_incomplete", "insufficient_drugs",
        "no_drugs_detected",
    ] = "ok"
    notes: list[str] = Field(default_factory=list)
