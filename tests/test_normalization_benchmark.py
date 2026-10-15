from evals.normalization_benchmark import brand_of, label_text, ocr_noise, outcome, summarize


def test_a_product_name_is_written_the_way_a_label_prints_it():
    assert label_text("atorvastatin 20 MG Oral Tablet") == "ATORVASTATIN 20 MG TABLET"
    assert label_text("metformin hydrochloride 500 MG Extended Release Oral Tablet") == \
        "METFORMIN HYDROCHLORIDE 500 MG EXTENDED RELEASE TABLET"


def test_ocr_noise_is_deterministic_and_changes_the_name_not_the_strength():
    a = ocr_noise("LISINOPRIL 10 MG TABLET", seed=3)
    assert a == ocr_noise("LISINOPRIL 10 MG TABLET", seed=3)
    assert a != "LISINOPRIL 10 MG TABLET"
    assert a.endswith("10 MG TABLET")


def test_the_brand_comes_from_a_single_ingredient_branded_product():
    assert brand_of(["atorvastatin 20 MG Oral Tablet [Lipitor]"]) == "Lipitor"
    assert brand_of(["amlodipine 5 MG / atorvastatin 10 MG Oral Tablet [Caduet]"]) is None
    assert brand_of([]) is None


def test_outcomes_separate_the_dangerous_error_from_an_honest_abstention():
    assert outcome("RXCUI:1", "RXCUI:1") == "correct"
    assert outcome(None, "RXCUI:1") == "abstained"
    assert outcome("RXCUI:2", "RXCUI:1") == "wrong"


def test_summary_reports_wrong_answers_with_an_interval():
    s = summarize(["correct"] * 90 + ["abstained"] * 8 + ["wrong"] * 2)
    assert s["n"] == 100 and s["wrong"] == 2 and s["abstained"] == 8
    assert s["accuracy_when_answered"] == 90 / 92
    assert s["wrong_rate_hi"] > 0.02          # 2/100 is not "2% exactly"
