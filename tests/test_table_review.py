import pytest

from evals.metrics import wilson_interval
from scripts.apply_review import rejections_from, review_precision
from scripts.review_sheet import group_claims, select_for_review

DEMO = {"RXCUI:1", "RXCUI:2"}


def row(subject, obj, severity="warning", span="s", via=""):
    return {"subject_rxcui": subject, "object_rxcui": obj, "severity": severity,
            "span_id": span, "via_class": via}


# ---- one verdict per claim -----------------------------------------------------

def test_a_class_claim_is_one_item_however_many_drugs_it_reached():
    rows = [row("RXCUI:9", f"RXCUI:{i}", via="NSAIDs") for i in range(10, 18)]
    (claim,) = group_claims(rows)
    assert claim["claim"] == "NSAIDs" and len(claim["objects"]) == 8


def test_named_rows_stay_one_claim_each():
    claims = group_claims([row("RXCUI:9", "RXCUI:10"), row("RXCUI:9", "RXCUI:11")])
    assert sorted(c["claim"] for c in claims) == ["RXCUI:10", "RXCUI:11"]


# ---- what a reviewer must see, and the random sample ---------------------------

def _claims(n):
    return group_claims([row("RXCUI:9", f"RXCUI:{100 + i}", span=f"s{i}") for i in range(n)])


def test_every_contraindicated_demo_and_conflicting_claim_must_be_reviewed():
    rows = [row("RXCUI:9", "RXCUI:10", "contraindicated", span="a"),
            row("RXCUI:1", "RXCUI:2", span="b"),
            row("RXCUI:9", "RXCUI:11", span="c"),
            row("RXCUI:9", "RXCUI:12", span="d")]
    must, sample = select_for_review(group_claims(rows), DEMO, {("RXCUI:9", "RXCUI:11", "c")}, n_sample=0)
    assert sorted(c["span_id"] for c in must) == ["a", "b", "c"]
    assert sample == []


def test_the_sample_is_drawn_only_from_claims_not_already_reviewed_and_is_reproducible():
    claims = _claims(50)
    must, s1 = select_for_review(claims, set(), set(), n_sample=10, seed=1)
    _, s2 = select_for_review(claims, set(), set(), n_sample=10, seed=1)
    assert must == [] and len(s1) == 10 and s1 == s2


def test_the_sample_is_split_between_named_and_class_claims():
    rows = ([row("RXCUI:9", f"RXCUI:{100 + i}", span=f"n{i}") for i in range(40)]
            + [row("RXCUI:9", f"RXCUI:{200 + i}", span=f"c{i}", via="NSAIDs") for i in range(40)])
    _, sample = select_for_review(group_claims(rows), set(), set(), n_sample=20, seed=3)
    kinds = [bool(c["via_class"]) for c in sample]
    assert kinds.count(True) == 10 and kinds.count(False) == 10


# ---- turning verdicts into data ------------------------------------------------

def verdict(v, sev="", section="sample", claim="RXCUI:10"):
    return {"section": section, "span_id": "s", "subject_rxcui": "RXCUI:9", "claim": claim,
            "verdict (keep / drop / regrade)": v, "corrected_severity": sev, "note": "n"}


def test_drop_and_regrade_become_rejections_keep_does_not():
    out = rejections_from([verdict("keep"), verdict("drop"), verdict("regrade", "monitor")])
    assert [(r["corrected_severity"]) for r in out] == ["", "monitor"]


def test_a_regrade_without_a_valid_grade_is_refused():
    with pytest.raises(ValueError, match="regrade"):
        rejections_from([verdict("regrade", "deadly")])


def test_an_unknown_verdict_is_refused_rather_than_guessed():
    with pytest.raises(ValueError, match="maybe"):
        rejections_from([verdict("maybe")])


def test_precision_counts_the_sample_only_and_separates_pair_from_grade():
    rows = ([verdict("keep")] * 8 + [verdict("regrade", "monitor")] + [verdict("drop")]
            + [verdict("drop", section="must review")] * 5)
    p = review_precision(rows)
    assert p["n"] == 10
    assert p["pair_correct"] == 9 and p["pair_and_grade_correct"] == 8


def test_unreviewed_sample_rows_are_not_counted():
    p = review_precision([verdict("keep"), verdict("")])
    assert p["n"] == 1 and p["unreviewed"] == 1


# ---- the interval --------------------------------------------------------------

def test_wilson_interval_is_honest_at_the_edges():
    lo, hi = wilson_interval(10, 10)
    assert hi == 1.0 and 0.65 < lo < 0.75      # 10/10 is not "100% accurate"
    lo, hi = wilson_interval(90, 100)
    assert 0.82 < lo < 0.84 and 0.94 < hi < 0.96
    assert wilson_interval(0, 0) == (None, None)


# ---- review findings -----------------------------------------------------------

from scripts.apply_review import table_precision, unmatched
from scripts.build_interactions import claim_key


def test_a_typographic_hyphen_does_not_break_a_rejection():
    assert claim_key("s", "RXCUI:9", "Beta‑blockers ") == claim_key("s", "RXCUI:9", "beta-blockers")


def test_a_claim_written_two_ways_is_one_claim():
    claims = group_claims([row("RXCUI:9", "RXCUI:10", via="NSAIDs"), row("RXCUI:9", "RXCUI:11", via="nsaids ")])
    assert len(claims) == 1 and len(claims[0]["objects"]) == 2


def test_a_claim_with_mixed_grades_must_be_reviewed():
    claims = group_claims([row("RXCUI:9", "RXCUI:10", "monitor", via="NSAIDs"),
                           row("RXCUI:9", "RXCUI:11", "warning", via="NSAIDs")])
    must, _ = select_for_review(claims, set(), set(), n_sample=0)
    assert must and "mixed grades" in must[0]["why"]


def test_table_precision_weights_each_group_by_its_size():
    """Named and class claims are sampled 50/50 but are not 50/50 of the table;
    the must-review group is reviewed in full, so it is known, not estimated."""
    p = table_precision(
        groups={"named": (40, 50), "class": (25, 50), "must review": (250, 262)},
        sizes={"named": 1608, "class": 663, "must review": 262})
    assert round(p["estimate"], 3) == round((1608 * 0.8 + 663 * 0.5 + 250) / 2533, 3)
    assert p["groups"]["named"]["lo"] < 0.8 < p["groups"]["named"]["hi"]


def test_a_verdict_that_matches_no_claim_in_the_table_is_reported():
    claims = {claim_key("s", "RXCUI:9", "NSAIDs")}
    bad = unmatched([{"span_id": "s", "subject_rxcui": "RXCUI:9", "claim": "Beta?blockers"},
                     {"span_id": "s", "subject_rxcui": "RXCUI:9", "claim": "nsaids"}], claims)
    assert [b["claim"] for b in bad] == ["Beta?blockers"]


# ---- re-review findings --------------------------------------------------------

def test_a_verdict_already_applied_is_not_reported_as_unmatched():
    """After a rebuild the dropped claim is gone from the table; re-running
    apply on the same sheet must not stop on the reviewer's own drop."""
    already = {claim_key("s", "RXCUI:9", "NSAIDs")}
    bad = unmatched([{"span_id": "s", "subject_rxcui": "RXCUI:9", "claim": "NSAIDs"}], set(), already)
    assert bad == []


def test_the_table_wide_estimate_waits_until_every_group_is_fully_reviewed():
    sizes = {"named": 1608, "class": 663, "must review": 262}
    partial = table_precision({"named": (40, 50), "class": (25, 50), "must review": (10, 10)}, sizes,
                              expected={"named": 50, "class": 50, "must review": 262})
    assert partial["estimate"] is None
    done = table_precision({"named": (40, 50), "class": (25, 50), "must review": (250, 262)}, sizes,
                           expected={"named": 50, "class": 50, "must review": 262})
    assert done["estimate"] is not None
    assert done["lo"] < done["estimate"] < done["hi"]
