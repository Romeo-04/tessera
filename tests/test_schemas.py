import pytest
from pydantic import ValidationError

from tessera.schemas import CodeSet, DrugRecord, NormalizedDrug


def test_drug_record_holds_raw_label_text():
    r = DrugRecord(
        raw_name="METFORMIN HCl ER 500MG",
        strength="500 mg",
        form="tablet, extended release",
        directions="Take 1 tablet by mouth twice daily",
    )
    assert r.raw_name.startswith("METFORMIN")


def test_codeset_rejects_anything_that_is_not_an_rxcui():
    with pytest.raises(ValidationError):
        CodeSet(codes=["metformin"])
    with pytest.raises(ValidationError):
        CodeSet(codes=["RXCUI:abc"])


def test_codeset_accepts_well_formed_codes():
    cs = CodeSet(codes=["RXCUI:860975", "RXCUI:1049640"])
    assert len(cs.codes) == 2


def test_normalized_drug_marks_low_confidence_as_needing_confirmation():
    d = NormalizedDrug(
        record=DrugRecord(raw_name="METFORMIN 500"),
        rxcui="RXCUI:860975",
        display_name="metformin ER 500 MG",
        confidence=0.41,
        candidates=[],
    )
    assert d.needs_confirmation is True
