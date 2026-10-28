"""The whole tracer bullet through the single seam: Video in, Sidecar out."""

from __future__ import annotations

import hashlib
import io
import re
import sys
import wave

import numpy as np
import pytest

from subie.cli import run
from subie.exit_codes import EXIT_FAILED, EXIT_OK, EXIT_USAGE
from subie.media import MediaInfo
from subie.transcript import Segment, Transcript
from tests.fakes import (
    CPU_ONLY,
    GPU_READY,
    FakeMediaProbe,
    FakeModelDownloader,
    FakeTranscriber,
    FakeTranscriberFactory,
    make_deps,
    one_segment,
)
from tests.wav import write_wav


def _deps(transcript: Transcript | None = None, **kwargs):
    factory = FakeTranscriberFactory(FakeTranscriber(transcript or one_segment()))
    return make_deps(transcriber_factory=factory, **kwargs), factory


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_a_video_becomes_a_sidecar_and_prints_one_summary_line(tmp_path, capsys):
    video = tmp_path / "talk.wav"
    write_wav(video)
    deps, factory = _deps(one_segment("Hello there."))

    code = run([str(video)], deps)

    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert captured.err == ""
    lines = captured.out.splitlines()
    assert len(lines) == 1
    assert re.fullmatch(r"talk\.wav " + "\u2192" + r" talk\.srt  1 cue  \d+\.\d+s", lines[0])
    sidecar = tmp_path / "talk.srt"
    assert sidecar.exists()
    assert sidecar.read_bytes() == (b"1\r\n00:00:00,000 --> 00:00:01,700\r\nHello there.\r\n")
    assert factory.calls == [("Systran/faster-whisper-small.en", "cpu", "int8")]


def test_the_default_device_is_cpu_and_default_model_is_small_en(tmp_path, capsys):
    video = tmp_path / "talk.wav"
    write_wav(video)
    deps, factory = _deps(hardware=CPU_ONLY)

    assert run([str(video)], deps) == EXIT_OK

    assert factory.calls == [("Systran/faster-whisper-small.en", "cpu", "int8")]


def test_a_working_gpu_uses_turbo_and_float16(tmp_path, capsys):
    video = tmp_path / "talk.wav"
    write_wav(video)
    deps, factory = _deps(hardware=GPU_READY)

    assert run([str(video)], deps) == EXIT_OK

    assert factory.calls == [("mobiuslabsgmbh/faster-whisper-large-v3-turbo", "cuda", "float16")]


def test_model_and_device_flags_override_the_resolved_defaults(tmp_path, capsys):
    video = tmp_path / "talk.wav"
    write_wav(video)
    deps, factory = _deps(hardware=GPU_READY)

    assert run([str(video), "--device", "cpu", "--model", "base.en"], deps) == EXIT_OK

    assert factory.calls == [("Systran/faster-whisper-base.en", "cpu", "int8")]


def test_forcing_cuda_on_a_machine_without_one_fails_clearly_and_starts_no_engine(tmp_path, capsys):
    video = tmp_path / "talk.wav"
    write_wav(video)
    deps, factory = _deps(hardware=CPU_ONLY)

    code = run([str(video), "--device", "cuda"], deps)

    captured = capsys.readouterr()
    assert code == EXIT_FAILED
    assert captured.out == ""
    assert "cuda device is not usable" in captured.err
    assert "Traceback" not in captured.err
    assert factory.calls == []
    assert not (tmp_path / "talk.srt").exists()


def test_an_unknown_model_is_a_usage_error(tmp_path, capsys):
    video = tmp_path / "talk.wav"
    write_wav(video)
    deps, factory = _deps()

    code = run([str(video), "--model", "gigantic"], deps)

    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert "unknown model 'gigantic'" in captured.err
    assert factory.calls == []


def test_the_video_bytes_are_unchanged(tmp_path, capsys):
    video = tmp_path / "talk.wav"
    write_wav(video)
    before = _sha256(video)
    deps, _ = _deps()

    assert run([str(video)], deps) == EXIT_OK

    assert _sha256(video) == before


def test_sidecar_is_valid_srt_with_two_cues(tmp_path, capsys):
    video = tmp_path / "talk.wav"
    write_wav(video, seconds=3.0)
    transcript = Transcript(
        segments=(
            Segment(start=0.0, end=1.5, text=" Hello there. "),
            Segment(start=8.0, end=9.0, text="General Kenobi."),
        )
    )
    deps, _ = _deps(transcript)

    assert run([str(video)], deps) == EXIT_OK

    sidecar = tmp_path / "talk.srt"
    data = sidecar.read_bytes()
    assert not data.startswith(b"\xef\xbb\xbf")
    assert data == (
        b"1\r\n"
        b"00:00:00,000 --> 00:00:01,700\r\n"
        b"Hello there.\r\n"
        b"\r\n"
        b"2\r\n"
        b"00:00:08,000 --> 00:00:09,200\r\n"
        b"General Kenobi.\r\n"
    )
    assert data.decode("utf-8").endswith("\r\n")


def test_no_temporary_audio_file_is_left_behind(tmp_path, capsys):
    video = tmp_path / "talk.wav"
    write_wav(video)
    deps, _ = _deps()

    assert run([str(video)], deps) == EXIT_OK

    assert sorted(path.name for path in tmp_path.iterdir() if path.is_file()) == [
        "talk.srt",
        "talk.wav",
    ]


def test_keep_audio_retains_the_decoded_audio_in_a_predictable_place(tmp_path, capsys):
    video = tmp_path / "talk.wav"
    write_wav(video, seconds=0.5, rate=44_100, channels=2)
    deps, _ = _deps()

    code = run([str(video), "--keep-audio"], deps)

    assert code == EXIT_OK
    kept = tmp_path / "talk.keep-audio.wav"
    assert kept.exists()
    assert sorted(path.name for path in tmp_path.iterdir() if path.is_file()) == [
        "talk.keep-audio.wav",
        "talk.srt",
        "talk.wav",
    ]
    with wave.open(str(kept), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getframerate() == 16_000
        assert wav.getnframes() == 8_000


def test_without_keep_audio_nothing_is_retained(tmp_path, capsys):
    video = tmp_path / "talk.wav"
    write_wav(video)
    deps, _ = _deps()

    assert run([str(video)], deps) == EXIT_OK

    assert not (tmp_path / "talk.keep-audio.wav").exists()


def test_audio_is_decoded_to_16k_mono_float32(tmp_path, capsys):
    video = tmp_path / "music.wav"
    write_wav(video, seconds=0.5, rate=44_100, channels=2)
    deps, factory = _deps()

    assert run([str(video)], deps) == EXIT_OK

    audio = factory.transcriber.seen[0]
    assert audio.sample_rate == 16_000
    assert audio.samples.ndim == 1
    assert audio.samples.dtype == np.float32
    assert audio.duration_s == pytest.approx(0.5, abs=0.01)


def test_a_missing_model_with_no_network_names_the_model_and_cache(tmp_path, capsys, subie_home):
    video = tmp_path / "talk.wav"
    write_wav(video)
    downloader = FakeModelDownloader(
        error=OSError("We couldn't connect to 'https://huggingface.co' to load this file")
    )
    deps = make_deps(hardware=CPU_ONLY, downloader=downloader)

    code = run([str(video)], deps)

    captured = capsys.readouterr()
    assert code == EXIT_FAILED
    assert captured.out == ""
    assert "model 'small.en'" in captured.err
    assert str(subie_home / "models") in captured.err
    assert "not in the cache" in captured.err
    assert "could not be downloaded" in captured.err
    assert "Traceback" not in captured.err
    assert not (tmp_path / "talk.srt").exists()


def test_a_video_path_that_does_not_exist_fails_clearly(tmp_path, capsys):
    missing = tmp_path / "nothing.mp4"
    deps, factory = _deps()

    code = run([str(missing)], deps)

    captured = capsys.readouterr()
    assert code == EXIT_FAILED
    assert captured.out == ""
    assert "video not found" in captured.err
    assert "Traceback" not in captured.err
    assert factory.calls == []


def test_a_video_with_no_audio_stream_fails_clearly(tmp_path, capsys):
    video = tmp_path / "silent.mp4"
    video.write_bytes(b"not really a video")
    deps, factory = _deps(
        media_probe=FakeMediaProbe(info=MediaInfo(duration_s=1.0, has_audio=False))
    )

    code = run([str(video)], deps)

    captured = capsys.readouterr()
    assert code == EXIT_FAILED
    assert "has no audio stream" in captured.err
    assert "Traceback" not in captured.err
    assert factory.calls == []
    assert not (tmp_path / "silent.srt").exists()


def test_a_missing_video_does_not_stop_the_next_video(tmp_path, capsys):
    good = tmp_path / "good.wav"
    write_wav(good)
    deps, _ = _deps()

    code = run([str(tmp_path / "missing.wav"), str(good)], deps)

    captured = capsys.readouterr()
    assert code == EXIT_FAILED
    assert "video not found" in captured.err
    assert "good.wav" in captured.out
    assert (tmp_path / "good.srt").exists()


def test_a_video_with_no_speech_produces_no_empty_sidecar(tmp_path, capsys):
    video = tmp_path / "talk.wav"
    write_wav(video)
    deps, _ = _deps(Transcript(segments=()))

    code = run([str(video)], deps)

    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert "no speech detected" in captured.err
    assert not (tmp_path / "talk.srt").exists()


def test_the_summary_line_survives_a_legacy_windows_console_codepage(tmp_path, monkeypatch):
    """The arrow must not crash a run whose output is redirected on Windows."""
    video = tmp_path / "talk.wav"
    write_wav(video)
    deps, _ = _deps(one_segment("Hello there."))
    out_buffer = io.BytesIO()
    err_buffer = io.BytesIO()
    legacy_stdout = io.TextIOWrapper(out_buffer, encoding="cp1252", newline="")
    legacy_stderr = io.TextIOWrapper(err_buffer, encoding="cp1252", newline="")
    monkeypatch.setattr(sys, "stdout", legacy_stdout)
    monkeypatch.setattr(sys, "stderr", legacy_stderr)

    code = run([str(video)], deps)

    legacy_stdout.flush()
    legacy_stderr.flush()
    assert code == EXIT_OK
    assert err_buffer.getvalue() == b""
    assert "\u2192" in out_buffer.getvalue().decode("utf-8")
