"""The ``subie`` command line: parsing, dispatch and exit codes."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Never

from subie import __version__, models
from subie.deps import Deps, default_deps
from subie.errors import one_line
from subie.exit_codes import EXIT_FAILED, EXIT_OK, EXIT_USAGE
from subie.models import Model
from subie.pipeline import (
    JobError,
    JobSkipped,
    RunSettings,
    resolve_run_settings,
    run_job,
)
from subie.runs import (
    JobOutcome,
    JobStatus,
    RunSummary,
    is_fresh,
    sidecar_for,
    videos_in,
)

#: The named commands. Anything else at argv[0] is a Video path (the default action).
COMMANDS = ("doctor",)

_HELP_TOKENS = ("-h", "--help")

_VALUE_FLAGS = ("--device", "--model", "--out-dir")


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


def _add_run_flags(parser: _Parser) -> None:
    """Flags that only the default action acts on, but that belong in its help."""
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="also process Videos in subfolders",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-process Videos whose Sidecar is already up to date",
    )
    parser.add_argument(
        "--out-dir",
        metavar="DIR",
        help="write every Sidecar into DIR instead of beside its Video",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="print errors only, suppressing per-Video lines and the Run summary",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="include the recognition engine's own logging",
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
    _add_run_flags(parser)
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
        description="Write a Sidecar beside each Video, or for every Video in a folder.",
        epilog=(
            "Commands: doctor. Exit codes: 0 success (including everything skipped), "
            "1 a failed Video, 2 usage error."
        ),
    )
    _add_keep_audio(parser)
    _add_run_flags(parser)
    parser.add_argument(
        "paths", nargs="+", metavar="VIDEO", help="a Video, or a folder of Videos"
    )
    return parser


def run(argv: Sequence[str], deps: Deps) -> int:
    """Run one invocation and return its exit code. The seam every test goes through."""
    _configure_output_encoding()
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


def _configure_output_encoding() -> None:
    """Write redirected output as UTF-8 so the summary arrow cannot crash a Run.

    Windows uses the ANSI code page for a redirected stdout, where U+2192 is
    unencodable. The Sidecar is already written by the time the summary line is
    printed, so a failed print must not turn a success into a reported failure.
    """
    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue
        encoding = (getattr(stream, "encoding", None) or "").lower().replace("-", "")
        if encoding == "utf8":
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue


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
    targets = _targets(args.paths, recursive=args.recursive)
    if not targets:
        return EXIT_OK
    out_dir = _prepare_out_dir(args.out_dir)

    reporter = _Reporter(quiet=args.quiet)
    outcomes: list[JobOutcome] = []
    settings: RunSettings | None = None
    settings_failure: BaseException | None = None

    with _engine_logging(args.verbose and not args.quiet):
        for target in targets:
            if target.error is not None:
                reporter.error(target.error)
                outcomes.append(_failed(target.video, target.error))
                continue

            sidecar = sidecar_for(target.video, out_dir)
            if not args.force and is_fresh(target.video, sidecar):
                outcome = JobOutcome(
                    target.video, JobStatus.SKIPPED, sidecar=sidecar, detail="up to date"
                )
                outcomes.append(outcome)
                reporter.job(outcome)
                continue

            if settings is None:
                if settings_failure is not None:
                    outcomes.append(_failed(target.video, settings_failure, sidecar=sidecar))
                    continue
                try:
                    settings = resolve_run_settings(
                        deps,
                        requested_device=args.device,
                        requested_model=requested_model,
                    )
                except Exception as exc:
                    settings_failure = exc
                    reporter.error(exc)
                    outcomes.append(_failed(target.video, exc, sidecar=sidecar))
                    continue

            try:
                result = run_job(
                    target.video,
                    settings,
                    deps,
                    sidecar=sidecar,
                    keep_audio=args.keep_audio,
                )
            except JobSkipped as exc:
                reporter.warning(exc)
                outcomes.append(
                    JobOutcome(
                        target.video,
                        JobStatus.SKIPPED,
                        sidecar=sidecar,
                        detail=one_line(exc),
                    )
                )
                continue
            except Exception as exc:
                reporter.error(exc)
                outcomes.append(_failed(target.video, exc, sidecar=sidecar))
                continue

            outcome = JobOutcome(
                video=result.video,
                status=JobStatus.SUBTITLED,
                sidecar=result.sidecar,
                cues=result.cues,
                elapsed_s=result.elapsed_s,
            )
            outcomes.append(outcome)
            reporter.job(outcome)

    summary = RunSummary.of(outcomes)
    if len(outcomes) > 1:
        reporter.summary(summary)
    return EXIT_FAILED if summary.any_failed else EXIT_OK


@dataclass(frozen=True)
class _Target:
    """A path a Run must account for, or the reason it cannot be a Job."""

    video: Path
    error: JobError | None = None


def _targets(raw_paths: Sequence[str], *, recursive: bool) -> list[_Target]:
    """Expand folders into their Videos, keeping bad paths as reportable failures."""
    targets: list[_Target] = []
    for raw in raw_paths:
        path = Path(raw).expanduser()
        if path.is_dir():
            try:
                targets.extend(_Target(video) for video in videos_in(path, recursive=recursive))
            except OSError as exc:
                targets.append(
                    _Target(
                        path,
                        JobError(f"cannot read folder {path}: {exc.strerror or exc}"),
                    )
                )
        elif path.is_file():
            targets.append(_Target(path))
        elif not path.exists():
            targets.append(_Target(path, JobError(f"video not found: {path}")))
        else:
            targets.append(_Target(path, JobError(f"not a Video file: {path}")))
    return targets


def _prepare_out_dir(raw: str | None) -> Path | None:
    if raw is None:
        return None
    out_dir = Path(raw).expanduser()
    if out_dir.exists() and not out_dir.is_dir():
        raise UsageError(f"--out-dir is not a directory: {out_dir}")
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise UsageError(
            f"cannot create output directory {out_dir}: {exc.strerror or exc}"
        ) from None
    return out_dir


def _failed(video: Path, exc: BaseException, *, sidecar: Path | None = None) -> JobOutcome:
    return JobOutcome(
        video, JobStatus.FAILED, sidecar=sidecar, detail=one_line(exc)
    )


class _Reporter:
    """The only place that decides what a Run's output looks like."""

    def __init__(self, *, quiet: bool) -> None:
        self.quiet = quiet

    def job(self, outcome: JobOutcome) -> None:
        if not self.quiet:
            print(_job_line(outcome))

    def warning(self, exc: BaseException) -> None:
        if not self.quiet:
            print(f"subie: warning: {one_line(exc)}", file=sys.stderr)

    def error(self, exc: BaseException) -> None:
        _print_error(exc)

    def summary(self, summary: RunSummary) -> None:
        if not self.quiet:
            print(summary.line())


def _job_line(outcome: JobOutcome) -> str:
    sidecar = outcome.sidecar.name if outcome.sidecar else "?"
    if outcome.status is JobStatus.SUBTITLED:
        cues = "1 cue" if outcome.cues == 1 else f"{outcome.cues} cues"
        return (
            f"{outcome.video.name} \u2192 {sidecar}  {cues}  {outcome.elapsed_s:.1f}s"
        )
    return f"{outcome.video.name} \u2192 {sidecar}  skipped ({outcome.detail or 'skipped'})"


@contextmanager
def _engine_logging(enabled: bool) -> Iterator[None]:
    """Route the recognition engine's logs to stderr for the duration of the Run."""
    if not enabled:
        yield
        return

    import logging

    engine_loggers = [logging.getLogger(name) for name in ("faster_whisper", "ctranslate2")]
    previous = [(logger.level, logger.propagate) for logger in engine_loggers]
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    for logger in engine_loggers:
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    try:
        yield
    finally:
        for logger, (level, propagate) in zip(engine_loggers, previous, strict=True):
            logger.removeHandler(handler)
            logger.setLevel(level)
            logger.propagate = propagate
        handler.close()


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
