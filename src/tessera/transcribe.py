"""Spoken questions: audio in, the words out, nothing else.

Omni is the same model that reads the labels, so the spoken question needs no
second speech vendor. It is asked only to transcribe. The transcript goes back
to the device, where the caregiver can see and correct it, and the device's
deterministic guardrail - not a model - decides whether it is answered.
"""
from __future__ import annotations

import base64
from pathlib import Path

from tessera.router import Tier

# A spoken question is a sentence or two. Anything longer is not a question
# and is not passed on whole.
MAX_CHARS = 500

PROMPT = (
    "Transcribe exactly what is said in this recording, in the speaker's own "
    "words. Do not answer the question, add anything, or correct the speaker. "
    "Return only the transcript. If nothing intelligible is said, return nothing."
)


def audio_kind(head: bytes) -> str | None:
    """MIME type from magic bytes. Phones record m4a; browsers record webm."""
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return "audio/mp4"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "audio/webm"
    if head.startswith(b"RIFF") and head[8:12] == b"WAVE":
        return "audio/wav"
    if head.startswith(b"OggS"):
        return "audio/ogg"
    return None


def _audio_part(data: bytes, mime: str) -> dict:
    # UNVERIFIED against Token Factory: no key has been available. This is the
    # vLLM multimodal convention (a data URI under "audio_url"). If the live
    # endpoint expects OpenAI's "input_audio" shape instead, this is the only
    # line that changes.
    return {"type": "audio_url",
            "audio_url": {"url": f"data:{mime};base64,{base64.b64encode(data).decode()}"}}


def transcribe(path: Path, mime: str, router) -> str:
    raw = router.complete(
        Tier.OMNI,
        [{"role": "user", "content": [{"type": "text", "text": PROMPT},
                                      _audio_part(Path(path).read_bytes(), mime)]}],
    )
    return (raw or "").strip()[:MAX_CHARS]
