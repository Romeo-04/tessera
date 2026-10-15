from scripts.build_formulary import resolve
from tessera.schemas import Candidate


def test_a_seed_resolves_to_its_ingredient_not_a_product():
    """data/formulary.csv held RXCUI:858747 for ursodiol - "ursodiol 300 MG Oral
    Capsule", a product - so no ursodiol label could ever be matched to it."""
    match = lambda term, max_entries=5: [  # noqa: E731
        Candidate(rxcui="RXCUI:858747", display_name="ursodiol 300 MG Oral Capsule", score=1.0)]
    ing = lambda rxcui: (("RXCUI:62427", "ursodeoxycholate"),)  # noqa: E731
    best = resolve("ursodiol", match_fn=match, ingredient_fn=ing)
    assert best.rxcui == "RXCUI:62427"


def test_a_seed_whose_ingredient_cannot_be_confirmed_is_unresolved_not_a_product():
    """Review: match_ingredients keeps a product code when the ingredient lookup
    fails or the product is a combination. The builder must not store either."""
    import httpx
    import pytest
    match = lambda term, max_entries=5: [  # noqa: E731
        Candidate(rxcui="RXCUI:858747", display_name="ursodiol 300 MG Oral Capsule", score=1.0)]

    def down(rxcui):
        raise httpx.ConnectError("blip")
    with pytest.raises(httpx.HTTPError):
        resolve("ursodiol", match_fn=match, ingredient_fn=down)

    combo = lambda rxcui: (("RXCUI:1", "a"), ("RXCUI:2", "b"))  # noqa: E731
    assert resolve("a-b", match_fn=match, ingredient_fn=combo) is None
