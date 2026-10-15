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
