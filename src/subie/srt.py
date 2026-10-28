"""SRT rendering. Cue construction lives in :mod:`subie.segment`."""

from __future__ import annotations

from collections.abc import Sequence

from subie.segment import Cue


def render_srt(cues: Sequence[Cue]) -> bytes:
    """Render cues as UTF-8 SRT: CRLF, no BOM, one blank line between cues."""
    blocks = [
        "\r\n".join(
            (
                str(number),
                f"{format_timestamp(cue.start)} --> {format_timestamp(cue.end)}",
                "\r\n".join(cue.text.splitlines()),
                "",
            )
        )
        for number, cue in enumerate(cues, start=1)
    ]
    return "\r\n".join(blocks).encode("utf-8")


def format_timestamp(seconds: float) -> str:
    """Format seconds as SRT's ``hh:mm:ss,mmm``."""
    total_ms = max(0, round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"
