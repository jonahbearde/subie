"""Readability segmentation: a pure function from a Transcript to Cues.

The engine's segment boundaries are input, not output. Words are packed into Cues until
one of the limits in ``docs/subtitle-policy.md`` is reached; the values and their
precedence live in that document, not here.

This module does no I/O, touches no model and reads no clock, so the same Transcript
always produces the same Cue list.
"""

from __future__ import annotations

from dataclasses import dataclass

from subie.transcript import Transcript, Word

#: Readability limits. docs/subtitle-policy.md is the reference for their meaning.
MAX_LINE_CHARS = 42
MAX_LINES_PER_CUE = 2
MIN_LINE_BALANCE = 0.5
MAX_READING_CPS = 20.0
MIN_CUE_DURATION_S = 1.0
MAX_CUE_DURATION_S = 7.0
TRAILING_PADDING_S = 0.2
INTER_CUE_GAP_S = 0.1

_SENTENCE_END = frozenset(".?!")
_CLAUSE_END = frozenset(",;:")
_CLOSERS = frozenset("\"')]}\u2019\u201d\u00bb")


@dataclass(frozen=True)
class Cue:
    """One on-screen subtitle event: a start, an end, and at most two lines of text."""

    start: float
    end: float
    text: str


def cues_from_transcript(transcript: Transcript) -> tuple[Cue, ...]:
    """Build the readable Cue list for a Transcript.

    Sentence ends are treated as grouping opportunities, not as Cue boundaries: short
    sentences share a Cue when the combination still satisfies every limit, and long
    ones are split at clause punctuation or at the longest pause.
    """
    words = _speech_words(transcript)
    if not words:
        return ()
    return tuple(
        Cue(
            start=words[first].start,
            end=_timed_end(words, first, last),
            text="\n".join(_line_break(_cue_text(words, first, last))),
        )
        for first, last in _cue_groups(words)
    )


def _speech_words(transcript: Transcript) -> tuple[Word, ...]:
    """Flatten the engine's segments into the word stream segmentation works on.

    A segment without word timings still yields one word, so a Transcript from a source
    that omits them degrades to segment-shaped Cues instead of disappearing.
    """
    words: list[Word] = []
    for segment in transcript.segments:
        if segment.words:
            words.extend(
                Word(
                    start=word.start,
                    end=word.end,
                    text=text,
                    probability=word.probability,
                )
                for word in segment.words
                if (text := word.text.strip())
            )
            continue
        text = segment.text.strip()
        if text:
            words.append(Word(start=segment.start, end=segment.end, text=text))
    return tuple(words)


def _cue_groups(words: tuple[Word, ...]) -> list[tuple[int, int]]:
    """Choose inclusive word ranges for Cues, merging short sentences where allowed."""
    groups: list[tuple[int, int]] = []
    pending: tuple[int, int] | None = None
    for first, last in _sentences(words):
        if _fits(words, first, last):
            if pending is not None and _fits(words, pending[0], last):
                pending = (pending[0], last)
                continue
            if pending is not None:
                groups.append(pending)
            pending = (first, last)
            continue

        if pending is not None:
            groups.append(pending)
            pending = None
        groups.extend(_split(words, first, last))
    if pending is not None:
        groups.append(pending)
    return groups


def _sentences(words: tuple[Word, ...]) -> list[tuple[int, int]]:
    """Inclusive word ranges, split after each sentence-ending token."""
    ranges: list[tuple[int, int]] = []
    first = 0
    for last, word in enumerate(words):
        if _ends_sentence(word.text):
            ranges.append((first, last))
            first = last + 1
    if first < len(words):
        ranges.append((first, len(words) - 1))
    return ranges


def _fits(words: tuple[Word, ...], first: int, last: int) -> bool:
    return _fits_text_and_duration(words, first, last) and _fits_reading_speed(words, first, last)


def _fits_text_and_duration(words: tuple[Word, ...], first: int, last: int) -> bool:
    if _layout(_cue_text(words, first, last)) is None:
        return False
    duration = words[last].end + TRAILING_PADDING_S - words[first].start
    return duration <= MAX_CUE_DURATION_S


def _fits_reading_speed(words: tuple[Word, ...], first: int, last: int) -> bool:
    duration = _timed_end(words, first, last) - words[first].start
    if duration <= 0:
        return False
    return len(_cue_text(words, first, last)) / duration <= MAX_READING_CPS


def _split(words: tuple[Word, ...], first: int, last: int) -> list[tuple[int, int]]:
    """Split an over-long sentence by text capacity, then by reading speed."""
    groups: list[tuple[int, int]] = []
    for start, end in _capacity_groups(words, first, last):
        groups.extend(_reading_speed_groups(words, start, end))
    return groups


def _capacity_groups(words: tuple[Word, ...], first: int, last: int) -> list[tuple[int, int]]:
    """Greedy fill by line count, line length and maximum duration."""
    groups: list[tuple[int, int]] = []
    start = first
    while start <= last:
        end = _max_capacity_end(words, start, last)
        if end >= last:
            groups.append((start, last))
            break
        split = _preferred_break(words, start, end)
        groups.append((start, split))
        start = split + 1
    return groups


def _max_capacity_end(words: tuple[Word, ...], first: int, last: int) -> int:
    end = first
    for candidate in range(first, last + 1):
        if not _fits_text_and_duration(words, first, candidate):
            break
        end = candidate
    return end


def _reading_speed_groups(words: tuple[Word, ...], first: int, last: int) -> list[tuple[int, int]]:
    """Split a Cue that would exceed the reading-speed limit; never stretch it."""
    if last <= first or _fits_reading_speed(words, first, last):
        return [(first, last)]
    split = _reading_speed_break(words, first, last)
    return _reading_speed_groups(words, first, split) + _reading_speed_groups(
        words, split + 1, last
    )


def _preferred_break(words: tuple[Word, ...], first: int, max_end: int) -> int:
    """The best break point at or before ``max_end``, in policy precedence order."""
    if max_end <= first:
        return first
    boundary = _last_boundary(words, first, max_end + 1)
    return max_end if boundary is None else boundary


def _reading_speed_break(words: tuple[Word, ...], first: int, last: int) -> int:
    """The best place to split a reading-speed offender, always before ``last``."""
    boundary = _last_boundary(words, first, last)
    if boundary is not None:
        return boundary
    return _balanced_split(words, first, last)


def _last_boundary(words: tuple[Word, ...], first: int, last: int) -> int | None:
    """Latest sentence end, clause end, or longest pause strictly before ``last``."""
    if last <= first:
        return None
    for index in range(last - 1, first - 1, -1):
        if _ends_sentence(words[index].text):
            return index
    for index in range(last - 1, first - 1, -1):
        if _ends_clause(words[index].text):
            return index
    return _longest_pause(words, first, last)


def _longest_pause(words: tuple[Word, ...], first: int, last: int) -> int | None:
    """The latest word before the longest positive inter-word pause."""
    best: int | None = None
    best_pause = 0.0
    for index in range(first, last):
        pause = words[index + 1].start - words[index].end
        if pause > best_pause:
            best = index
            best_pause = pause
    return best


def _balanced_split(words: tuple[Word, ...], first: int, last: int) -> int:
    """The word boundary whose two halves differ least in characters."""
    best = first
    best_score: int | None = None
    for index in range(first, last):
        left = len(_cue_text(words, first, index))
        right = len(_cue_text(words, index + 1, last))
        score = abs(left - right)
        if best_score is None or score < best_score:
            best = index
            best_score = score
    return best


def _cue_text(words: tuple[Word, ...], first: int, last: int) -> str:
    return " ".join(word.text for word in words[first : last + 1])


def _line_break(text: str) -> tuple[str, ...]:
    """Lay a Cue's text out in at most two lines, preferring clause boundaries."""
    if len(text) <= MAX_LINE_CHARS:
        return (text,)
    tokens = text.split(" ")
    candidates: list[tuple[bool, bool, int, float, int, str, str]] = []
    for index in range(1, len(tokens)):
        left = " ".join(tokens[:index])
        right = " ".join(tokens[index:])
        if len(left) > MAX_LINE_CHARS or len(right) > MAX_LINE_CHARS:
            continue
        candidates.append(
            (
                not _ends_sentence(tokens[index - 1]),
                not _ends_clause(tokens[index - 1]),
                abs(len(left) - len(right)),
                abs(len(left) - len(text) / 2),
                index,
                left,
                right,
            )
        )
    if not candidates:
        return (text,)
    preferred = [
        candidate
        for candidate in candidates
        if (not candidate[0] or not candidate[1]) and _balanced(candidate[5], candidate[6])
    ]
    if preferred:
        preferred.sort(key=lambda candidate: candidate[:5])
        _, _, _, _, _, left, right = preferred[0]
        return (left, right)
    _, _, _, _, _, left, right = min(candidates, key=lambda candidate: candidate[2:5])
    return (left, right)


def _balanced(left: str, right: str) -> bool:
    shorter, longer = sorted((len(left), len(right)))
    return longer == 0 or shorter >= MIN_LINE_BALANCE * longer


def _layout(text: str) -> tuple[str, ...] | None:
    lines = _line_break(text)
    if len(lines) > MAX_LINES_PER_CUE:
        return None
    if any(len(line) > MAX_LINE_CHARS for line in lines):
        return None
    return lines


def _timed_end(words: tuple[Word, ...], first: int, last: int) -> float:
    """The Cue's out: padding, the inter-Cue gap, and the one-second minimum."""
    start = words[first].start
    next_start = words[last + 1].start if last + 1 < len(words) else None
    end = _clipped_end(words[last].end, next_start)
    if end - start >= MIN_CUE_DURATION_S:
        return end

    target = start + MIN_CUE_DURATION_S
    if next_start is not None:
        room = next_start - INTER_CUE_GAP_S
        if room < end:
            room = next_start
        target = min(target, room)
    return max(end, target)


def _clipped_end(last_end: float, next_start: float | None) -> float:
    """Pad the last word, reserving the gap unless that would cut into speech."""
    padded = last_end + TRAILING_PADDING_S
    if next_start is None:
        return padded
    room = next_start - INTER_CUE_GAP_S
    if room >= last_end:
        return min(padded, room)
    return min(padded, next_start)


def _ends_sentence(text: str) -> bool:
    return _last_significant(text) in _SENTENCE_END


def _ends_clause(text: str) -> bool:
    return _last_significant(text) in _CLAUSE_END


def _last_significant(text: str) -> str:
    for character in reversed(text):
        if character not in _CLOSERS:
            return character
    return ""
