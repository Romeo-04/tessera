from scripts.review_sheet import review_flags

NAMES = {"RXCUI:29046": "lisinopril", "RXCUI:9997": "spironolactone", "RXCUI:4603": "furosemide"}
DEMO = {"RXCUI:29046", "RXCUI:4603"}


def row(subject, obj, severity="warning"):
    return {"subject_rxcui": subject, "object_rxcui": obj, "severity": severity, "span_id": "s"}


def test_a_passage_that_names_the_other_drug_is_not_flagged_for_naming():
    text = "Potassium-sparing diuretics (spironolactone, amiloride) can increase the risk of hyperkalemia."
    assert "object not named in passage" not in review_flags(row("RXCUI:29046", "RXCUI:9997"), text, NAMES, set())


def test_a_pair_the_passage_never_names_is_flagged():
    """The builder's likeliest error: a drug inferred from a class the label names."""
    text = "Diuretics: excessive drop in blood pressure."
    assert "object not named in passage" in review_flags(row("RXCUI:29046", "RXCUI:4603"), text, NAMES, set())


def test_naming_is_case_insensitive_and_whole_word():
    assert "object not named in passage" not in review_flags(
        row("RXCUI:29046", "RXCUI:4603"), "FUROSEMIDE may potentiate...", NAMES, set())
    assert "object not named in passage" in review_flags(
        row("RXCUI:29046", "RXCUI:4603"), "furosemidex is not a drug", NAMES, set())


def test_every_contraindicated_row_is_flagged():
    flags = review_flags(row("RXCUI:29046", "RXCUI:9997", "contraindicated"), "spironolactone", NAMES, set())
    assert "contraindicated: always reviewed" in flags


def test_rows_touching_a_demo_drug_are_flagged():
    flags = review_flags(row("RXCUI:29046", "RXCUI:9997"), "spironolactone", NAMES, DEMO)
    assert "demo drug" in flags


def test_a_clean_row_has_no_flags():
    assert review_flags(row("RXCUI:9997", "RXCUI:9997"), "spironolactone", NAMES, set()) == []
