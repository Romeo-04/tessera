"""Spoken questions: audio in, the words out, nothing else.

No model on Token Factory accepts audio (checked live, 2026-10-04), so the
transcriber is a pluggable dependency of the API (`Deps.transcribe_fn`) and
none is wired by default: /health reports `voice: false` and the app hides the
mic. Whatever fills it later must return only the words; the device shows them
to the caregiver to correct, and the device's deterministic guardrail - not a
model - decides whether the question is answered.
"""
from __future__ import annotations


def audio_kind(head: bytes) -> str | None:
    """MIME type from magic bytes. Phones record m4a; browsers record webm."""
    if len(head) >= 12 and head[4:8] == b"ftyp":
        # 3GP shares the ISO container but usually carries narrowband AMR;
        # labelling it mp4 would hand a transcriber the wrong codec.
        return "audio/3gpp" if head[8:11] == b"3gp" else "audio/mp4"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "audio/webm"
    if head.startswith(b"RIFF") and head[8:12] == b"WAVE":
        return "audio/wav"
    if head.startswith(b"OggS"):
        return "audio/ogg"
    return None
