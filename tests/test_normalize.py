from tessera.normalize import normalize_drugs
from tessera.schemas import Candidate, DrugRecord

FORMULARY = {"RXCUI:860975", "RXCUI:29046"}


def fake_match(scores):
    def _match(term, max_entries=20):
        return [Candidate(rxcui=r, display_name=n, score=s) for r, n, s in scores]

    return _match


def test_confident_unambiguous_match_is_accepted():
    out = normalize_drugs(
        [DrugRecord(raw_name="METFORMIN ER 500")], FORMULARY,
        fake_match([("RXCUI:860975", "metformin ER 500 MG", 1.0),
                    ("RXCUI:29046", "lisinopril", 0.20)]),
    )
    assert out[0].rxcui == "RXCUI:860975"
    assert out[0].needs_confirmation is False


def test_two_near_equal_candidates_force_confirmation():
    """Review Focus 2: never pick arbitrarily between equal candidates.

    A 500 mg extended-release and a 500 mg immediate-release are different
    drugs to a pharmacist and identical to a fuzzy string match.
    """
    out = normalize_drugs(
        [DrugRecord(raw_name="METFORMIN 500")], FORMULARY,
        fake_match([("RXCUI:860975", "metformin ER 500 MG", 1.0),
                    ("RXCUI:29046", "metformin IR 500 MG", 0.98)]),
    )
    assert out[0].needs_confirmation is True
    assert len(out[0].candidates) == 2, "the user needs the options to choose from"


def test_clear_separation_between_candidates_is_accepted():
    out = normalize_drugs(
        [DrugRecord(raw_name="METFORMIN 500")], FORMULARY,
        fake_match([("RXCUI:860975", "metformin ER 500 MG", 1.0),
                    ("RXCUI:29046", "something else", 0.80)]),
    )
    assert out[0].needs_confirmation is False


def test_drug_outside_the_formulary_is_marked_excluded_not_dropped():
    """Review Focus 1: the user must be told the answer is partial.

    Silently dropping it produces a confident, incomplete safety answer, which
    is the most dangerous failure this system has.
    """
    out = normalize_drugs(
        [DrugRecord(raw_name="PHENPROCOUMON")], FORMULARY,
        fake_match([("RXCUI:999999", "phenprocoumon", 1.0)]),
    )
    assert len(out) == 1, "the drug must still appear in the output"
    assert out[0].in_formulary is False
    assert out[0].rxcui is None


def test_no_candidates_at_all_still_returns_a_row():
    out = normalize_drugs(
        [DrugRecord(raw_name="qqzz")], FORMULARY, fake_match([])
    )
    assert len(out) == 1
    assert out[0].rxcui is None
    assert out[0].needs_confirmation is True


def test_strength_is_used_to_disambiguate_the_query():
    seen = {}

    def _match(term, max_entries=20):
        seen["term"] = term
        return [Candidate(rxcui="RXCUI:860975", display_name="m", score=1.0)]

    normalize_drugs(
        [DrugRecord(raw_name="METFORMIN", strength="500 mg")], FORMULARY, _match
    )
    assert "500 mg" in seen["term"]


def test_every_input_record_produces_exactly_one_output_row():
    out = normalize_drugs(
        [DrugRecord(raw_name="A"), DrugRecord(raw_name="B"), DrugRecord(raw_name="C")],
        FORMULARY, fake_match([]),
    )
    assert len(out) == 3
