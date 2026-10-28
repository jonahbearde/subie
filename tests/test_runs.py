"""Run planning: folders, freshness, per-Job failure, exit codes and output discipline."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from subie.cli import run
from subie.exit_codes import EXIT_FAILED, EXIT_OK, EXIT_USAGE
from subie.media import MediaError, MediaInfo
from subie.transcript import Transcript
from tests.fakes import (
    CPU_ONLY,
    FakeMediaProbe,
    FakeTranscriber,
    FakeTranscriberFactory,
    make_deps,
    one_segment,
)
from tests.wav import write_wav


def _deps(
    transcript: Transcript | None = None,
    *,
    media_probe: FakeMediaProbe | None = None,
    transcriber: FakeTranscriber | None = None,
):
    transcriber = transcriber or FakeTranscriber(transcript or one_segment("Hello there."))
    factory = FakeTranscriberFactory(transcriber)
    deps = make_deps(
        hardware=CPU_ONLY,
        media_probe=media_probe,
        transcriber_factory=factory,
    )
    return deps, factory, transcriber


def _video(path: Path) -> Path:
    write_wav(path)
    return path


def _make_fresh(video: Path, contents: bytes = b"old sidecar") -> Path:
    """Give ``video`` a Sidecar whose mtime is unambiguously newer."""
    sidecar = video.with_suffix(".srt")
    sidecar.write_bytes(contents)
    stamp = time.time_ns()
    os.utime(video, ns=(stamp, stamp))
    os.utime(sidecar, ns=(stamp + 1_000_000_000, stamp + 1_000_000_000))
    return sidecar


def test_a_folder_subtitles_every_video_directly_inside_and_ignores_non_videos(tmp_path, capsys):
    folder = tmp_path / "Videos"
    folder.mkdir()
    first = _video(folder / "first.wav")
    second = _video(folder / "second.wav")
    (folder / "notes.txt").write_text("not media", encoding="utf-8")
    probe = FakeMediaProbe()
    deps, factory, _ = _deps(media_probe=probe)

    code = run([str(folder)], deps)

    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert (folder / "first.srt").exists()
    assert (folder / "second.srt").exists()
    assert first.name in captured.out
    assert second.name in captured.out
    assert "notes" not in captured.out + captured.err
    assert [path.name for path in probe.seen] == ["first.wav", "second.wav"]
    assert "2 subtitled, 0 skipped, 0 failed" in captured.out
    assert len(factory.calls) == 2


def test_subfolders_are_not_entered_by_default(tmp_path, capsys):
    folder = tmp_path / "Videos"
    (folder / "sub").mkdir(parents=True)
    _video(folder / "top.wav")
    _video(folder / "sub" / "nested.wav")
    deps, factory, _ = _deps()

    code = run([str(folder)], deps)

    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert (folder / "top.srt").exists()
    assert not (folder / "sub" / "nested.srt").exists()
    assert "top.wav" in captured.out
    assert "nested" not in captured.out
    assert len(factory.calls) == 1
    assert len(factory.transcriber.seen) == 1


def test_recursive_enters_subfolders_and_writes_each_sidecar_beside_its_video(tmp_path, capsys):
    folder = tmp_path / "Videos"
    (folder / "sub").mkdir(parents=True)
    top = _video(folder / "top.wav")
    nested = _video(folder / "sub" / "nested.wav")
    deps, _, _ = _deps()

    code = run([str(folder), "-r"], deps)

    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert (folder / "top.srt").exists()
    assert (folder / "sub" / "nested.srt").exists()
    assert "2 subtitled, 0 skipped, 0 failed" in captured.out
    assert top.exists() and nested.exists()


def test_a_fresh_sidecar_is_reported_skipped_and_not_reprocessed(tmp_path, capsys):
    video = _video(tmp_path / "talk.wav")
    sidecar = _make_fresh(video)
    deps, factory, _ = _deps()

    code = run([str(video)], deps)

    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert "skipped (up to date)" in captured.out
    assert captured.err == ""
    assert factory.calls == []
    assert sidecar.read_bytes() == b"old sidecar"


def test_force_reprocesses_a_fresh_sidecar(tmp_path, capsys):
    video = _video(tmp_path / "talk.wav")
    sidecar = _make_fresh(video)
    deps, factory, _ = _deps(one_segment("Hello there."))

    code = run([str(video), "--force"], deps)

    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert "1 cue" in captured.out
    assert len(factory.calls) == 1
    assert sidecar.read_bytes() == (b"1\r\n00:00:00,000 --> 00:00:01,700\r\nHello there.\r\n")


def test_out_dir_places_every_sidecar_there_named_after_its_video(tmp_path, capsys):
    folder = tmp_path / "Videos"
    folder.mkdir()
    _video(folder / "first.wav")
    _video(folder / "second.wav")
    out_dir = tmp_path / "subtitles" / "nested"
    deps, _, _ = _deps()

    code = run([str(folder), "--out-dir", str(out_dir)], deps)

    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert sorted(path.name for path in out_dir.iterdir()) == ["first.srt", "second.srt"]
    assert not (folder / "first.srt").exists()
    assert not (folder / "second.srt").exists()
    assert "2 subtitled, 0 skipped, 0 failed" in captured.out


def test_freshness_is_checked_in_the_out_dir(tmp_path, capsys):
    video = _video(tmp_path / "talk.wav")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    sidecar = out_dir / "talk.srt"
    sidecar.write_bytes(b"old sidecar")
    stamp = time.time_ns()
    os.utime(video, ns=(stamp, stamp))
    os.utime(sidecar, ns=(stamp + 1_000_000_000, stamp + 1_000_000_000))
    deps, factory, _ = _deps()

    code = run([str(video), "--out-dir", str(out_dir)], deps)

    assert code == EXIT_OK
    assert factory.calls == []
    assert sidecar.read_bytes() == b"old sidecar"


def test_a_video_with_no_audio_fails_without_a_sidecar(tmp_path, capsys):
    video = _video(tmp_path / "silent.wav")
    probe = FakeMediaProbe(by_name={"silent.wav": MediaInfo(duration_s=1.0, has_audio=False)})
    deps, factory, _ = _deps(media_probe=probe)

    code = run([str(video)], deps)

    captured = capsys.readouterr()
    assert code == EXIT_FAILED
    assert "has no audio stream" in captured.err
    assert not (tmp_path / "silent.srt").exists()
    assert factory.calls == []


def test_a_video_with_no_speech_warns_and_counts_as_a_skip(tmp_path, capsys):
    video = _video(tmp_path / "quiet.wav")
    deps, _, _ = _deps(Transcript(segments=()))

    code = run([str(video)], deps)

    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert "warning: no speech detected" in captured.err
    assert not (tmp_path / "quiet.srt").exists()


def test_one_broken_video_does_not_stop_later_videos(tmp_path, capsys):
    folder = tmp_path / "Videos"
    folder.mkdir()
    _video(folder / "first.wav")
    _video(folder / "broken.wav")
    _video(folder / "last.wav")
    probe = FakeMediaProbe(by_name={"broken.wav": MediaInfo(duration_s=1.0, has_audio=False)})
    deps, factory, _ = _deps(media_probe=probe)

    code = run([str(folder)], deps)

    captured = capsys.readouterr()
    assert code == EXIT_FAILED
    assert (folder / "first.srt").exists()
    assert (folder / "last.srt").exists()
    assert not (folder / "broken.srt").exists()
    assert len(factory.calls) == 2
    assert "2 subtitled, 0 skipped, 1 failed" in captured.out


def test_a_video_that_cannot_be_read_fails_without_stopping_the_rest(tmp_path, capsys):
    folder = tmp_path / "Videos"
    folder.mkdir()
    _video(folder / "first.wav")
    _video(folder / "broken.wav")
    _video(folder / "last.wav")
    probe = FakeMediaProbe(
        errors_by_name={"broken.wav": MediaError("cannot read broken.wav: invalid data")}
    )
    deps, factory, _ = _deps(media_probe=probe)

    code = run([str(folder)], deps)

    captured = capsys.readouterr()
    assert code == EXIT_FAILED
    assert "cannot read broken.wav" in captured.err
    assert (folder / "first.srt").exists()
    assert (folder / "last.srt").exists()
    assert not (folder / "broken.srt").exists()
    assert len(factory.calls) == 2
    assert "2 subtitled, 0 skipped, 1 failed" in captured.out


def test_a_folder_of_good_broken_nonvideo_and_already_subtitled(tmp_path, capsys):
    folder = tmp_path / "Videos"
    folder.mkdir()
    _video(folder / "good.wav")
    _video(folder / "broken.wav")
    (folder / "notes.txt").write_text("not media", encoding="utf-8")
    done = _video(folder / "done.wav")
    done_sidecar = _make_fresh(done, b"already done")
    probe = FakeMediaProbe(by_name={"broken.wav": MediaInfo(duration_s=1.0, has_audio=False)})
    deps, factory, _ = _deps(media_probe=probe)

    code = run([str(folder)], deps)

    captured = capsys.readouterr()
    assert code == EXIT_FAILED
    assert (folder / "good.srt").exists()
    assert not (folder / "broken.srt").exists()
    assert done_sidecar.read_bytes() == b"already done"
    assert len(factory.calls) == 1
    assert "notes" not in captured.out + captured.err
    assert "1 subtitled, 1 skipped, 1 failed" in captured.out


def test_everything_skipped_is_still_success(tmp_path, capsys):
    folder = tmp_path / "Videos"
    folder.mkdir()
    _make_fresh(_video(folder / "first.wav"))
    _make_fresh(_video(folder / "second.wav"))
    deps, factory, _ = _deps()

    code = run([str(folder)], deps)

    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert "0 subtitled, 2 skipped, 0 failed" in captured.out
    assert factory.calls == []


def test_quiet_suppresses_per_video_lines_and_the_summary(tmp_path, capsys):
    folder = tmp_path / "Videos"
    folder.mkdir()
    _video(folder / "good.wav")
    _make_fresh(_video(folder / "done.wav"))
    deps, _, _ = _deps()

    code = run([str(folder), "--quiet"], deps)

    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert captured.out == ""
    assert captured.err == ""


def test_quiet_still_prints_errors(tmp_path, capsys):
    video = _video(tmp_path / "silent.wav")
    probe = FakeMediaProbe(by_name={"silent.wav": MediaInfo(duration_s=1.0, has_audio=False)})
    deps, _, _ = _deps(media_probe=probe)

    code = run([str(video), "--quiet"], deps)

    captured = capsys.readouterr()
    assert code == EXIT_FAILED
    assert captured.out == ""
    assert "has no audio stream" in captured.err


def test_quiet_suppresses_the_no_speech_warning(tmp_path, capsys):
    video = _video(tmp_path / "quiet.wav")
    deps, _, _ = _deps(Transcript(segments=()))

    code = run([str(video), "--quiet"], deps)

    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert captured.out == ""
    assert captured.err == ""


class _LoggingTranscriber(FakeTranscriber):
    def transcribe(self, audio):
        logging.getLogger("faster_whisper").info("engine marker")
        return super().transcribe(audio)


def test_verbose_includes_engine_logging(tmp_path, capsys):
    video = _video(tmp_path / "talk.wav")
    deps, _, _ = _deps(transcriber=_LoggingTranscriber(one_segment()))

    assert run([str(video), "--force"], deps) == EXIT_OK
    default = capsys.readouterr()
    assert "engine marker" not in default.err

    assert run([str(video), "--force", "--verbose"], deps) == EXIT_OK
    verbose = capsys.readouterr()
    assert "engine marker" in verbose.err


def test_a_single_video_prints_no_run_summary(tmp_path, capsys):
    video = _video(tmp_path / "talk.wav")
    deps, _, _ = _deps()

    assert run([str(video)], deps) == EXIT_OK

    captured = capsys.readouterr()
    assert len(captured.out.splitlines()) == 1
    assert "subtitled," not in captured.out
    assert "skipped," not in captured.out


def test_out_dir_that_is_a_file_is_a_usage_error(tmp_path, capsys):
    video = _video(tmp_path / "talk.wav")
    out_file = tmp_path / "out"
    out_file.write_text("not a directory", encoding="utf-8")
    deps, factory, _ = _deps()

    code = run([str(video), "--out-dir", str(out_file)], deps)

    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert "not a directory" in captured.err
    assert factory.calls == []
