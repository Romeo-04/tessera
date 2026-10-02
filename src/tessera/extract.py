from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path

from tessera.router import Tier
from tessera.schemas import DrugRecord

PROMPT = """These photographs show prescription medication bottles.

For EVERY distinct bottle or label you can see, read off exactly what is
printed. Do not guess, do not complete partial words, and do not add drugs
you cannot actually see. If a field is unreadable, use null.

Return strict JSON only:
{"drugs": [{"raw_name": "...", "strength": "...", "form": "...",
            "directions": "..."}]}
"""


def encode_image(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    data = base64.b64encode(Path(path).read_bytes()).decode()
    return f"data:{mime};base64,{data}"


def extract_drugs(image_paths: list[Path], router) -> list[DrugRecord]:
    """Read every visible label in one Omni call.

    All photographs go into a single request rather than one call per image:
    Omni keeps a unified multimodal context, so it can tell that two shots of
    the same bottle are one drug. Calling per image would lose that and double
    the cost.

    The same model handles the spoken question elsewhere in the product. That
    collapse - one model for OCR and speech - is why the device side needs no
    second vendor, and it is what makes the privacy split possible at all.
    """
    content: list[dict] = [{"type": "text", "text": PROMPT}]
    for p in image_paths:
        content.append({"type": "image_url", "image_url": {"url": encode_image(p)}})

    raw = router.complete(
        Tier.OMNI,
        [{"role": "user", "content": content}],
        response_format={"type": "json_object"},
    )
    try:
        items = json.loads(raw).get("drugs", [])
    except (json.JSONDecodeError, AttributeError, TypeError):
        return []
    if not isinstance(items, list):
        return []

    out: list[DrugRecord] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = (item.get("raw_name") or "").strip()
        if not name:
            continue
        out.append(
            DrugRecord(
                raw_name=name,
                strength=item.get("strength"),
                form=item.get("form"),
                directions=item.get("directions"),
            )
        )
    return out
