"""The command-line surface: usage, help, version, exit codes."""

from __future__ import annotations

from subie.cli import run
from subie.exit_codes import EXIT_FAILED, EXIT_OK, EXIT_USAGE
from tests.fakes import make_deps


def test_no_arguments_prints_usage_and_exits_with_the_usage_code(capsys):
    code = run([], make_deps())

    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert "usage: subie" in captured.err
    assert "doctor" in captured.err
    assert "Traceback" not in captured.err


def test_help_documents_every_command_and_flag(capsys):
    code = run(["--help"], make_deps())

    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert "doctor" in captured.out
    assert "models" in captured.out
    assert "--version" in captured.out
    assert "--help" in captured.out
    assert "--device" in captured.out
    assert "--model" in captured.out
    assert "--keep-audio" in captured.out
    assert "-r" in captured.out
    assert "--force" in captured.out
    assert "--out-dir" in captured.out
    assert "--quiet" in captured.out
    assert "--verbose" in captured.out


def test_sidecar_help_documents_the_default_action(capsys):
    code = run(["talk.wav", "--help"], make_deps())

    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert "VIDEO" in captured.out
    assert "--device" in captured.out
    assert "--model" in captured.out
    assert "--keep-audio" in captured.out
    assert "-r" in captured.out
    assert "--force" in captured.out
    assert "--out-dir" in captured.out
    assert "--quiet" in captured.out
    assert "--verbose" in captured.out


def test_doctor_help_documents_its_flags(capsys):
    code = run(["doctor", "--help"], make_deps())

    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert "--device" in captured.out
    assert "--model" in captured.out


def test_models_help_documents_listing_pulling_and_removing(capsys):
    code = run(["models", "--help"], make_deps())

    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert "list" in captured.out
    assert "pull" in captured.out
    assert "rm" in captured.out


def test_models_pull_help_names_the_models_that_can_be_pulled(capsys):
    code = run(["models", "pull", "--help"], make_deps())

    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert "NAME" in captured.out
    assert "small.en" in captured.out
    assert "turbo" in captured.out


def test_models_pull_without_a_name_is_a_usage_error(capsys):
    code = run(["models", "pull"], make_deps())

    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert "Traceback" not in captured.err


def test_flags_before_a_command_still_run_the_command(capsys):
    code = run(["--device", "cpu", "doctor"], make_deps())

    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert "subie doctor" in captured.out


def test_version_prints_the_package_version(capsys):
    code = run(["--version"], make_deps())

    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert "subie" in captured.out
    assert "0.1.0" in captured.out


def test_a_bare_unknown_token_is_treated_as_a_missing_video_path(capsys):
    code = run(["frobnicate"], make_deps())

    captured = capsys.readouterr()
    assert code == EXIT_FAILED
    assert "video not found: frobnicate" in captured.err
    assert "Traceback" not in captured.err


def test_unknown_flag_is_a_usage_error(capsys):
    code = run(["doctor", "--turbo"], make_deps())

    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert "Traceback" not in captured.err


def test_unknown_device_is_a_usage_error(capsys):
    code = run(["doctor", "--device", "tpu"], make_deps())

    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert "Traceback" not in captured.err
