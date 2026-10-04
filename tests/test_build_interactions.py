import json

from scripts.build_interactions import assertions_from, build_table, extract_assertions, extract_raw
from tessera.errors import UpstreamError
from tessera.schemas import InteractionAssertion

FORMULARY = {
    "RXCUI:11289": "warfarin",
    "RXCUI:1191": "aspirin",
    "RXCUI:860975": "metformin",
}


class StubRouter:
    def __init__(self, payload):
        self.payload = payload
        self.seen_tier = None

    def complete(self, tier, messages, **kw):
        self.seen_tier = tier
        return json.dumps(self.payload)


def test_named_drugs_become_assertions_against_the_subject():
    router = StubRouter({"interactions": [{"drug": "aspirin", "severity": "warning"}]})
    out = extract_assertions(
        "Concomitant aspirin increases bleeding risk.",
        "RXCUI:11289", "span-1", FORMULARY, router,
    )
    assert len(out) == 1
    assert out[0].subject_rxcui == "RXCUI:11289"
    assert out[0].object_rxcui == "RXCUI:1191"
    assert out[0].severity == "warning"
    assert out[0].span_id == "span-1"


def test_drugs_outside_the_formulary_are_ignored():
    router = StubRouter(
        {"interactions": [{"drug": "phenprocoumon", "severity": "warning"}]}
    )
    assert extract_assertions("text", "RXCUI:11289", "s", FORMULARY, router) == []


def test_section_with_no_interactions_yields_nothing():
    """Silence in the label must never become a fabricated assertion."""
    router = StubRouter({"interactions": []})
    assert extract_assertions(
        "No known interactions.", "RXCUI:11289", "s", FORMULARY, router
    ) == []


def test_unparseable_model_output_is_not_checked_rather_than_empty():
    """An unreadable verdict is not "this label names no interactions" -
    reported as empty, it would be a silent gap in the safety table."""
    class Broken:
        def complete(self, tier, messages, **kw):
            return "not json at all"

    assert extract_assertions("text", "RXCUI:11289", "s", FORMULARY, Broken()) is None


def test_a_drug_cannot_interact_with_itself():
    router = StubRouter({"interactions": [{"drug": "warfarin", "severity": "warning"}]})
    assert extract_assertions("text", "RXCUI:11289", "s", FORMULARY, router) == []


def test_invalid_severity_grade_is_discarded():
    router = StubRouter({"interactions": [{"drug": "aspirin", "severity": "deadly"}]})
    assert extract_assertions("text", "RXCUI:11289", "s", FORMULARY, router) == []


def test_the_same_pair_is_not_asserted_twice_from_one_span():
    router = StubRouter({"interactions": [
        {"drug": "aspirin", "severity": "warning"},
        {"drug": "Aspirin", "severity": "monitor"},
    ]})
    out = extract_assertions("text", "RXCUI:11289", "s", FORMULARY, router)
    assert len(out) == 1


def test_the_prompt_names_the_subject_drug_not_its_code():
    """I11: asking which drugs interact with "RXCUI:11289" while also saying
    "do not infer" gives the model no way to answer well."""
    seen = {}

    class Capturing:
        def complete(self, tier, messages, **kw):
            seen["prompt"] = messages[0]["content"]
            return json.dumps({"interactions": []})

    extract_assertions("some label text", "RXCUI:11289", "s", FORMULARY, Capturing())
    assert "warfarin" in seen["prompt"].lower()
    assert "RXCUI:11289" not in seen["prompt"]


def test_a_salt_or_brand_qualified_name_still_matches_its_ingredient():
    """I12: labels say "warfarin sodium" and "aspirin 81 mg", not the bare
    ingredient. Exact lowercase matching drops nearly all of them."""
    router = StubRouter({"interactions": [
        {"drug": "aspirin 81 mg", "severity": "warning"},
    ]})
    out = extract_assertions("text", "RXCUI:11289", "s", FORMULARY, router)
    assert len(out) == 1
    assert out[0].object_rxcui == "RXCUI:1191"


def test_matching_is_on_whole_words_so_unrelated_drugs_do_not_collide():
    router = StubRouter({"interactions": [
        {"drug": "metformin-containing products", "severity": "monitor"},
    ]})
    out = extract_assertions("text", "RXCUI:11289", "s", FORMULARY, router)
    assert len(out) == 1
    assert out[0].object_rxcui == "RXCUI:860975"


def test_a_drug_class_rather_than_an_ingredient_is_still_ignored():
    """"CYP3A4 inhibitors" names no drug we can resolve; dropping it is right."""
    router = StubRouter({"interactions": [
        {"drug": "CYP3A4 inhibitors", "severity": "warning"},
    ]})
    assert extract_assertions("text", "RXCUI:11289", "s", FORMULARY, router) == []


# ---- drug classes -------------------------------------------------------------

BY_NAME = {name.lower(): rxcui for rxcui, name in FORMULARY.items()}
MEMBERS = {"antidiabetics": ["RXCUI:860975"], "nsaids": ["RXCUI:1191", "RXCUI:11289"]}


def test_the_raw_read_keeps_classes_as_the_label_wrote_them():
    router = StubRouter({"interactions": [{"drug": "aspirin", "severity": "warning"}],
                         "classes": [{"class": "antidiabetic agents", "severity": "monitor"}]})
    raw = extract_raw("text", "warfarin", router)
    assert raw["classes"] == [{"class": "antidiabetic agents", "severity": "monitor"}]
    assert raw["interactions"] == [{"drug": "aspirin", "severity": "warning"}]


def test_an_unreadable_raw_read_is_none():
    class Broken:
        def complete(self, tier, messages, **kw):
            return "[1, 2"
    assert extract_raw("text", "warfarin", Broken()) is None


def test_the_prompt_asks_for_classes_separately_from_named_drugs():
    seen = {}

    class Capturing:
        def complete(self, tier, messages, **kw):
            seen["prompt"] = messages[0]["content"]
            return json.dumps({"interactions": [], "classes": []})

    extract_raw("text", "warfarin", Capturing())
    assert '"classes"' in seen["prompt"]


def test_a_class_expands_to_its_formulary_members_and_says_so():
    raw = {"interactions": [], "classes": [{"class": "antidiabetic agents", "severity": "monitor"}]}
    out = assertions_from(raw, "RXCUI:11289", "s", BY_NAME, MEMBERS)
    assert [(a.object_rxcui, a.severity, a.via_class) for a in out] == [
        ("RXCUI:860975", "monitor", "antidiabetic agents")]


def test_a_named_drug_is_not_marked_as_a_class_member():
    raw = {"interactions": [{"drug": "aspirin", "severity": "warning"}], "classes": []}
    (a,) = assertions_from(raw, "RXCUI:11289", "s", BY_NAME, MEMBERS)
    assert a.via_class is None


def test_a_named_drug_beats_the_same_drug_reached_through_its_class():
    """When the label names aspirin and also warns about NSAIDs, the citation
    should rest on the name, not the inference from its class."""
    raw = {"interactions": [{"drug": "aspirin", "severity": "monitor"}],
           "classes": [{"class": "NSAIDs", "severity": "monitor"}]}
    out = assertions_from(raw, "RXCUI:11289", "s", BY_NAME, MEMBERS)
    assert [(a.object_rxcui, a.via_class) for a in out] == [("RXCUI:1191", None)]


def test_a_class_never_makes_the_subject_interact_with_itself():
    raw = {"interactions": [], "classes": [{"class": "NSAIDs", "severity": "warning"}]}
    out = assertions_from(raw, "RXCUI:11289", "s", BY_NAME, MEMBERS)
    assert [a.object_rxcui for a in out] == ["RXCUI:1191"]


def test_an_unmapped_class_or_bad_grade_yields_nothing():
    raw = {"interactions": [], "classes": [
        {"class": "drugs that prolong the QT interval", "severity": "warning"},
        {"class": "NSAIDs", "severity": "deadly"},
        "not even an object",
    ]}
    assert assertions_from(raw, "RXCUI:11289", "s", BY_NAME, MEMBERS) == []


def test_without_class_members_only_named_drugs_count():
    raw = {"interactions": [{"drug": "aspirin", "severity": "warning"}],
           "classes": [{"class": "antidiabetic agents", "severity": "monitor"}]}
    out = assertions_from(raw, "RXCUI:11289", "s", BY_NAME, {})
    assert [a.object_rxcui for a in out] == ["RXCUI:1191"]


# ---- the build loop -----------------------------------------------------------

def test_build_collects_results_and_lists_failed_spans(tmp_path):
    def extract(job):
        return None if job == "bad" else {"job": job}
    done, failed = build_table(["s1", "bad", "s2"], extract, tmp_path / "p.jsonl", sleep=lambda s: None)
    assert done == {"s1": {"job": "s1"}, "s2": {"job": "s2"}}
    assert failed == ["bad"]


def test_an_upstream_error_is_retried_then_recorded_not_fatal(tmp_path):
    calls = {"n": 0}

    def extract(job):
        if job == "flaky":
            calls["n"] += 1
            if calls["n"] < 2:
                raise UpstreamError("blip")
            return {"ok": True}
        raise UpstreamError("down")

    done, failed = build_table(["flaky", "dead"], extract, tmp_path / "p.jsonl", sleep=lambda s: None)
    assert list(done) == ["flaky"]
    assert failed == ["dead"]


def test_a_rerun_resumes_and_does_not_repeat_finished_spans(tmp_path):
    progress = tmp_path / "p.jsonl"
    seen = []

    def extract(job):
        seen.append(job)
        return {"job": job}

    build_table(["s1", "s2"], extract, progress, sleep=lambda s: None)
    seen.clear()
    done, failed = build_table(["s1", "s2", "s3"], extract, progress, sleep=lambda s: None)
    assert seen == ["s3"]
    assert sorted(done) == ["s1", "s2", "s3"]


def test_a_failed_span_is_retried_on_the_next_run(tmp_path):
    progress = tmp_path / "p.jsonl"
    build_table(["s1"], lambda j: None, progress, sleep=lambda s: None)
    done, failed = build_table(["s1"], lambda j: {"ok": 1}, progress, sleep=lambda s: None)
    assert list(done) == ["s1"] and failed == []


def test_an_empty_model_reply_is_unreadable_not_a_crash():
    """Seen live: one of 922 calls came back with no content at all."""
    class Empty:
        def complete(self, tier, messages, **kw):
            return None
    assert extract_raw("text", "warfarin", Empty()) is None
