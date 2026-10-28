"""SRT rendering: exact bytes, no players required."""

from __future__ import annotations

from subie.segment import Cue
from subie.srt import format_timestamp, render_srt


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
