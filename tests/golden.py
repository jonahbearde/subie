"""Golden-file harness: a fixture Transcript in, the exact Sidecar bytes out.

A fixture lives beside the exact Sidecar bytes it must produce. Tests drive the single
seam — ``run(argv, deps)`` — rather than the segmenter's internals.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from subie.cli import run
from subie.exit_codes import EXIT_OK
from subie.text import is_bracketed, is_music_only
from subie.transcript import Segment, Transcript, Word
from tests.fakes import (
    CPU_ONLY,
    FakeMediaProbe,
    FakeTranscriber,
    FakeTranscriberFactory,
    make_deps,
)
from tests.wav import write_wav

#: The policy's numbers, repeated here so that changing one in the code is a test diff.
_LIMITS = {
    "line_chars": 42,
    "lines": 2,
    "cps": 20.0,
    "min_duration": 1.0,
    "max_duration": 7.0,
    "gap": 0.1,
}

#: The blocklist's thresholds, repeated for the same reason: the harness judges
#: production against the policy, not against production's own idea of "doubtful".
_CONFIDENCE = {"avg_logprob": -1.0, "no_speech_prob": 0.6}

#: What a Cue must show of a word, for a Cue's text to be matched back to its words.
_TOKEN = re.compile(r"[^\W_]+")


def fixture_cases(directory: Path) -> list[Path]:
    """Every ``*.transcript`` fixture in ``directory``, in a stable order."""
    return sorted(directory.glob("*.transcript"))


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
    """Read the compact fixture format.

    ``S start end [logprob=…] [no-speech=…]`` opens a Segment, ``W start end text``
    adds a word, and ``T text`` gives the open Segment's text for a Segment whose
    source reported no word timings.
    """
    segments: list[Segment] = []
    start = 0.0
    end = 0.0
    words: list[Word] = []
    spoken_text: str | None = None
    avg_logprob: float | None = None
    no_speech_prob: float | None = None
    open_segment = False

    def close() -> None:
        if not open_segment:
            return
        text = spoken_text if spoken_text is not None else " ".join(w.text.strip() for w in words)
        segments.append(
            Segment(
                start=start,
                end=end,
                text=text,
                words=tuple(words),
                avg_logprob=avg_logprob,
                no_speech_prob=no_speech_prob,
            )
        )

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        kind, _, payload = line.partition(" ")
        if kind == "S":
            close()
            fields = payload.split()
            start = float(fields[0])
            end = float(fields[1])
            options = dict(field.split("=", 1) for field in fields[2:])
            words = []
            spoken_text = None
            avg_logprob = float(options["logprob"]) if "logprob" in options else None
            no_speech_prob = float(options["no-speech"]) if "no-speech" in options else None
            open_segment = True
        elif kind == "T":
            spoken_text = payload
        elif kind == "W":
            fields = payload.split(maxsplit=2)
            text = fields[2] if len(fields) > 2 else ""
            words.append(Word(start=float(fields[0]), end=float(fields[1]), text=text))
        else:
            raise ValueError(f"unknown fixture line: {raw!r}")

    close()
    return Transcript(segments=tuple(segments))


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


@dataclass(frozen=True)
class SpokenWord:
    """One word a Cue could show, carrying the confidence of the Segment it came from."""

    start: float
    end: float
    text: str
    segment: Segment


def transcript_words(transcript: Transcript) -> list[SpokenWord]:
    """Flatten the Transcript into the words a Sidecar could display, in order.

    Music-only words carry no speech, and a Segment without word timings is one
    word-shaped piece of text, so both appear here the way the segmenter sees them.
    """
    words: list[SpokenWord] = []
    for segment in transcript.segments:
        if segment.words:
            words.extend(
                SpokenWord(word.start, word.end, word.text.strip(), segment)
                for word in segment.words
                if word.text.strip()
            )
        elif segment.text.strip():
            words.append(SpokenWord(segment.start, segment.end, segment.text.strip(), segment))
    return [word for word in words if not is_music_only(word.text)]


def assert_readability(data: bytes, transcript: Transcript, *, label: str) -> None:
    """Check the Sidecar against the policy's external limits, Cue by Cue."""
    cues = _timed_cues(data)
    assert cues, f"{label}: no Cues"
    words = transcript_words(transcript)
    cursor = 0

    for index, (start, end, lines) in enumerate(cues):
        position = f"{label}: cue {index + 1} ({_timestamp(start)} --> {_timestamp(end)})"
        _assert_limits(position, start, end, lines)

        tokens = _tokens(" ".join(lines))
        begin, stop = _match(words, cursor, tokens, position=position)
        span = words[begin:stop]
        assert abs(start - span[0].start) <= 0.001, (
            f"{position}: start is not the first word's start"
        )
        assert end >= span[-1].end - 0.001, f"{position}: ends before the last word"

        if stop < len(words):
            next_start = words[stop].start
            assert end <= next_start + 0.001, f"{position}: overlaps the next Cue"
            available = next_start - span[-1].end
            gap = next_start - end
            assert gap <= available + 0.001, f"{position}: gap exceeds the silence"
            if available >= _LIMITS["gap"] - 0.0005:
                assert gap >= _LIMITS["gap"] - 0.002, (
                    f"{position}: gap to the next Cue is {gap:.3f}s"
                )
        cursor = stop

    dropped = [word.text for word in words[cursor:] if not _droppable(word)]
    assert not dropped, f"{label}: words dropped without a rule: {dropped}"


def _assert_limits(position: str, start: float, end: float, lines: list[str]) -> None:
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


def _match(
    words: list[SpokenWord],
    cursor: int,
    tokens: tuple[str, ...],
    *,
    position: str,
) -> tuple[int, int]:
    """The word span a Cue displays, skipping only words a rule is allowed to drop."""
    for begin in range(cursor, len(words)):
        skipped = words[cursor:begin]
        if not all(_droppable(word) for word in skipped):
            break
        for stop in range(begin + 1, len(words) + 1):
            if _kept_tokens(words[begin:stop]) != tokens:
                continue
            # Punctuation can be a word of its own: it belongs to the Cue it follows.
            while stop < len(words) and _kept_tokens(words[begin : stop + 1]) == tokens:
                stop += 1
            return begin, stop
    pytest.fail(
        f"{position}: no run of Transcript words reads as {' '.join(tokens)!r}",
        pytrace=False,
    )


def _kept_tokens(span: list[SpokenWord]) -> tuple[str, ...]:
    """The tokens a Cue keeps from a span: markers survive only when nothing else does."""
    if span and all(is_bracketed(word.text) for word in span):
        return tuple(token for word in span for token in _tokens(word.text))
    return tuple(
        token for word in span if not is_bracketed(word.text) for token in _tokens(word.text)
    )


def _droppable(word: SpokenWord) -> bool:
    return is_bracketed(word.text) or _low_confidence(word.segment)


def _low_confidence(segment: Segment) -> bool:
    logprob = segment.avg_logprob
    no_speech = segment.no_speech_prob
    return (logprob is not None and logprob <= _CONFIDENCE["avg_logprob"]) or (
        no_speech is not None and no_speech >= _CONFIDENCE["no_speech_prob"]
    )


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(token.casefold() for token in _TOKEN.findall(text))


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
