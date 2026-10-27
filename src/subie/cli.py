"""The ``subie`` command line: parsing, dispatch and exit codes."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Never

from subie import __version__, models
from subie.deps import Deps, default_deps
from subie.errors import one_line
from subie.exit_codes import EXIT_FAILED, EXIT_OK, EXIT_USAGE
from subie.models import Model
from subie.pipeline import (
    JobError,
    JobResult,
    resolve_run_settings,
    run_job,
    validate_video,
)

#: The named commands. Anything else at argv[0] is a Video path (the default action).
COMMANDS = ("doctor",)

_HELP_TOKENS = ("-h", "--help")

_VALUE_FLAGS = ("--device", "--model")


class UsageError(Exception):
    """The user asked for something the command line cannot express."""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        raise UsageError(message)


def _common_parser() -> _Parser:
    """Flags shared by the default action and every named command."""
    parser = _Parser(add_help=False)
    parser.add_argument("--version", action="version", version=f"subie {__version__}")
    parser.add_argument(
        "--device",
        choices=("auto", "cuda", "cpu"),
        default="auto",
        help="device to use (default: auto, CUDA when it is genuinely usable)",
    )
    parser.add_argument(
        "--model",
        metavar="NAME",
        help="model to use (default: derived from the resolved device)",
    )
    return parser


def _add_keep_audio(parser: _Parser) -> None:
    parser.add_argument(
        "--keep-audio",
        action="store_true",
        help="keep the decoded 16 kHz mono audio beside the Video for debugging",
    )


def build_parser() -> _Parser:
    """The help surface: named commands plus the default action's flags.

    The default action itself is parsed by :func:`build_sidecar_parser`, because a
    parser cannot have both an optional positional path and required subcommands.
    """
    parser = _Parser(
        prog="subie",
        parents=[_common_parser()],
        description=(
            "Write English .srt subtitles for English-language videos. "
            "With a Video path and no command, writes VIDEO.srt beside it."
        ),
        epilog=(
            "Commands: doctor. "
            "Exit codes: 0 success, 1 a failed Video or an unready machine, 2 usage error."
        ),
    )
    _add_keep_audio(parser)
    commands = parser.add_subparsers(dest="command", metavar="command")
    commands.add_parser(
        "doctor",
        parents=[_common_parser()],
        help="report whether this machine is ready to subtitle videos",
        description=(
            "Report the interpreter, bundled FFmpeg, media probe, resolved device, "
            "GPU, CUDA libraries, compute type, model and cache, without downloading "
            "anything."
        ),
    )
    return parser


def build_sidecar_parser() -> _Parser:
    """The default action: one or more Video paths, with the common flags."""
    parser = _Parser(
        prog="subie",
        parents=[_common_parser()],
        description="Write a Sidecar beside each Video.",
        epilog=("Commands: doctor. Exit codes: 0 success, 1 a failed Video, 2 usage error."),
    )
    _add_keep_audio(parser)
    parser.add_argument("paths", nargs="+", metavar="VIDEO", help="a Video to subtitle")
    return parser


def run(argv: Sequence[str], deps: Deps) -> int:
    """Run one invocation and return its exit code. The seam every test goes through."""
    argv = list(argv)
    if not argv:
        _print_usage_error(
            build_parser(),
            "a command or a Video path is required (try 'subie --help')",
            show_help=True,
        )
        return EXIT_USAGE

    parser = _parser_for(argv)
    try:
        args = parser.parse_args(argv)
    except UsageError as exc:
        _print_usage_error(parser, str(exc))
        return EXIT_USAGE
    except SystemExit as exc:  # --help and --version
        return int(exc.code or EXIT_OK)

    try:
        if getattr(args, "command", None) == "doctor":
            return _doctor(args, deps)
        return _sidecar(args, deps)
    except UsageError as exc:
        _print_usage_error(parser, str(exc))
        return EXIT_USAGE
    except Exception as exc:
        _print_error(exc)
        return EXIT_FAILED


def main(argv: Sequence[str] | None = None) -> int:
    return run(sys.argv[1:] if argv is None else argv, default_deps())


def _parser_for(argv: list[str]) -> _Parser:
    if argv[0] in COMMANDS or argv[0] in _HELP_TOKENS:
        return build_parser()
    if _first_positional(argv) in COMMANDS:
        return build_parser()
    return build_sidecar_parser()


def _first_positional(argv: list[str]) -> str | None:
    """The first token that is neither a flag nor a flag's value."""
    skip_value = False
    for token in argv:
        if skip_value:
            skip_value = False
            continue
        if token in _VALUE_FLAGS:
            skip_value = True
            continue
        if token.startswith("-"):
            continue
        return token
    return None


def _requested_model(name: str | None) -> Model | None:
    if name is None:
        return None
    model = models.lookup(name)
    if model is None:
        names = ", ".join(model.name for model in models.known_models())
        raise UsageError(f"unknown model '{name}'; known models: {names}")
    return model


def _sidecar(args: argparse.Namespace, deps: Deps) -> int:
    requested_model = _requested_model(args.model)

    videos: list[Path] = []
    failed = False
    for raw in args.paths:
        video = Path(raw).expanduser()
        try:
            validate_video(video)
        except JobError as exc:
            _print_error(exc)
            failed = True
            continue
        videos.append(video)
    if not videos:
        return EXIT_FAILED if failed else EXIT_OK

    settings = resolve_run_settings(
        deps, requested_device=args.device, requested_model=requested_model
    )
    for video in videos:
        try:
            result = run_job(video, settings, deps, keep_audio=args.keep_audio)
        except Exception as exc:
            _print_error(exc)
            failed = True
            continue
        print(_summary_line(result))
    return EXIT_FAILED if failed else EXIT_OK


def _summary_line(result: JobResult) -> str:
    cues = "1 cue" if result.cues == 1 else f"{result.cues} cues"
    return f"{result.video.name} \u2192 {result.sidecar.name}  {cues}  {result.elapsed_s:.1f}s"


def _doctor(args: argparse.Namespace, deps: Deps) -> int:
    requested_model = _requested_model(args.model)

    from subie.doctor import diagnose

    result = diagnose(deps, requested_device=args.device, requested_model=requested_model)
    for line in result.lines:
        print(line)
    return result.exit_code


def _print_error(exc: BaseException) -> None:
    print(f"subie: error: {one_line(exc)}", file=sys.stderr)


def _print_usage_error(
    parser: argparse.ArgumentParser, message: str, *, show_help: bool = False
) -> None:
    if show_help:
        parser.print_help(sys.stderr)
    else:
        parser.print_usage(sys.stderr)
    print(f"subie: error: {message}", file=sys.stderr)
