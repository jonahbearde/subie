"""The ``subie`` command line: parsing, dispatch and exit codes."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from typing import Never

from subie import __version__, models
from subie.deps import Deps, default_deps
from subie.errors import one_line
from subie.exit_codes import EXIT_FAILED, EXIT_OK, EXIT_USAGE


class UsageError(Exception):
    """The user asked for something the command line cannot express."""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        raise UsageError(message)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="subie",
        description="Write English .srt subtitles for English-language videos.",
        epilog="Exit codes: 0 success, 1 a failed video, 2 usage error.",
    )
    parser.add_argument("--version", action="version", version=f"subie {__version__}")

    commands = parser.add_subparsers(dest="command", metavar="command", required=True)
    doctor = commands.add_parser(
        "doctor",
        help="report whether this machine is ready to subtitle videos",
        description=(
            "Report the interpreter, bundled FFmpeg, media probe, resolved device, "
            "GPU, CUDA libraries, compute type, model and cache, without downloading "
            "anything."
        ),
    )
    doctor.add_argument(
        "--device",
        choices=("auto", "cuda", "cpu"),
        default="auto",
        help="device to report on (default: auto, CUDA when it is genuinely usable)",
    )
    doctor.add_argument(
        "--model",
        metavar="NAME",
        help="model to report on (default: derived from the resolved device)",
    )
    return parser


def run(argv: Sequence[str], deps: Deps) -> int:
    """Run one invocation and return its exit code. The seam every test goes through."""
    parser = build_parser()
    argv = list(argv)
    if not argv:
        _print_usage_error(parser, "a command is required (try 'subie --help')", show_help=True)
        return EXIT_USAGE

    try:
        args = parser.parse_args(argv)
    except UsageError as exc:
        _print_usage_error(parser, str(exc))
        return EXIT_USAGE
    except SystemExit as exc:  # --help and --version
        return int(exc.code or EXIT_OK)

    try:
        return _dispatch(args, deps)
    except UsageError as exc:
        _print_usage_error(parser, str(exc))
        return EXIT_USAGE
    except Exception as exc:
        if os.environ.get("SUBIE_DEBUG"):
            raise
        print(f"subie: error: {one_line(exc)}", file=sys.stderr)
        return EXIT_FAILED


def main(argv: Sequence[str] | None = None) -> int:
    return run(sys.argv[1:] if argv is None else argv, default_deps())


def _dispatch(args: argparse.Namespace, deps: Deps) -> int:
    if args.command == "doctor":
        return _doctor(args, deps)
    raise UsageError(f"unknown command '{args.command}'")


def _doctor(args: argparse.Namespace, deps: Deps) -> int:
    if args.model is not None:
        model = models.lookup(args.model)
        if model is None:
            names = ", ".join(model.name for model in models.known_models())
            raise UsageError(f"unknown model '{args.model}'; known models: {names}")

    from subie.doctor import diagnose

    result = diagnose(deps, requested_device=args.device, requested_model=args.model)
    for line in result.lines:
        print(line)
    return result.exit_code


def _print_usage_error(
    parser: argparse.ArgumentParser, message: str, *, show_help: bool = False
) -> None:
    if show_help:
        parser.print_help(sys.stderr)
    else:
        parser.print_usage(sys.stderr)
    print(f"subie: error: {message}", file=sys.stderr)
