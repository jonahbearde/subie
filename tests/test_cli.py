"""The command-line surface: usage, help, version, exit codes."""

from __future__ import annotations

from subie.cli import run
from subie.exit_codes import EXIT_OK, EXIT_USAGE
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
    assert "--version" in captured.out
    assert "--help" in captured.out


def test_doctor_help_documents_its_flags(capsys):
    code = run(["doctor", "--help"], make_deps())

    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert "--device" in captured.out
    assert "--model" in captured.out


def test_version_prints_the_package_version(capsys):
    code = run(["--version"], make_deps())

    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert "subie" in captured.out
    assert "0.1.0" in captured.out


def test_unknown_command_is_a_usage_error_without_a_traceback(capsys):
    code = run(["frobnicate"], make_deps())

    captured = capsys.readouterr()
    assert code == EXIT_USAGE
    assert "usage: subie" in captured.err
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
