from tessera.router import Tier
from tessera.transcribe import MAX_CHARS, audio_kind, transcribe


class FakeRouter:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def complete(self, tier, messages, **kw):
        self.calls.append((tier, messages))
        return self.reply


M4A = b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 32
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 32
WAV = b"RIFF\x00\x00\x00\x00WAVEfmt " + b"\x00" * 32


def test_recognises_the_formats_phones_and_browsers_record():
    assert audio_kind(M4A) == "audio/mp4"
    assert audio_kind(WEBM) == "audio/webm"
    assert audio_kind(WAV) == "audio/wav"
    assert audio_kind(b"%PDF-1.7") is None


def test_transcription_runs_on_omni_and_returns_only_the_words(tmp_path):
    clip = tmp_path / "q.m4a"
    clip.write_bytes(M4A)
    router = FakeRouter("  Can he take the water pill with the blood pressure one?  ")
    text = transcribe(clip, "audio/mp4", router)
    assert text == "Can he take the water pill with the blood pressure one?"
    assert router.calls[0][0] is Tier.OMNI


def test_the_prompt_asks_for_a_verbatim_transcript_not_an_answer(tmp_path):
    clip = tmp_path / "q.m4a"
    clip.write_bytes(M4A)
    router = FakeRouter("x")
    transcribe(clip, "audio/mp4", router)
    prompt = router.calls[0][1][0]["content"][0]["text"].lower()
    assert "transcribe" in prompt and "do not answer" in prompt


def test_a_runaway_transcript_is_cut_rather_than_trusted(tmp_path):
    clip = tmp_path / "q.m4a"
    clip.write_bytes(M4A)
    assert len(transcribe(clip, "audio/mp4", FakeRouter("a" * 5000))) == MAX_CHARS


def test_nothing_intelligible_is_an_empty_string(tmp_path):
    clip = tmp_path / "q.m4a"
    clip.write_bytes(M4A)
    assert transcribe(clip, "audio/mp4", FakeRouter(None)) == ""


def test_a_3gp_recording_is_not_mislabelled_as_mp4():
    three_gp = b"\x00\x00\x00\x18ftyp3gp4" + b"\x00" * 32
    assert audio_kind(three_gp) == "audio/3gpp"
