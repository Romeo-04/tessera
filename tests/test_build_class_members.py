import pytest

from scripts.build_class_members import members_by_class

ENTRIES = [
    {"key": "ace-inhibitors", "patterns": ["x"], "rxclass": [("ACE Inhibitor", "EPC")]},
    {"key": "k-sparing", "patterns": ["x"],
     "rxclass": [("Potassium-sparing Diuretic", "EPC"), ("Aldosterone Antagonist", "EPC")]},
]
CLASS_IDS = {("ACE Inhibitor", "EPC"): "N1", ("Potassium-sparing Diuretic", "EPC"): "N2",
             ("Aldosterone Antagonist", "EPC"): "N3"}
MEMBERS = {"N1": ["1546022", "999"], "N2": ["111"], "N3": ["222"]}
INGREDIENT = {"1546022": ["RXCUI:29046"], "999": ["RXCUI:999"], "111": ["RXCUI:620"],
              "222": ["RXCUI:9997"]}
FORMULARY = {"lisinopril": "RXCUI:29046", "amiloride": "RXCUI:620",
             "spironolactone": "RXCUI:9997", "rifampin": "RXCUI:9384"}


def _run(class_ids=CLASS_IDS, entries=ENTRIES):
    return members_by_class(
        entries,
        find_class=lambda name, ctype: class_ids.get((name, ctype)),
        class_members=lambda class_id, ctype: MEMBERS[class_id],
        ingredients=lambda rxcui: INGREDIENT.get(rxcui, []),
        formulary=FORMULARY,
    )


def test_members_are_mapped_to_formulary_ingredient_codes():
    """RxClass lists "lisinopril anhydrous"; the formulary keys lisinopril."""
    assert _run()["ace-inhibitors"] == ["RXCUI:29046"]


def test_a_class_built_from_several_rxclass_classes_is_their_union():
    assert _run()["k-sparing"] == ["RXCUI:620", "RXCUI:9997"]


def test_a_class_name_rxclass_no_longer_knows_fails_loudly():
    with pytest.raises(SystemExit, match="Aldosterone Antagonist"):
        _run({k: v for k, v in CLASS_IDS.items() if k[0] != "Aldosterone Antagonist"})


def test_a_named_list_is_used_as_written_and_unknown_names_are_reported():
    entries = [{"key": "inducers", "patterns": ["x"], "ingredients": ["rifampin", "mitotane"]}]
    missing = []
    out = members_by_class(entries, find_class=None, class_members=None, ingredients=None,
                           formulary=FORMULARY, not_carried=missing.append)
    assert out["inducers"] == ["RXCUI:9384"]
    assert missing == ["mitotane"]


def test_an_excluded_ingredient_is_dropped_from_the_rxclass_members():
    entries = [dict(ENTRIES[1], exclude=["amiloride"])]
    assert _run(entries=entries)["k-sparing"] == ["RXCUI:9997"]
