"""Golden-file harness for readability segmentation.

A fixture Transcript lives beside the exact Sidecar bytes it must produce. The test
drives the single seam — ``run(argv, deps)`` — rather than the segmenter's internals.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from subie.cli import run
from subie.exit_codes import EXIT_OK
from subie.transcript import Segment, Transcript, Word
from tests.fakes import (
    CPU_ONLY,
    FakeMediaProbe,
    FakeTranscriber,
    FakeTranscriberFactory,
    make_deps,
)
from tests.wav import write_wav

FIXTURES = Path(__file__).parent / "fixtures" / "segmentation"

#: The policy's numbers, repeated here so that changing one in the code is a test diff.
_LIMITS = {
    "line_chars": 42,
    "lines": 2,
    "cps": 20.0,
    "min_duration": 1.0,
    "max_duration": 7.0,
    "gap": 0.1,
}


def fixture_cases() -> list[Path]:
    """Every ``*.transcript`` fixture, in a stable order."""
    return sorted(FIXTURES.glob("*.transcript"))


def run_fixture(transcript_path: Path, tmp_path: Path, capsys) -> tuple[bytes, Transcript]:
    """Run one fixture through the real CLI seam and return its Sidecar bytes."""
    transcript = parse_transcript(transcript_path.read_text(encoding="utf-8"))
    video = tmp_path / "clip.wav"
    write_wav(video)
    factory = FakeTranscriberFactory(FakeTranscriber(transcript))
    deps = make_deps(
        hardware=CPU_ONLY,
        media_probe=FakeMediaProbe(),
        transcriber_factory=factory,
    )

    code = run([str(video)], deps)
    captured = capsys.readouterr()

    assert code == EXIT_OK, captured.err
    assert captured.err == ""
    sidecar = tmp_path / "clip.srt"
    assert sidecar.exists(), "a fixture with speech must produce a Sidecar"
    return sidecar.read_bytes(), transcript


def parse_transcript(text: str) -> Transcript:
    """Read the compact fixture format: ``S start end`` and ``W start end text``."""
    segments: list[Segment] = []
    segment_start = 0.0
    segment_end = 0.0
    words: list[Word] = []
    seen_segment = False

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(maxsplit=3)
        kind = parts[0]
        if kind == "S":
            if seen_segment:
                segments.append(_segment(segment_start, segment_end, words))
            segment_start = float(parts[1])
            segment_end = float(parts[2])
            words = []
            seen_segment = True
        elif kind == "W":
            word_text = parts[3] if len(parts) > 3 else ""
            words.append(Word(start=float(parts[1]), end=float(parts[2]), text=word_text))
        else:
            raise ValueError(f"unknown fixture line: {raw!r}")

    if seen_segment:
        segments.append(_segment(segment_start, segment_end, words))
    return Transcript(segments=tuple(segments))


def _segment(start: float, end: float, words: list[Word]) -> Segment:
    return Segment(
        start=start,
        end=end,
        text=" ".join(word.text.strip() for word in words),
        words=tuple(words),
    )


def assert_sidecar_bytes(actual: bytes, expected: bytes, *, label: str) -> None:
    """Assert exact bytes, reporting the first differing Cue when there is one."""
    if actual == expected:
        return

    actual_cues = _parsed_cues(actual)
    expected_cues = _parsed_cues(expected)
    for index in range(max(len(actual_cues), len(expected_cues))):
        actual_cue = actual_cues[index] if index < len(actual_cues) else None
        expected_cue = expected_cues[index] if index < len(expected_cues) else None
        if actual_cue != expected_cue:
            pytest.fail(
                f"{label}: cue {index + 1} differs\n"
                f"  expected: {expected_cue!r}\n"
                f"  actual:   {actual_cue!r}",
                pytrace=False,
            )

    for offset, (actual_byte, expected_byte) in enumerate(zip(actual, expected, strict=False)):
        if actual_byte != expected_byte:
            pytest.fail(
                f"{label}: bytes differ at offset {offset} "
                f"(actual {actual_byte:#04x}, expected {expected_byte:#04x})",
                pytrace=False,
            )
    pytest.fail(
        f"{label}: Sidecar lengths differ (actual {len(actual)}, expected {len(expected)})",
        pytrace=False,
    )


def assert_readability(data: bytes, transcript: Transcript, *, label: str) -> None:
    """Check the Sidecar against the policy's external limits, Cue by Cue."""
    cues = _timed_cues(data)
    assert cues, f"{label}: no Cues"
    words = [word for segment in transcript.segments for word in segment.words]
    cursor = 0

    for index, (start, end, lines) in enumerate(cues):
        position = f"{label}: cue {index + 1} ({_timestamp(start)} --> {_timestamp(end)})"
        assert 1 <= len(lines) <= _LIMITS["lines"], f"{position}: {len(lines)} lines"
        for line in lines:
            assert len(line) <= _LIMITS["line_chars"], f"{position}: line too long: {line!r}"

        duration = end - start
        assert duration >= _LIMITS["min_duration"] - 0.002, f"{position}: {duration:.3f}s long"
        assert duration <= _LIMITS["max_duration"] + 0.002, f"{position}: {duration:.3f}s long"

        characters = len(" ".join(lines))
        assert characters / duration <= _LIMITS["cps"] + 0.05, (
            f"{position}: {characters / duration:.2f} CPS"
        )

        tokens = " ".join(lines).split(" ")
        matched = words[cursor : cursor + len(tokens)]
        if [word.text.strip() for word in matched] != tokens:
            pytest.fail(
                f"{label}: cue {index + 1} text does not match the Transcript words",
                pytrace=False,
            )
        cursor += len(tokens)

        first_word_start = matched[0].start
        last_word_end = matched[-1].end
        assert abs(start - first_word_start) <= 0.001, (
            f"{position}: start is not the first word's start"
        )
        assert end >= last_word_end - 0.001, f"{position}: ends before the last word"

        if cursor < len(words):
            next_start = words[cursor].start
            assert end <= next_start + 0.001, f"{position}: overlaps the next Cue"
            available = next_start - last_word_end
            gap = next_start - end
            assert gap <= available + 0.001, f"{position}: gap exceeds the silence"
            if available >= _LIMITS["gap"] - 0.0005:
                assert gap >= _LIMITS["gap"] - 0.002, (
                    f"{position}: gap to the next Cue is {gap:.3f}s"
                )
            if index + 1 < len(cues):
                assert abs(cues[index + 1][0] - next_start) <= 0.001, (
                    f"{position}: the next Cue does not start on its first word"
                )

    assert cursor == len(words), f"{label}: not every Transcript word appears in a Cue"


def _parsed_cues(data: bytes) -> list[tuple[str, str, str]]:
    cues: list[tuple[str, str, str]] = []
    for block in _blocks(data):
        lines = block.split("\n")
        cues.append((lines[0], lines[1], "\n".join(lines[2:])))
    return cues


def _timed_cues(data: bytes) -> list[tuple[float, float, list[str]]]:
    cues: list[tuple[float, float, list[str]]] = []
    for block in _blocks(data):
        lines = block.split("\n")
        start, end = lines[1].split(" --> ")
        cues.append((_seconds(start), _seconds(end), lines[2:]))
    return cues


def _blocks(data: bytes) -> list[str]:
    text = data.decode("utf-8").replace("\r\n", "\n").rstrip("\n")
    return [block for block in text.split("\n\n") if block.strip()]


def _seconds(timestamp: str) -> float:
    hours, minutes, rest = timestamp.split(":")
    seconds, milliseconds = rest.split(",")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000


def _timestamp(seconds: float) -> str:
    total_ms = round(seconds * 1000)
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"
