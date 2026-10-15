from evals.metrics import ablation_table, citation_support_rate, precision_at_k, top1_accuracy
from tessera.telemetry import CallRecord


def test_abstentions_are_not_counted_as_correct_or_wrong():
    gold = {"a": "RXCUI:1", "b": "RXCUI:2", "c": "RXCUI:3", "d": "RXCUI:4"}
    preds = {"a": "RXCUI:1", "b": "RXCUI:9", "c": None, "d": "RXCUI:4"}
    m = top1_accuracy(preds, gold)
    assert m["n"] == 4
    assert m["abstained"] == 1
    assert m["coverage"] == 0.75
    assert abs(m["accuracy_when_answered"] - 2 / 3) < 1e-9
    assert m["accuracy_overall"] == 0.5


def test_a_missing_prediction_counts_as_an_abstention():
    m = top1_accuracy({}, {"a": "RXCUI:1"})
    assert m["abstained"] == 1
    assert m["accuracy_when_answered"] is None


def test_precision_at_5_treats_pairs_as_unordered():
    ranked = [("A", "B"), ("C", "D"), ("E", "F")]
    relevant = {("B", "A"), ("E", "F")}
    assert abs(precision_at_k(ranked, relevant, k=5) - 2 / 3) < 1e-9


def test_precision_only_looks_at_the_top_k():
    ranked = [("X", "Y")] * 5 + [("A", "B")]
    assert precision_at_k(ranked, {("A", "B")}, k=5) == 0.0


def test_precision_of_an_empty_ranking_is_undefined_not_perfect():
    assert precision_at_k([], {("A", "B")}) is None


def test_citation_support_rate():
    assert citation_support_rate([True, True, False, True]) == 0.75
    assert citation_support_rate([]) is None


def test_ablation_table_reports_each_tier_with_its_cost():
    calls = [
        CallRecord("DEEP", "ultra", 1000, 200, 900.0, 0.0016),
        CallRecord("DEEP", "ultra", 1000, 200, 1100.0, 0.0016),
        CallRecord("CHEAP", "lightning", 500, 50, 100.0, 0.00004),
    ]
    table = ablation_table(calls)
    deep = next(line for line in table.splitlines() if line.startswith("| DEEP"))
    assert "| 2 |" in deep
    assert "1000" in deep  # mean latency, ms
    assert "$0.0032" in deep
    assert table.splitlines()[0].startswith("| Tier")


# ---- live session summary ------------------------------------------------------

from evals.metrics import session_summary


def test_session_summary_reports_median_and_worst_not_just_mean():
    sessions = [{"cost_usd": c, "latency_s": l, "shown": 2, "withheld": 0, "status": "ok"}
                for c, l in [(0.01, 4.0), (0.02, 6.0), (0.09, 30.0)]]
    s = session_summary(sessions)
    assert s["n"] == 3
    assert s["cost_median"] == 0.02 and s["cost_max"] == 0.09
    assert s["latency_median"] == 6.0 and s["latency_max"] == 30.0


def test_session_summary_counts_the_verifier_withholding_sentences():
    sessions = [{"cost_usd": 0.01, "latency_s": 1.0, "shown": 3, "withheld": 1, "status": "ok"},
                {"cost_usd": 0.01, "latency_s": 1.0, "shown": 4, "withheld": 0, "status": "analysis_incomplete"}]
    s = session_summary(sessions)
    assert s["sentences_written"] == 8 and s["sentences_withheld"] == 1
    assert s["statuses"] == {"ok": 1, "analysis_incomplete": 1}


def test_no_sessions_is_not_a_number():
    assert session_summary([])["n"] == 0
    assert session_summary([])["cost_median"] is None
