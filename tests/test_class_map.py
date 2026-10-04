from scripts.class_map import CLASS_MAP, match_class


def test_label_wordings_map_to_their_class():
    assert match_class("angiotensin converting enzyme inhibitors") == "ace-inhibitors"
    assert match_class("ACE inhibitors") == "ace-inhibitors"
    assert match_class("antidiabetic medicines (insulins, oral hypoglycemic agents)") == "antidiabetics"
    assert match_class("Potassium-sparing diuretics") == "potassium-sparing-diuretics"
    assert match_class("NSAIDs") == "nsaids"
    assert match_class("non-steroidal anti-inflammatory drugs") == "nsaids"


def test_the_most_specific_class_wins():
    """'thiazide diuretics' must not be read as every diuretic."""
    assert match_class("thiazide-type diuretics") == "thiazide-diuretics"
    assert match_class("loop diuretics") == "loop-diuretics"
    assert match_class("diuretics") == "diuretics"


def test_an_unknown_class_matches_nothing():
    assert match_class("drugs that prolong the QT interval") is None
    assert match_class("") is None


def test_inducers_are_not_read_as_inhibitors():
    assert match_class("CYP3A4 inducers") == "cyp3a4-inducers"


def test_every_class_has_a_key_and_patterns():
    for entry in CLASS_MAP:
        assert entry["key"] and entry["patterns"], entry


def test_cyp3a4_strength_is_read_from_the_label_wording():
    assert match_class("strong CYP3A4 inhibitors") == "cyp3a4-strong-inhibitors"
    assert match_class("moderate CYP3A inhibitors") == "cyp3a4-moderate-inhibitors"
    # "strong or moderate" is both, so the general class - not the first word.
    assert match_class("strong or moderate CYP3A4 inhibitors") == "cyp3a4-inhibitors"
    assert match_class("inhibitors of CYP3A4") == "cyp3a4-inhibitors"
    assert match_class("strong CYP3A4 inducers") == "cyp3a4-strong-inducers"


def test_every_entry_lists_members_one_way():
    for entry in CLASS_MAP:
        assert bool(entry.get("rxclass")) != bool(entry.get("ingredients")), entry["key"]


def test_wordings_seen_in_the_corpus_map_to_their_class():
    """Each line is a phrase the extraction actually returned from a label."""
    cases = {
        "calcium channel blocking drugs": "calcium-channel-blockers",
        "angiotensin II receptor blocking agents": "arbs",
        "insulin secretagogues or insulin": "insulin-secretagogues",
        "digitalis glycosides": "digitalis",
        "thyroid products": "thyroid",
        "selective cyclooxygenase-2 inhibitors (COX-2 inhibitors)": "cox2-inhibitors",
        "salicylates": "salicylates",
        "dual inhibition of the renin-angiotensin system": "ras-inhibitors",
        "agents that affect the RAS": "ras-inhibitors",
        "carbonic anhydrase inhibitors": "carbonic-anhydrase-inhibitors",
        "tricyclic antidepressants": "tricyclics",
        "certain phenothiazines": "phenothiazines",
        "azole antifungals": "azole-antifungals",
        "protease inhibitors": "hiv-protease-inhibitors",
        "coumarins": "coumarins",
        "fibrates": "fibrates",
    }
    for phrase, key in cases.items():
        assert match_class(phrase) == key, phrase


def test_vague_wordings_stay_unmapped():
    for phrase in ["sympathomimetics", "drugs that reduce metformin clearance",
                   "drugs affecting glycemic control", "neprilysin inhibitor"]:
        assert match_class(phrase) is None, phrase
