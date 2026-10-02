import json

import pytest

from tessera.privacy import PrivacyViolation, to_code_set
from tessera.schemas import DrugRecord, NormalizedDrug


def drug(rxcui, name="METFORMIN HCL ER 500MG", conf=1.0):
    return NormalizedDrug(
        record=DrugRecord(
            raw_name=name,
            strength="500 mg",
            form="tablet, extended release",
            directions="Take twice daily with food",
        ),
        rxcui=rxcui,
        display_name="metformin ER",
        confidence=conf,
        candidates=[],
    )


def test_only_codes_survive_the_gate():
    cs = to_code_set([drug("RXCUI:860975"), drug("RXCUI:29046")])
    assert cs.codes == ["RXCUI:29046", "RXCUI:860975"]


def test_serialised_payload_contains_no_label_text_at_all():
    """The actual privacy claim, asserted on the wire format rather than the
    object graph - what leaves the device is the serialised form."""
    payload = json.dumps(to_code_set([drug("RXCUI:860975")]).model_dump())
    for leak in (
        "METFORMIN", "metformin", "500 mg", "twice daily",
        "raw_name", "directions", "tablet", "display_name",
    ):
        assert leak not in payload, f"{leak!r} leaked through the gate"


def test_unresolved_drugs_never_cross():
    cs = to_code_set([drug("RXCUI:860975"), drug(None)])
    assert cs.codes == ["RXCUI:860975"]


def test_a_malformed_code_is_refused_loudly():
    bad = drug("RXCUI:860975")
    bad.rxcui = "metformin"
    with pytest.raises(PrivacyViolation):
        to_code_set([bad])


def test_an_injected_non_numeric_code_is_refused():
    bad = drug("RXCUI:860975")
    bad.rxcui = "RXCUI:860975; DROP TABLE"
    with pytest.raises(PrivacyViolation):
        to_code_set([bad])


def test_duplicate_codes_collapse():
    cs = to_code_set([drug("RXCUI:860975"), drug("RXCUI:860975")])
    assert cs.codes == ["RXCUI:860975"]


def test_an_empty_input_produces_an_empty_code_set():
    assert to_code_set([]).codes == []
