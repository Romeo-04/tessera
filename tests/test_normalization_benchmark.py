from evals.normalization_benchmark import (
    brand_case, brand_of, label_text, ocr_noise, outcome, pick_product, summarize,
)


def test_a_product_name_is_written_the_way_a_label_prints_it():
    assert label_text("atorvastatin 20 MG Oral Tablet") == "ATORVASTATIN 20 MG TABLET"
    # RxNorm's "24 HR" prefix and pack quantities are not what a bottle says first.
    assert label_text("24 HR metformin hydrochloride 500 MG Extended Release Oral Tablet") == \
        "METFORMIN HYDROCHLORIDE 500 MG EXTENDED RELEASE TABLET"


def test_the_product_chosen_is_something_that_comes_in_a_pill_bottle():
    names = ["2 ML bumetanide 0.25 MG/ML Injection", "bumetanide 1 MG Oral Tablet",
             "bumetanide 0.5 MG Oral Tablet"]
    assert pick_product(names) == "bumetanide 0.5 MG Oral Tablet"
    assert pick_product(["tiotropium 0.0025 MG/ACTUAT Inhalation Spray"]) is None
    assert pick_product(["amlodipine 5 MG / atorvastatin 10 MG Oral Tablet"]) is None


def test_ocr_noise_lands_in_the_drug_name_and_nowhere_else():
    text = "METFORMIN HYDROCHLORIDE 500 MG EXTENDED RELEASE TABLET"
    for seed in range(30):
        out = ocr_noise(text, "metformin", seed=seed)
        assert out == ocr_noise(text, "metformin", seed=seed)
        assert out != text
        assert out.endswith(" HYDROCHLORIDE 500 MG EXTENDED RELEASE TABLET"), out


def test_the_brand_comes_from_a_single_ingredient_branded_product():
    assert brand_of(["atorvastatin 20 MG Oral Tablet [Lipitor]"]) == "Lipitor"
    assert brand_of(["amlodipine 5 MG / atorvastatin 10 MG Oral Tablet [Caduet]"]) is None
    assert brand_of([]) is None


def test_a_brand_case_uses_a_dose_strength_never_a_volume():
    assert brand_case("Lipitor", "ATORVASTATIN 20 MG TABLET") == "LIPITOR 20 MG"
    assert brand_case("Mapap", "ACETAMINOPHEN 100 ML ORAL SOLUTION") is None


def test_outcomes_count_a_wrong_out_of_scope_guess_as_wrong():
    assert outcome("RXCUI:1", "RXCUI:1", True, "metformin", "metformin") == "correct"
    assert outcome(None, "RXCUI:1", True, "metformin", "metformin") == "asked"
    assert outcome("RXCUI:2", "RXCUI:1", True, "glipizide", "metformin") == "wrong"
    # Outside the formulary but naming the right drug: honest, if unhelpful.
    assert outcome(None, "RXCUI:1", False, "ursodeoxycholate", "ursodiol") == "out of scope"
    # Outside the formulary and naming a different drug: the user is told the
    # wrong thing, so it is wrong.
    assert outcome(None, "RXCUI:1", False, "bupropion", "tramadol") == "wrong"


def test_summary_reports_wrong_answers_with_an_interval():
    s = summarize(["correct"] * 90 + ["asked"] * 6 + ["out of scope"] * 2 + ["wrong"] * 2)
    assert s["n"] == 100 and s["wrong"] == 2 and s["asked"] == 6 and s["out of scope"] == 2
    assert s["accuracy_when_answered"] == 90 / 92
    assert s["wrong_rate_hi"] > 0.02


def test_a_rerun_skips_cases_already_measured(tmp_path):
    from evals.normalization_benchmark import run_cases
    cases = [{"truth": "RXCUI:1", "truth_name": "a", "kind": "clean", "text": t} for t in ("A", "B", "C")]
    seen = []

    def judge(c):
        seen.append(c["text"])
        return {**c, "outcome": "correct"}

    progress = tmp_path / "p.jsonl"
    run_cases(cases[:2], judge, progress)
    seen.clear()
    out = run_cases(cases, judge, progress)
    assert seen == ["C"] and [r["text"] for r in out] == ["A", "B", "C"]
