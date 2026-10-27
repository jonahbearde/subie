"""Cue construction and SRT rendering: exact bytes, no players required."""

from __future__ import annotations

from subie.srt import Cue, cues_from_transcript, format_timestamp, render_srt
from subie.transcript import Segment, Transcript


def test_timestamps_use_hours_minutes_seconds_and_milliseconds():
    assert format_timestamp(0) == "00:00:00,000"
    assert format_timestamp(1.5) == "00:00:01,500"
    assert format_timestamp(3661.234) == "01:01:01,234"


def test_negative_timestamps_are_clamped_to_zero():
    assert format_timestamp(-0.5) == "00:00:00,000"


def test_srt_is_utf8_without_bom_crlf_and_a_trailing_newline():
    cues = (
        Cue(start=0.0, end=1.5, text="Hello there."),
        Cue(start=3661.234, end=3662.0, text="Second line."),
    )

    rendered = render_srt(cues)

    assert rendered == (
        b"1\r\n"
        b"00:00:00,000 --> 00:00:01,500\r\n"
        b"Hello there.\r\n"
        b"\r\n"
        b"2\r\n"
        b"01:01:01,234 --> 01:01:02,000\r\n"
        b"Second line.\r\n"
    )
    assert not rendered.startswith(b"\xef\xbb\xbf")
    assert rendered.decode("utf-8").endswith("\r\n")


def test_cues_preserve_internal_text_lines():
    rendered = render_srt((Cue(start=0.0, end=1.0, text="One\r\nTwo"),))

    assert b"One\r\nTwo\r\n" in rendered


def test_naive_cue_construction_is_one_cue_per_non_empty_segment():
    transcript = Transcript(
        segments=(
            Segment(start=0.0, end=1.0, text="  First segment. "),
            Segment(start=1.2, end=1.4, text="   "),
            Segment(start=1.5, end=2.0, text="Second segment."),
        )
    )

    cues = cues_from_transcript(transcript)

    assert [(cue.start, cue.end, cue.text) for cue in cues] == [
        (0.0, 1.0, "First segment."),
        (1.5, 2.0, "Second segment."),
    ]
