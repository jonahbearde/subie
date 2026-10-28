"""``subie models`` through the single seam: what is cached, pulling and removing.

The download step is faked, so nothing here needs the network.
"""

from __future__ import annotations

import re
from pathlib import Path

from subie.cli import run
from subie.exit_codes import EXIT_FAILED, EXIT_OK, EXIT_USAGE
from subie.models import cache_path_for
from tests.fakes import (
    CPU_ONLY,
    FakeModelDownloader,
    FakeTranscriber,
    FakeTranscriberFactory,
    cached_model,
    make_deps,
    one_segment,
)
from tests.wav import write_wav

SMALL_EN = "Systran/faster-whisper-small.en"
BASE_EN = "Systran/faster-whisper-base.en"
OFFLINE = OSError("We couldn't connect to 'https://huggingface.co' to load this file")


def _models(capsys, deps, *args):
    code = run(["models", *args], deps)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _run_video(capsys, deps, tmp_path: Path, *args):
    video = tmp_path / "talk.wav"
    write_wav(video)
    code = run([str(video), *args], deps)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _cache_line(out: str) -> str:
    for line in out.splitlines():
        if line.strip().startswith("cache"):
            return line.split(None, 1)[1].strip()
    raise AssertionError(f"no cache line in:\n{out}")


def _deps(downloader: FakeModelDownloader | None = None):
    """A machine whose only model is whatever the fake network writes."""
    transcriber = FakeTranscriber(one_segment("Hello there."))
    factory = FakeTranscriberFactory(transcriber)
    downloader = downloader or FakeModelDownloader()
    deps = make_deps(hardware=CPU_ONLY, downloader=downloader, transcriber_factory=factory)
    return deps, downloader, factory


def test_list_on_an_empty_cache_says_so_plainly(capsys, subie_home):
    code, out, err = _models(capsys, make_deps(hardware=CPU_ONLY), "list")

    assert code == EXIT_OK
    assert err == ""
    assert "Traceback" not in out
    assert _cache_line(out) == str(subie_home / "models")
    assert "none in the cache" in out


def test_list_reports_each_model_present_with_its_size(capsys, subie_home):
    cache = subie_home / "models"
    cached_model(cache, SMALL_EN, model_bytes=b"\0" * (2 * 1024 * 1024))
    cached_model(cache, "mobiuslabsgmbh/faster-whisper-large-v3-turbo")
    # Something in the cache that is not one of the models the tool knows about.
    unrelated = cache_path_for("someone/unrelated", cache) / "snapshots" / "x"
    unrelated.mkdir(parents=True)
    (unrelated / "model.bin").write_bytes(b"junk")

    code, out, err = _models(capsys, make_deps(hardware=CPU_ONLY), "list")

    assert code == EXIT_OK
    assert err == ""
    lines = [line.strip() for line in out.splitlines() if line.startswith("  ")]
    assert _cache_line(out) == str(cache)
    assert "small.en  2 MB  " + SMALL_EN in lines
    assert "turbo" in out
    assert "1.6 GB" not in out  # the fake model is 4 KB, not a real download
    assert "unrelated" not in out
    assert "model     size  repository" in out


def test_a_model_that_is_not_usable_from_the_cache_is_not_listed(capsys, subie_home):
    cache = subie_home / "models"
    directory = cache_path_for(SMALL_EN, cache)
    snapshot = directory / "snapshots" / ("0" * 40)
    snapshot.mkdir(parents=True)
    refs = directory / "refs"
    refs.mkdir(parents=True)
    (refs / "main").write_text("0" * 40, encoding="utf-8")

    # A directory with no snapshot in it, then a snapshot without a tokenizer, then
    # one with the files a load actually needs: only the last one counts.
    for files, expected in (
        ({}, "none in the cache"),
        ({"config.json": "{}", "model.bin": "\0"}, "none in the cache"),
        ({"tokenizer.json": "{}"}, "small.en"),
    ):
        for name, contents in files.items():
            (snapshot / name).write_text(contents, encoding="utf-8")

        code, out, err = _models(capsys, make_deps(hardware=CPU_ONLY), "list")

        assert code == EXIT_OK
        assert expected in out


def test_a_snapshot_without_a_resolvable_ref_is_not_listed(capsys, subie_home):
    """A download that died before writing refs/main cannot be addressed offline."""
    cache = subie_home / "models"
    snapshot = cache_path_for(SMALL_EN, cache) / "snapshots" / ("0" * 40)
    snapshot.mkdir(parents=True)
    (snapshot / "config.json").write_text("{}", encoding="utf-8")
    (snapshot / "tokenizer.json").write_text("{}", encoding="utf-8")
    (snapshot / "model.bin").write_bytes(b"\0")

    code, out, err = _models(capsys, make_deps(hardware=CPU_ONLY), "list")

    assert code == EXIT_OK
    assert err == ""
    assert "none in the cache" in out


def test_pull_downloads_a_model_that_then_appears_in_list(capsys, subie_home):
    deps, downloader, _ = _deps()

    code, out, err = _models(capsys, deps, "pull", "small.en")

    assert code == EXIT_OK
    assert err == ""
    assert f"pulling small.en ({SMALL_EN}) into {subie_home / 'models'}" in out
    assert "pulled small.en" in out
    assert downloader.calls == [(SMALL_EN, subie_home / "models")]

    code, out, err = _models(capsys, deps, "list")

    assert code == EXIT_OK
    assert "none in the cache" not in out
    assert "small.en" in out


def test_pulling_a_model_that_is_already_cached_downloads_nothing(capsys, subie_home):
    cached_model(subie_home / "models", SMALL_EN)
    deps, downloader, _ = _deps()

    code, out, err = _models(capsys, deps, "pull", "small.en")

    assert code == EXIT_OK
    assert err == ""
    assert "small.en is already in the cache" in out
    assert str(subie_home / "models") in out
    assert downloader.calls == []


def test_pull_without_network_names_the_model_and_the_cache_and_prints_no_traceback(
    capsys, subie_home
):
    deps, _, _ = _deps(FakeModelDownloader(error=OFFLINE))

    code, out, err = _models(capsys, deps, "pull", "small.en")

    assert code == EXIT_FAILED
    assert "Traceback" not in out + err
    assert "pulling small.en" in out
    assert "model 'small.en'" in err
    assert str(subie_home / "models") in err
    assert "couldn't connect" in err

    code, out, err = _models(capsys, deps, "list")

    assert code == EXIT_OK
    assert "none in the cache" in out


def test_a_pulled_model_is_used_by_a_run_without_asking_the_network_again(
    capsys, subie_home, tmp_path
):
    deps, downloader, factory = _deps()
    assert _models(capsys, deps, "pull", "small.en")[0] == EXIT_OK

    downloader.error = OFFLINE  # the machine goes offline after the pull
    code, out, err = _run_video(capsys, deps, tmp_path)

    assert code == EXIT_OK, err
    assert factory.calls == [(SMALL_EN, "cpu", "int8")]
    assert downloader.calls == [(SMALL_EN, subie_home / "models")]
    assert (tmp_path / "talk.srt").exists()


def test_rm_removes_the_model_and_a_later_run_reports_the_missing_model(
    capsys, subie_home, tmp_path
):
    deps, downloader, factory = _deps()
    assert _models(capsys, deps, "pull", "small.en")[0] == EXIT_OK

    code, out, err = _models(capsys, deps, "rm", "small.en")

    assert code == EXIT_OK
    assert err == ""
    assert re.fullmatch(r"removed small\.en +4 KB", out.strip())
    assert not cache_path_for(SMALL_EN, subie_home / "models").exists()
    assert _models(capsys, deps, "list")[1].count("none in the cache") == 1

    downloader.error = OFFLINE
    code, out, err = _run_video(capsys, deps, tmp_path)

    assert code == EXIT_FAILED
    assert factory.calls == []
    assert "Traceback" not in out + err
    assert "model 'small.en'" in err
    assert str(subie_home / "models") in err
    assert "not in the cache" in err
    assert not (tmp_path / "talk.srt").exists()


def test_removing_a_model_that_is_not_in_the_cache_fails_clearly(capsys, subie_home):
    code, out, err = _models(capsys, make_deps(hardware=CPU_ONLY), "rm", "small.en")

    assert code == EXIT_FAILED
    assert out == ""
    assert "model 'small.en' is not in the cache" in err
    assert str(subie_home / "models") in err
    assert "Traceback" not in err


def test_unknown_model_names_are_usage_errors_and_change_nothing(capsys, subie_home):
    deps, downloader, _ = _deps()
    cached_model(subie_home / "models", SMALL_EN)

    for command in ("pull", "rm"):
        code, out, err = _models(capsys, deps, command, "gigantic")

        assert code == EXIT_USAGE
        assert out == ""
        assert "unknown model 'gigantic'" in err
        assert "small.en" in err  # the message names the models that do exist
        assert "Traceback" not in err

    assert downloader.calls == []
    assert cache_path_for(SMALL_EN, subie_home / "models").is_dir()


def test_models_without_a_subcommand_is_a_usage_error(capsys):
    code, out, err = _models(capsys, make_deps(hardware=CPU_ONLY))

    assert code == EXIT_USAGE
    assert out == ""
    assert "usage: subie" in err
    assert "Traceback" not in err


def test_a_known_model_that_cannot_be_pulled_fails_before_any_decoding(
    capsys, subie_home, tmp_path
):
    deps, downloader, factory = _deps()
    downloader.errors_by_repo[BASE_EN] = OFFLINE

    code, out, err = _run_video(capsys, deps, tmp_path, "--model", "base.en", "--keep-audio")

    assert code == EXIT_FAILED
    assert "Traceback" not in out + err
    assert "model 'base.en'" in err
    assert str(subie_home / "models") in err
    assert factory.calls == []
    assert not (tmp_path / "talk.keep-audio.wav").exists()
    assert not (tmp_path / "talk.srt").exists()


def test_a_download_that_leaves_no_usable_model_fails_before_any_decoding(
    capsys, subie_home, tmp_path
):
    class EmptyDownloader(FakeModelDownloader):
        """Reports success without writing anything, the way a broken mirror might."""

        def __call__(self, repo_id: str, *, destination: Path) -> None:
            self.calls.append((repo_id, destination))

    deps, _, factory = _deps(EmptyDownloader())

    code, out, err = _run_video(capsys, deps, tmp_path, "--keep-audio")

    assert code == EXIT_FAILED
    assert "Traceback" not in out + err
    assert "model 'small.en'" in err
    assert str(subie_home / "models") in err
    assert "not usable" in err
    assert factory.calls == []
    assert not (tmp_path / "talk.keep-audio.wav").exists()
    assert not (tmp_path / "talk.srt").exists()


def test_doctor_models_and_a_run_agree_on_the_cache_location(capsys, subie_home, tmp_path):
    deps, _, _ = _deps()
    assert _models(capsys, deps, "pull", "small.en")[0] == EXIT_OK

    _, out, _ = _models(capsys, deps, "list")
    cache = _cache_line(out)

    code = run(["doctor"], deps)
    doctor_out = capsys.readouterr().out

    assert code == EXIT_OK
    assert cache == str(subie_home / "models")
    assert re.search(rf"^\s+model cache\s+{re.escape(cache)}$", doctor_out, re.MULTILINE)
    assert re.search(r"^\s+models present\s+small\.en$", doctor_out, re.MULTILINE)

    code, _, err = _run_video(capsys, deps, tmp_path)

    assert code == EXIT_OK, err
