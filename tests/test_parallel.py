"""Several Jobs in flight at once: the ``--jobs`` flag, its defaults and its safety."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from subie.audio import Audio
from subie.cli import run
from subie.exit_codes import EXIT_FAILED, EXIT_OK, EXIT_USAGE
from subie.media import MediaInfo
from subie.transcript import Transcript
from tests.fakes import CPU_ONLY, GPU_READY, FakeMediaProbe, FakeTranscriber, one_segment
from tests.golden import parse_transcript
from tests.support import deps as _deps
from tests.support import folder_of_videos as _folder
from tests.support import make_fresh
from tests.wav import write_wav

FIXTURES = Path(__file__).parent / "fixtures"

#: The bytes one `one_segment("Hello there.")` Video must produce.
HELLO_SIDECAR = b"1\r\n00:00:00,000 --> 00:00:01,700\r\nHello there.\r\n"

#: Long enough that two Jobs that are allowed to overlap really do overlap.
DELAY_S = 0.1


class _NoSpeechForDuration(FakeTranscriber):
    """One Video hears nothing at all; the rest hear the fixture Transcript."""

    def __init__(self, transcript: Transcript, *, delay_s: float, silent_s: float) -> None:
        super().__init__(transcript, delay_s=delay_s)
        self.silent_s = silent_s

    def transcript_for(self, audio: Audio) -> Transcript:
        if round(audio.duration_s, 3) == round(self.silent_s, 3):
            return Transcript(segments=())
        return super().transcript_for(audio)


class _FailsForDuration(FakeTranscriber):
    """One Video's recognition fails inside the same delay as the others."""

    def __init__(self, transcript: Transcript, *, delay_s: float, fails_s: float) -> None:
        super().__init__(transcript, delay_s=delay_s)
        self.fails_s = fails_s

    def transcript_for(self, audio: Audio) -> Transcript:
        if round(audio.duration_s, 3) == round(self.fails_s, 3):
            raise RuntimeError("engine exploded")
        return super().transcript_for(audio)


class _InterruptsForDuration(FakeTranscriber):
    """The engine is interrupted on one Video; the rest obey the controlled delay."""

    def __init__(self, transcript: Transcript, *, delay_s: float, interrupts_s: float) -> None:
        super().__init__(transcript, delay_s=delay_s)
        self.interrupts_s = interrupts_s

    def transcribe(self, audio: Audio) -> Transcript:
        if round(audio.duration_s, 3) == round(self.interrupts_s, 3):
            raise KeyboardInterrupt
        return super().transcribe(audio)


def test_jobs_must_be_a_positive_whole_number(tmp_path, capsys):
    video = tmp_path / "talk.wav"
    write_wav(video)
    deps, factory, _ = _deps()

    for value, complaint in (
        ("0", "must be at least 1"),
        ("-1", "must be at least 1"),
        ("two", "must be a whole number"),
        ("1.5", "must be a whole number"),
        ("", "must be a whole number"),
    ):
        code = run([str(video), "--jobs", value], deps)

        captured = capsys.readouterr()
        assert code == EXIT_USAGE, value
        assert f"argument --jobs: {complaint}" in captured.err
        assert "unrecognized arguments" not in captured.err
        assert "Traceback" not in captured.err
        assert factory.calls == []
        assert not (tmp_path / "talk.srt").exists()


def test_jobs_lets_several_videos_transcribe_at_once(tmp_path, capsys):
    folder = _folder(tmp_path, 4)
    deps, _, transcriber = _deps(transcriber=FakeTranscriber(one_segment(), delay_s=DELAY_S))

    code = run([str(folder), "--jobs", "4"], deps)

    captured = capsys.readouterr()
    assert code == EXIT_OK, captured.err
    assert transcriber.max_in_flight > 1
    assert "4 subtitled, 0 skipped, 0 failed" in captured.out


def test_jobs_one_runs_a_single_job_at_a_time(tmp_path, capsys):
    folder = _folder(tmp_path, 3)
    deps, _, transcriber = _deps(transcriber=FakeTranscriber(one_segment(), delay_s=DELAY_S))

    code = run([str(folder), "--jobs", "1"], deps)

    assert code == EXIT_OK
    assert transcriber.max_in_flight == 1


def test_the_default_on_a_gpu_machine_is_one_job_at_a_time(tmp_path, capsys):
    folder = _folder(tmp_path, 3)
    deps, _, transcriber = _deps(
        hardware=GPU_READY,
        transcriber=FakeTranscriber(one_segment(), delay_s=DELAY_S),
    )

    code = run([str(folder)], deps)

    captured = capsys.readouterr()
    assert code == EXIT_OK, captured.err
    assert transcriber.max_in_flight == 1


def test_the_default_on_a_cpu_machine_is_more_than_one_job(tmp_path, capsys):
    folder = _folder(tmp_path, 3)
    deps, _, transcriber = _deps(
        hardware=CPU_ONLY,
        transcriber=FakeTranscriber(one_segment(), delay_s=DELAY_S),
    )

    code = run([str(folder)], deps)

    captured = capsys.readouterr()
    assert code == EXIT_OK, captured.err
    assert transcriber.max_in_flight > 1


def test_the_summary_counts_every_outcome_with_jobs_in_flight(tmp_path, capsys):
    folder = tmp_path / "Videos"
    folder.mkdir()
    write_wav(folder / "good-a.wav", seconds=0.2)
    write_wav(folder / "good-b.wav", seconds=0.2)
    write_wav(folder / "quiet.wav", seconds=0.4)
    write_wav(folder / "broken.wav", seconds=0.8)
    done = folder / "done.wav"
    write_wav(done, seconds=0.6)
    done_sidecar = make_fresh(done)
    probe = FakeMediaProbe(by_name={"broken.wav": MediaInfo(duration_s=1.0, has_audio=False)})
    transcriber = _NoSpeechForDuration(one_segment("Hello there."), delay_s=DELAY_S, silent_s=0.4)
    deps, _, _ = _deps(media_probe=probe, transcriber=transcriber)

    code = run([str(folder), "--jobs", "4"], deps)

    captured = capsys.readouterr()
    assert code == EXIT_FAILED
    assert "2 subtitled, 2 skipped, 1 failed" in captured.out
    assert done_sidecar.read_bytes() == b"old sidecar"


def test_job_lines_are_whole_and_the_summary_is_last(tmp_path, capsys):
    folder = _folder(tmp_path, 4)
    deps, _, _ = _deps(transcriber=FakeTranscriber(one_segment(), delay_s=DELAY_S / 2))

    code = run([str(folder), "--jobs", "4"], deps)

    captured = capsys.readouterr()
    assert code == EXIT_OK
    lines = captured.out.splitlines()
    assert len(lines) == 5
    job_line = re.compile(r"talk-\d\.wav \u2192 talk-\d\.srt  1 cue  \d+\.\d+s")
    for line in lines[:-1]:
        assert job_line.fullmatch(line), line
    assert {line.split(" \u2192 ")[0] for line in lines[:-1]} == {
        f"talk-{index}.wav" for index in range(4)
    }
    assert lines[-1] == "4 subtitled, 0 skipped, 0 failed"


def test_sidecars_are_byte_identical_at_one_and_four_jobs(tmp_path):
    fixture = FIXTURES / "segmentation" / "clause-boundary-splits.transcript"
    transcript = parse_transcript(fixture.read_text(encoding="utf-8"))
    folder = _folder(tmp_path, 3)
    serial = tmp_path / "serial"
    parallel = tmp_path / "parallel"
    deps, _, _ = _deps(transcriber=FakeTranscriber(transcript))

    assert run([str(folder), "--jobs", "1", "--out-dir", str(serial)], deps) == EXIT_OK
    expected = {path.name: path.read_bytes() for path in serial.iterdir()}
    assert run([str(folder), "--jobs", "4", "--out-dir", str(parallel)], deps) == EXIT_OK
    actual = {path.name: path.read_bytes() for path in parallel.iterdir()}

    assert actual == expected
    assert expected, "the fixture must produce Sidecars"
    assert all(payload.count(b" --> ") > 1 for payload in expected.values())


def test_a_failing_job_leaves_the_other_jobs_sidecar_whole(tmp_path, capsys):
    folder = tmp_path / "Videos"
    folder.mkdir()
    write_wav(folder / "good.wav", seconds=0.2)
    write_wav(folder / "broken.wav", seconds=0.4)
    transcriber = _FailsForDuration(one_segment("Hello there."), delay_s=DELAY_S, fails_s=0.4)
    deps, _, _ = _deps(transcriber=transcriber)

    code = run([str(folder), "--jobs", "2"], deps)

    captured = capsys.readouterr()
    assert code == EXIT_FAILED
    assert transcriber.max_in_flight == 2
    assert "recognition failed for broken.wav" in captured.err
    assert not (folder / "broken.srt").exists()
    assert (folder / "good.srt").read_bytes() == HELLO_SIDECAR
    assert "1 subtitled, 0 skipped, 1 failed" in captured.out


def test_two_videos_that_would_share_a_sidecar_are_a_usage_error(tmp_path, capsys):
    folder = tmp_path / "Videos"
    (folder / "season-1").mkdir(parents=True)
    (folder / "season-2").mkdir()
    write_wav(folder / "season-1" / "episode.wav")
    write_wav(folder / "season-2" / "episode.wav")
    out_dir = tmp_path / "subtitles"
    deps, factory, _ = _deps()

    code = run([str(folder), "-r", "--out-dir", str(out_dir), "--jobs", "2"], deps)

    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert "would both write" in captured.err
    assert "episode.srt" in captured.err
    assert factory.calls == []
    assert not (out_dir / "episode.srt").exists()


def test_an_interrupted_run_does_not_start_every_queued_job(tmp_path):
    folder = _folder(tmp_path, 3, seconds=0.4)
    write_wav(folder / "talk-0.wav", seconds=0.2)
    probe = FakeMediaProbe()
    deps, _, _ = _deps(
        media_probe=probe,
        transcriber=_InterruptsForDuration(one_segment(), delay_s=0.3, interrupts_s=0.2),
    )

    with pytest.raises(KeyboardInterrupt):
        run([str(folder), "--jobs", "2"], deps)

    # talk-0 interrupts immediately; talk-1 is in flight; talk-2 must never start.
    assert len(probe.seen) < 3
