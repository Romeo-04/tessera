from tessera.transcribe import audio_kind


M4A = b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 32
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 32
WAV = b"RIFF\x00\x00\x00\x00WAVEfmt " + b"\x00" * 32


def test_recognises_the_formats_phones_and_browsers_record():
    assert audio_kind(M4A) == "audio/mp4"
    assert audio_kind(WEBM) == "audio/webm"
    assert audio_kind(WAV) == "audio/wav"
    assert audio_kind(b"%PDF-1.7") is None


def test_a_3gp_recording_is_not_mislabelled_as_mp4():
    three_gp = b"\x00\x00\x00\x18ftyp3gp4" + b"\x00" * 32
    assert audio_kind(three_gp) == "audio/3gpp"
