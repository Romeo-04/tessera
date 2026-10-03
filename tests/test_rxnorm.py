import json
from pathlib import Path

import httpx
import respx

from tessera.sources.rxnorm import approximate_match

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "rxnorm_approximate.json").read_text()
)

ENDPOINT = "https://rxnav.nlm.nih.gov/REST/approximateTerm.json"


@respx.mock
def test_approximate_match_returns_scored_candidates_best_first():
    respx.get(url__startswith=ENDPOINT).mock(
        return_value=httpx.Response(200, json=FIXTURE)
    )
    cands = approximate_match("METFORMIN HCL ER 500MG")
    assert cands, "expected at least one candidate"
    assert all(c.rxcui.startswith("RXCUI:") for c in cands)
    assert cands == sorted(cands, key=lambda c: -c.score)


@respx.mock
def test_scores_are_normalised_against_the_best_candidate():
    """RxNorm's raw score is unbounded (~8-15 in practice), not a percentage.

    Only separation between candidates carries meaning, so the top candidate
    is defined as 1.0 and everything else is its share of that.
    """
    respx.get(url__startswith=ENDPOINT).mock(
        return_value=httpx.Response(
            200,
            json={
                "approximateGroup": {
                    "candidate": [
                        {"rxcui": "111", "name": "alpha", "score": "12.44"},
                        {"rxcui": "222", "name": "beta", "score": "11.97"},
                    ]
                }
            },
        )
    )
    cands = approximate_match("whatever")
    assert cands[0].score == 1.0
    assert 0.96 < cands[1].score < 0.97


@respx.mock
def test_repeated_rxcui_collapses_to_its_best_scoring_entry():
    """RxNorm returns the same rxcui several times with different scores."""
    respx.get(url__startswith=ENDPOINT).mock(
        return_value=httpx.Response(
            200,
            json={
                "approximateGroup": {
                    "candidate": [
                        {"rxcui": "860975", "name": "metformin ER", "score": "14.35"},
                        {"rxcui": "860975", "name": None, "score": "14.32"},
                        {"rxcui": "861007", "name": "other", "score": "8.19"},
                    ]
                }
            },
        )
    )
    cands = approximate_match("METFORMIN")
    assert [c.rxcui for c in cands] == ["RXCUI:860975", "RXCUI:861007"]
    assert cands[0].display_name == "metformin ER"


@respx.mock
def test_best_available_name_is_kept_even_when_the_top_entry_has_none():
    """RxNorm's highest-scoring entry for a concept often has a null name.

    The name is what the user is shown when we ask them to confirm an
    ambiguous match, so taking the top entry's null and stopping there leaves
    them choosing between blanks.
    """
    respx.get(url__startswith=ENDPOINT).mock(
        return_value=httpx.Response(
            200,
            json={
                "approximateGroup": {
                    "candidate": [
                        {"rxcui": "6809", "name": None, "score": "14.35"},
                        {"rxcui": "6809", "name": "metformin", "score": "14.32"},
                    ]
                }
            },
        )
    )
    cands = approximate_match("METFORMIN")
    assert len(cands) == 1
    assert cands[0].display_name == "metformin"


@respx.mock
def test_approximate_match_returns_empty_list_when_nothing_matches():
    respx.get(url__startswith=ENDPOINT).mock(
        return_value=httpx.Response(200, json={"approximateGroup": {}})
    )
    assert approximate_match("qqzzxx notadrug") == []


# ---- ingredient-level matching ----------------------------------------------
# Live RxNorm answers a bottle label with strength-level concepts
# ("METF0RMIN 500 mg" -> 316256 "metformin 500 MG"), while the formulary and the
# interaction table are keyed by ingredient (metformin = 6809). Observed
# 2026-10-03; without this mapping nearly every real label is "out of scope".

from tessera.schemas import Candidate  # noqa: E402
from tessera.sources.rxnorm import ingredients_of, match_ingredients  # noqa: E402

HISTORY = "https://rxnav.nlm.nih.gov/REST/rxcui/{}/historystatus.json"
RELATED = "https://rxnav.nlm.nih.gov/REST/rxcui/{}/related.json"


def _history(rxcui, tty, bases):
    return {"rxcuiStatusHistory": {
        "metaData": {"status": "Active"},
        "attributes": {"rxcui": rxcui, "tty": tty},
        "definitionalFeatures": {"ingredientAndStrength": [
            {"baseRxcui": b, "baseName": n} for b, n in bases]},
    }}


@respx.mock
def test_a_strength_level_concept_maps_to_its_ingredient():
    ingredients_of.cache_clear()
    respx.get(HISTORY.format("316256")).mock(return_value=httpx.Response(
        200, json=_history("316256", "SCDC", [("6809", "metformin")])))
    assert ingredients_of("RXCUI:316256") == (("RXCUI:6809", "metformin"),)


@respx.mock
def test_an_ingredient_maps_to_itself():
    ingredients_of.cache_clear()
    respx.get(HISTORY.format("29046")).mock(return_value=httpx.Response(
        200, json={"rxcuiStatusHistory": {"metaData": {}, "attributes": {
            "rxcui": "29046", "tty": "IN", "name": "lisinopril"}}}))
    assert ingredients_of("RXCUI:29046") == (("RXCUI:29046", "lisinopril"),)


@respx.mock
def test_a_concept_with_no_strength_falls_back_to_related_ingredients():
    ingredients_of.cache_clear()
    respx.get(HISTORY.format("214250")).mock(return_value=httpx.Response(
        200, json={"rxcuiStatusHistory": {"metaData": {}, "attributes": {"tty": "MIN"}}}))
    respx.get(url__startswith=RELATED.format("214250")).mock(return_value=httpx.Response(
        200, json={"relatedGroup": {"conceptGroup": [{"tty": "IN", "conceptProperties": [
            {"rxcui": "1191", "name": "aspirin"}, {"rxcui": "1886", "name": "caffeine"}]}]}}))
    assert ingredients_of("RXCUI:214250") == (
        ("RXCUI:1191", "aspirin"), ("RXCUI:1886", "caffeine"))


def _fake(cands, mapping):
    match = lambda term, max_entries=20: cands  # noqa: E731
    ing = lambda rxcui: mapping.get(rxcui, ())  # noqa: E731
    return match, ing


def test_strengths_of_one_ingredient_collapse_to_that_ingredient():
    """Three metformin strengths are one answer, not an ambiguity."""
    match, ing = _fake(
        [Candidate(rxcui="RXCUI:316256", display_name="metformin 500 MG", score=1.0, raw_score=12.0),
         Candidate(rxcui="RXCUI:861007", display_name="METFORMIN HCL 500MG TAB", score=0.94, raw_score=11.3),
         Candidate(rxcui="RXCUI:4821", display_name="glipizide", score=0.5, raw_score=6.0)],
        {"RXCUI:316256": (("RXCUI:6809", "metformin"),),
         "RXCUI:861007": (("RXCUI:6809", "metformin"),),
         "RXCUI:4821": (("RXCUI:4821", "glipizide"),)},
    )
    out = match_ingredients("METF0RMIN 500 mg", match_fn=match, ingredient_fn=ing)
    assert [c.rxcui for c in out] == ["RXCUI:6809", "RXCUI:4821"]
    assert out[0].score == 1.0 and out[0].raw_score == 12.0
    assert out[0].display_name == "metformin"
    assert abs(out[1].score - 0.5) < 1e-9


def test_a_combination_product_is_not_replaced_by_a_single_ingredient():
    """If the label is lisinopril/HCTZ, answering 'lisinopril' would be wrong."""
    match, ing = _fake(
        [Candidate(rxcui="RXCUI:214618", display_name="hydrochlorothiazide / lisinopril", score=1.0),
         Candidate(rxcui="RXCUI:29046", display_name="lisinopril", score=0.9)],
        {"RXCUI:214618": (("RXCUI:5487", "hydrochlorothiazide"), ("RXCUI:29046", "lisinopril")),
         "RXCUI:29046": (("RXCUI:29046", "lisinopril"),)},
    )
    out = match_ingredients("LISINOPRIL-HCTZ", match_fn=match, ingredient_fn=ing)
    assert out[0].rxcui == "RXCUI:214618"


def test_an_unmappable_candidate_keeps_its_own_code():
    match, ing = _fake([Candidate(rxcui="RXCUI:999", display_name="x", score=1.0)], {})
    assert [c.rxcui for c in match_ingredients("x", match_fn=match, ingredient_fn=ing)] == ["RXCUI:999"]


def test_a_failed_ingredient_lookup_keeps_the_candidate_rather_than_dropping_it():
    def boom(rxcui):
        raise httpx.ConnectError("down")
    match = lambda term, max_entries=20: [Candidate(rxcui="RXCUI:316256", display_name="m", score=1.0)]  # noqa: E731
    assert [c.rxcui for c in match_ingredients("m", match_fn=match, ingredient_fn=boom)] == ["RXCUI:316256"]
