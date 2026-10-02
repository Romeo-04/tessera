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
def test_approximate_match_returns_empty_list_when_nothing_matches():
    respx.get(url__startswith=ENDPOINT).mock(
        return_value=httpx.Response(200, json={"approximateGroup": {}})
    )
    assert approximate_match("qqzzxx notadrug") == []
