import base64
import json

from tessera.extract import encode_image, extract_drugs
from tessera.router import Tier


class StubRouter:
    def __init__(self, payload):
        self.payload = payload
        self.seen = None

    def complete(self, tier, messages, **kw):
        self.seen = (tier, messages)
        return json.dumps(self.payload)


def _img(tmp_path, name="a.jpg"):
    p = tmp_path / name
    p.write_bytes(b"\xff\xd8\xff\xe0fake")
    return p


def test_extracts_one_record_per_bottle(tmp_path):
    router = StubRouter({"drugs": [
        {"raw_name": "METFORMIN HCL ER", "strength": "500 mg",
         "form": "tablet", "directions": "twice daily"},
        {"raw_name": "LISINOPRIL", "strength": "10 mg",
         "form": "tablet", "directions": "once daily"},
    ]})
    out = extract_drugs([_img(tmp_path)], router)
    assert [d.raw_name for d in out] == ["METFORMIN HCL ER", "LISINOPRIL"]
    assert out[0].strength == "500 mg"


def test_uses_the_omni_tier(tmp_path):
    router = StubRouter({"drugs": []})
    extract_drugs([_img(tmp_path)], router)
    assert router.seen[0] is Tier.OMNI


def test_every_image_is_attached_to_the_single_call(tmp_path):
    """One call for all bottles - the unified multimodal context is the point."""
    router = StubRouter({"drugs": []})
    extract_drugs([_img(tmp_path, "a.jpg"), _img(tmp_path, "b.jpg")], router)
    content = router.seen[1][0]["content"]
    assert sum(1 for c in content if c.get("type") == "image_url") == 2


def test_unreadable_model_output_yields_no_records(tmp_path):
    class Broken:
        def complete(self, tier, messages, **kw):
            return "sorry, I cannot read this image"

    assert extract_drugs([_img(tmp_path)], Broken()) == []


def test_a_record_with_no_name_is_discarded(tmp_path):
    router = StubRouter({"drugs": [
        {"raw_name": "", "strength": "500 mg"},
        {"raw_name": "   ", "strength": "10 mg"},
        {"raw_name": "VALID DRUG"},
    ]})
    out = extract_drugs([_img(tmp_path)], router)
    assert [d.raw_name for d in out] == ["VALID DRUG"]


def test_image_is_encoded_as_a_data_url(tmp_path):
    p = tmp_path / "a.jpg"
    p.write_bytes(b"hello")
    url = encode_image(p)
    assert url.startswith("data:image/jpeg;base64,")
    assert base64.b64decode(url.split(",", 1)[1]) == b"hello"
