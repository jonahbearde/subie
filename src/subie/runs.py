"""Planning a Run: which files it covers, where a Sidecar goes, and the outcome.

The directory scanner, the freshness rule and the Run summary live here so that the
command line only has to decide *when* to apply them. Nothing in this module touches a
model or the network.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

#: Files a directory scan treats as Videos. Both video containers and audio-only media
#: are accepted: the tool only needs an audio stream. Anything else in a folder is
#: ignored silently rather than reported as a broken Video.
VIDEO_SUFFIXES = frozenset(
    {
        ".3g2",
        ".3gp",
        ".aac",
        ".aif",
        ".aiff",
        ".alac",
        ".asf",
        ".avi",
        ".divx",
        ".f4v",
        ".flac",
        ".flv",
        ".m2ts",
        ".m2v",
        ".m4a",
        ".m4p",
        ".m4v",
        ".mkv",
        ".mov",
        ".mp3",
        ".mp4",
        ".mpe",
        ".mpeg",
        ".mpg",
        ".mpv",
        ".mts",
        ".mxf",
        ".ogg",
        ".ogv",
        ".opus",
        ".qt",
        ".rm",
        ".rmvb",
        ".ts",
        ".vob",
        ".wav",
        ".webm",
        ".wma",
        ".wmv",
        ".y4m",
    }
)


class JobStatus(StrEnum):
    """What happened to one Video in a Run."""

    SUBTITLED = "subtitled"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class JobOutcome:
    """One Video's result, whether it produced a Sidecar, was skipped, or failed."""

    video: Path
    status: JobStatus
    sidecar: Path | None = None
    cues: int = 0
    elapsed_s: float = 0.0
    detail: str | None = None


@dataclass(frozen=True)
class RunSummary:
    """The counts a Run reports once it covered more than one Video."""

    subtitled: int
    skipped: int
    failed: int

    @classmethod
    def of(cls, outcomes: Iterable[JobOutcome]) -> RunSummary:
        counts = {status: 0 for status in JobStatus}
        for outcome in outcomes:
            counts[outcome.status] += 1
        return cls(
            subtitled=counts[JobStatus.SUBTITLED],
            skipped=counts[JobStatus.SKIPPED],
            failed=counts[JobStatus.FAILED],
        )

    @property
    def any_failed(self) -> bool:
        return self.failed > 0

    def line(self) -> str:
        return f"{self.subtitled} subtitled, {self.skipped} skipped, {self.failed} failed"


def is_video_path(path: Path) -> bool:
    """Whether a directory scan should consider this file a Video."""
    return path.suffix.lower() in VIDEO_SUFFIXES


def videos_in(directory: Path, *, recursive: bool) -> list[Path]:
    """The Videos directly inside ``directory``, or below it when ``recursive``.

    Non-video files and (unless recursive) subfolders are ignored without a word. The
    order is stable so that a Run's output is reproducible.
    """
    walker = directory.rglob("*") if recursive else directory.iterdir()
    videos = [path for path in walker if path.is_file() and is_video_path(path)]
    return sorted(videos, key=lambda path: str(path).casefold())


def sidecar_for(video: Path, out_dir: Path | None = None) -> Path:
    """Where a Video's Sidecar belongs: beside it, or under ``out_dir`` named after it."""
    name = f"{video.stem}.srt"
    if out_dir is None:
        return video.with_name(name)
    return out_dir / name


def is_fresh(video: Path, sidecar: Path) -> bool:
    """Whether an existing Sidecar is at least as new as its Video."""
    if sidecar == video:
        return False
    try:
        return sidecar.stat().st_mtime_ns >= video.stat().st_mtime_ns
    except OSError:
        return False
