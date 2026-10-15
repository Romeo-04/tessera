import pytest

from scripts.class_map import CLASS_MAP, excluded_text, match_classes

# Every phrase here is one the extraction returned from a real label.
CASES = {
    # one class, as labels write it
    "angiotensin converting enzyme inhibitors": ["ace-inhibitors"],
    "ACE inhibitor therapy": ["ace-inhibitors"],
    "antidiabetic medicines (insulins, oral hypoglycemic agents)": ["insulins", "antidiabetics"],
    "Potassium-sparing diuretics": ["potassium-sparing-diuretics"],
    "NSAIDs": ["nsaids"],
    "Non-steroidal Anti-inflammatory Drugs": ["nsaids"],
    "calcium channel blocking drugs": ["calcium-channel-blockers"],
    "angiotensin II receptor blocking agents": ["arbs"],
    "digitalis glycosides": ["digitalis"],
    "thyroid products": ["thyroid"],
    "salicylates": ["salicylates"],
    "agents that affect the RAS": ["ras-inhibitors"],
    "carbonic anhydrase inhibitors": ["carbonic-anhydrase-inhibitors"],
    "tricyclic antidepressants (TCAs)": ["tricyclics"],
    "azole antifungals": ["azole-antifungals"],
    "protease inhibitors": ["hiv-protease-inhibitors"],
    "Coumarin anticoagulants": ["coumarins"],
    "Long Acting Barbiturates": ["barbiturates"],
    "other opioids": ["opioids"],

    # a narrower class is not read as its parent ...
    "loop diuretics": ["loop-diuretics"],
    "thiazide-type diuretics": ["thiazide-diuretics"],
    "dihydropyridine calcium channel blockers": ["dihydropyridine-ccbs"],
    "Verapamil- or diltiazem-type calcium channel blockers": ["non-dihydropyridine-ccbs"],
    "calcium channel blockers of the verapamil or diltiazem type": ["non-dihydropyridine-ccbs"],
    "cardioselective beta-blockers": ["cardioselective-beta-blockers"],
    "Non-Steroidal Anti- inflammatory Drugs - Fenamates": ["fenamates"],
    "Mixed Agonist/Antagonist and Partial Agonist Opioid Analgesics": ["partial-agonist-opioids"],
    # ... but a phrase naming a class and its parent means both
    "Thiazides and other diuretics": ["thiazide-diuretics", "diuretics"],

    # negation means the opposite set
    "Non-Potassium-Sparing Diuretics": ["potassium-depleting-diuretics"],
    "non‑potassium‑sparing diuretics": ["potassium-depleting-diuretics"],
    "nonpotassium-sparing diuretics": ["potassium-depleting-diuretics"],
    "potassium-depleting diuretics": ["potassium-depleting-diuretics"],
    "Analgesics, Non-opioid (selective blocker of Na v 1.8 sodium channels)": [],

    # several classes in one phrase: all of them
    "ACE Inhibitors and ARBs": ["ace-inhibitors", "arbs"],
    "Insulin Secretagogues or Insulin": ["insulin-secretagogues", "insulins"],
    "SSRIs/SNRIs": ["ssris", "snris"],
    "selective serotonin and serotonin norepinephrine reuptake inhibitors (SSRIs, SNRIs)": ["ssris", "snris"],
    "SSRIs, Tricyclics and Related Antidepressants": ["tricyclics", "ssris"],
    "CYP3A4 Inhibitors and Inducers": ["cyp3a4-inhibitors", "cyp3a4-inducers"],
    "CYP 3A4 inducers and inhibitors": ["cyp3a4-inhibitors", "cyp3a4-inducers"],

    # CYP3A4 strength comes from the label's own word
    "strong CYP3A4 inhibitors": ["cyp3a4-strong-inhibitors"],
    "Potent CYP3A4 Inhibitors": ["cyp3a4-strong-inhibitors"],
    "potent inhibitor of CYP3A4": ["cyp3a4-strong-inhibitors"],
    "Strong CYP2D6 and CYP3A4 inhibitors": ["cyp3a4-strong-inhibitors"],
    "combined P-gp and strong CYP3A inhibitors": ["cyp3a4-strong-inhibitors"],
    "moderate inhibitors of CYP3A": ["cyp3a4-moderate-inhibitors"],
    "Moderate CYP3A4 Inducers": ["cyp3a4-moderate-inducers"],
    "moderate inducers of CYP3A": ["cyp3a4-moderate-inducers"],
    "strong and moderate CYP3A4 inhibitors": ["cyp3a4-strong-or-moderate-inhibitors"],
    "moderate or strong CYP3A4 inhibitors": ["cyp3a4-strong-or-moderate-inhibitors"],
    "Strong or Moderate Inducers of CYP3A": ["cyp3a4-strong-or-moderate-inducers"],
    "CYP3A4 inhibitors": ["cyp3a4-inhibitors"],
    "Inhibitors of CYP3A4": ["cyp3a4-inhibitors"],
    "any known CYP3A4 inducer": ["cyp3a4-inducers"],

    # a phrase that only resembles a class matches nothing
    "CYP2C8 and CYP3A4 Inducers and Drugs That May Decrease the Blood Glucose Lowering Effect of Repaglinide": ["cyp3a4-inducers"],
    "Aminosalicylates": [],
    "HCV protease inhibitors": [],
    "drugs that prolong the QT interval": [],
    "sympathomimetics": [],
    "drugs that reduce metformin clearance": [],
    "neprilysin inhibitor": [],
    "": [],

    # only part of a class: the label names which ones elsewhere
    "certain phenothiazines": [],
    "select HIV protease inhibitors": [],
    "intravenous beta adrenergic blocking agents": [],

    # the exclusion clause is not searched for classes
    "Fibrates (other than Gemfibrozil)": ["fibrates"],
    "Non-steroidal anti-inflammatory drugs (but not acetyl salicylic acid)": ["nsaids"],
}


@pytest.mark.parametrize("phrase,keys", CASES.items())
def test_label_wording_maps_to_exactly_these_classes(phrase, keys):
    assert match_classes(phrase) == keys


def test_an_exclusion_names_the_drug_left_out():
    assert "gemfibrozil" in excluded_text("Fibrates (other than Gemfibrozil)")
    assert "aspirin" in excluded_text("NSAIDs (but not acetyl salicylic acid)")
    assert excluded_text("NSAIDs") == ""


def test_every_class_has_a_key_and_patterns():
    for entry in CLASS_MAP:
        assert entry["key"] and entry["patterns"], entry


def test_every_entry_lists_members_one_way():
    for entry in CLASS_MAP:
        assert bool(entry.get("rxclass")) != bool(entry.get("ingredients")), entry["key"]


def test_keys_are_unique_and_refinements_point_at_real_keys():
    keys = [e["key"] for e in CLASS_MAP]
    assert len(keys) == len(set(keys))
    for e in CLASS_MAP:
        assert set(e.get("refines", [])) <= set(keys), e["key"]


@pytest.mark.parametrize("phrase", ["non-insulin antidiabetic agents", "insulin sensitizers",
                                    "drugs that increase insulin resistance"])
def test_insulin_named_only_as_a_property_is_not_insulin(phrase):
    assert "insulins" not in match_classes(phrase)


def test_weak_cyp3a4_inhibitors_are_not_read_as_strong_or_moderate():
    assert match_classes("weak CYP3A4 inhibitors") == []
