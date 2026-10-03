import numpy as np
import pytest

from tessera.corpus.index import EvidenceIndex
from tessera.schemas import EvidenceSpan


def span(i: int) -> EvidenceSpan:
    return EvidenceSpan(
        span_id=f"s{i}",
        setid="set",
        section="Drug Interactions",
        text=f"text {i}",
        source_url="https://example.org/?setid=set",
    )


def test_search_returns_nearest_span_first():
    spans = [span(0), span(1), span(2)]
    vecs = np.array([[1, 0], [0, 1], [0.9, 0.1]], dtype="float32")
    idx = EvidenceIndex(spans, vecs)
    hits = idx.search(np.array([1, 0], dtype="float32"), k=2)
    assert hits[0][0].span_id == "s0"
    assert hits[1][0].span_id == "s2"


def test_index_round_trips_through_disk(tmp_path):
    spans = [span(0), span(1)]
    vecs = np.array([[1, 0], [0, 1]], dtype="float32")
    EvidenceIndex(spans, vecs).save(tmp_path)
    loaded = EvidenceIndex.load(tmp_path)
    assert loaded.by_id("s1").text == "text 1"
    assert loaded.search(np.array([0, 1], dtype="float32"), k=1)[0][0].span_id == "s1"


def test_k_larger_than_corpus_does_not_explode():
    idx = EvidenceIndex([span(0)], np.array([[1, 0]], dtype="float32"))
    assert len(idx.search(np.array([1, 0], dtype="float32"), k=25)) == 1


def test_mismatched_spans_and_vectors_is_refused_at_construction():
    with pytest.raises(ValueError):
        EvidenceIndex([span(0), span(1)], np.array([[1, 0]], dtype="float32"))


def test_zero_vector_does_not_produce_nan_scores():
    """A degenerate embedding must not poison the ranking with NaN."""
    idx = EvidenceIndex(
        [span(0), span(1)], np.array([[0, 0], [1, 0]], dtype="float32")
    )
    hits = idx.search(np.array([1, 0], dtype="float32"), k=2)
    assert all(not np.isnan(score) for _, score in hits)
    assert hits[0][0].span_id == "s1"


def test_an_unknown_span_id_raises_a_typed_error_not_a_keyerror():
    """Span IDs hash the span text, so a corpus rebuild after a label revision
    invalidates a frozen interaction table. That must surface as a Tessera
    error mid-session, not a bare KeyError."""
    from tessera.errors import EvidenceMissing

    idx = EvidenceIndex([span(0)], np.array([[1, 0]], dtype="float32"))
    with pytest.raises(EvidenceMissing):
        idx.by_id("span-that-no-longer-exists")
