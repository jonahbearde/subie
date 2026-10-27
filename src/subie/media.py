"""Media I/O: probing and decoding through PyAV, never a system ffmpeg."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from subie.errors import SubieError


class MediaError(SubieError):
    """A Video could not be opened or read."""


@dataclass(frozen=True)
class MediaInfo:
    """What the probe could learn about a Video."""

    duration_s: float | None
    has_audio: bool


def probe_media(path: Path) -> MediaInfo:
    """Open a Video read-only and report its duration and audio-stream presence."""
    try:
        import av
    except Exception as exc:  # pragma: no cover - installation damage
        raise MediaError(f"PyAV is unavailable: {exc}") from None

    try:
        with av.open(str(path), mode="r") as container:
            has_audio = any(stream.type == "audio" for stream in container.streams)
            duration_s = (
                container.duration / av.time_base if container.duration is not None else None
            )
    except av.error.FFmpegError as exc:
        raise MediaError(f"cannot read {path.name}: {exc}") from None
    except OSError as exc:
        raise MediaError(f"cannot open {path.name}: {exc.strerror or exc}") from None

    return MediaInfo(duration_s=duration_s, has_audio=has_audio)


def ffmpeg_summary() -> str:
    """Describe the FFmpeg libraries bundled inside the PyAV wheel."""
    import av

    return f"{av.ffmpeg_version_info} (PyAV {av.__version__})"
