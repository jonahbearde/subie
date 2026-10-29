"""Readability segmentation: a pure function from a Transcript to Cues.

A Sentence is the unit a Cue is built from: a run of words ending at terminal punctuation
or at a long enough silence. Two Sentences therefore never share a Cue unless one of them
is too slight to stand on screen alone, and a Sentence too long for one Cue is halved at the
boundary nearest its middle, again if a half is still too long.

The limits and the construction rules live in ``docs/subtitle-policy.md``; this module
carries the values, not another explanation of them. It does no I/O, touches no model and
reads no clock, so the same Transcript always produces the same Cue list.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from subie.guard import is_phantom
from subie.text import ends_clause, ends_sentence, is_bracketed, is_music_only, normalize
from subie.transcript import Confidence, Transcript

#: Readability limits. docs/subtitle-policy.md is the reference for their meaning.
MAX_LINE_CHARS = 42
MAX_LINES_PER_CUE = 2
MIN_LINE_BALANCE = 0.5
MAX_READING_CPS = 20.0
MIN_CUE_DURATION_S = 1.0
MAX_CUE_DURATION_S = 7.0
TRAILING_PADDING_S = 0.2
INTER_CUE_GAP_S = 0.1
SENTENCE_PAUSE_S = 0.5
RESCUE_MIN_CHARS = 15
RESCUE_MIN_SPEECH_S = 1.0


@dataclass(frozen=True)
class Cue:
    """One on-screen subtitle event: a start, an end, and at most two lines of text."""

    start: float
    end: float
    text: str


@dataclass(frozen=True)
class _Spoken:
    """A word, the confidence of the Segment it came from, and whether it stands alone.

    ``standalone`` marks a word the engine emitted as a marker-only Segment: a
    non-speech event of its own, which never merges into a neighbouring Cue.
    """

    start: float
    end: float
    text: str
    confidence: Confidence
    standalone: bool = False


def cues_from_transcript(transcript: Transcript) -> tuple[Cue, ...]:
    """Build the readable Cue list for a Transcript, one Sentence to a Cue.

    A Sentence too slight to stand on screen alone absorbs one neighbour, and a Sentence
    whose screen time is too short to reach the minimum joins one, so the Cue list reads
    as thoughts rather than as the engine's chunks. Every limit is measured against the
    Cue's *cleaned* text, so a Cue that cleaning lengthens is split rather than written
    oversized, and a Cue that ends up saying nothing is dropped.
    """
    words = _speech_words(transcript)
    if not words:
        return ()

    cues: list[Cue] = []
    for first, last in _cue_groups(words):
        text = _display(words, first, last)
        if text is None:
            continue
        cues.append(
            Cue(
                start=words[first].start,
                end=_timed_end(words, first, last),
                text="\n".join(_line_break(text)),
            )
        )
    return tuple(cues)


def _speech_words(transcript: Transcript) -> tuple[_Spoken, ...]:
    """Flatten the engine's segments into the word stream segmentation works on.

    A Segment without word timings still yields one word, so a Transcript from a source
    that omits them degrades to segment-shaped Cues instead of disappearing. Words that
    are nothing but music notes carry no speech and never enter the stream.
    """
    words: list[_Spoken] = []
    for segment in transcript.segments:
        confidence = segment.confidence
        if segment.words:
            spoken = [
                (word, text)
                for word in segment.words
                if (text := word.text.strip()) and not is_music_only(text)
            ]
            standalone = bool(spoken) and all(is_bracketed(text) for _, text in spoken)
            words.extend(
                _Spoken(
                    start=word.start,
                    end=word.end,
                    text=text,
                    confidence=confidence,
                    standalone=standalone,
                )
                for word, text in spoken
            )
            continue
        text = segment.text.strip()
        if text and not is_music_only(text):
            words.append(
                _Spoken(
                    start=segment.start,
                    end=segment.end,
                    text=text,
                    confidence=confidence,
                    standalone=is_bracketed(text),
                )
            )
    return tuple(words)


def _cue_groups(words: tuple[_Spoken, ...]) -> list[tuple[int, int]]:
    """Choose inclusive word ranges for Cues, then split the ones over a limit.

    Grouping is one Sentence per Cue. Merging survives only as a rescue for a Sentence too
    slight to read on its own, and as the way out of a Sentence with too little screen time
    to reach the minimum. The phantom-phrase guard runs on each Sentence before any
    merging, so a doubtful invention is dropped on its own and never takes confident speech
    with it.
    """
    sentences = [
        (first, last)
        for first, last in _sentences(words)
        if not _invented(words, first, last)
    ]
    groups: list[tuple[int, int]] = []
    sources: list[tuple[int, int]] = []
    index = 0
    while index < len(sentences):
        first, last = sentences[index]
        if index + 1 < len(sentences):
            next_first, next_last = sentences[index + 1]
            if _joins_forward(words, first, last, next_first, next_last):
                groups.append((first, next_last))
                sources.append((index, index + 1))
                index += 2
                continue
        if _joins_backward(words, index, first, last, groups, sources):
            groups[-1] = (groups[-1][0], last)
            sources[-1] = (sources[-1][0], index)
            index += 1
            continue
        groups.append((first, last))
        sources.append((index, index))
        index += 1

    split: list[tuple[int, int]] = []
    for first, last in groups:
        split.extend(_halves(words, first, last))
    return split


def _joins_forward(
    words: tuple[_Spoken, ...], first: int, last: int, next_first: int, next_last: int
) -> bool:
    """True when this Sentence should absorb the Sentence after it."""
    if words[first].standalone or words[next_first].standalone:
        return False
    if _is_flash(words, first, last):
        return True
    return _is_slight(words, first, last) and _fits(words, first, next_last)


def _joins_backward(
    words: tuple[_Spoken, ...],
    index: int,
    first: int,
    last: int,
    groups: list[tuple[int, int]],
    sources: list[tuple[int, int]],
) -> bool:
    """True when this Sentence should absorb the Sentence before it.

    Only an untouched single-Sentence Cue can be absorbed: a rescue never grows into three
    Sentences.
    """
    if not groups or sources[-1] != (index - 1, index - 1):
        return False
    previous_first = groups[-1][0]
    if words[first].standalone or words[previous_first].standalone:
        return False
    if _is_flash(words, first, last):
        return True
    return _is_slight(words, first, last) and _fits(words, previous_first, last)


def _is_slight(words: tuple[_Spoken, ...], first: int, last: int) -> bool:
    """True when this Sentence is too short in text or in speech to stand on screen."""
    text = _display(words, first, last)
    if text is None:
        return False
    if len(text) < RESCUE_MIN_CHARS:
        return True
    return words[last].end - words[first].start < RESCUE_MIN_SPEECH_S


def _is_flash(words: tuple[_Spoken, ...], first: int, last: int) -> bool:
    """True when the next word starts too soon for this Sentence to reach the minimum."""
    if last + 1 >= len(words):
        return False
    return words[last + 1].start - words[first].start < MIN_CUE_DURATION_S


def _sentences(words: tuple[_Spoken, ...]) -> list[tuple[int, int]]:
    """Inclusive word ranges: one Sentence each, and around lone markers.

    A long enough silence ends a Sentence just as terminal punctuation does, so speech the
    engine left unpunctuated still breaks at the pauses the speaker made.
    """
    ranges: list[tuple[int, int]] = []
    first = 0
    for last, word in enumerate(words):
        if word.standalone:
            if first < last:
                ranges.append((first, last - 1))
            ranges.append((last, last))
            first = last + 1
        elif ends_sentence(word.text) or _pause_after(words, last):
            ranges.append((first, last))
            first = last + 1
    if first < len(words):
        ranges.append((first, len(words) - 1))
    return ranges


def _pause_after(words: tuple[_Spoken, ...], index: int) -> bool:
    """True when the silence before the next word is long enough to end a Sentence."""
    if index + 1 >= len(words):
        return False
    return words[index + 1].start - words[index].end >= SENTENCE_PAUSE_S


def _display(words: tuple[_Spoken, ...], first: int, last: int) -> str | None:
    """The cleaned text this word range would show, or ``None`` if it shows nothing."""
    return normalize(_cue_text(words, first, last))


def _invented(words: tuple[_Spoken, ...], first: int, last: int) -> bool:
    """True when this sentence is an invention rather than something that was said."""
    text = _display(words, first, last)
    return text is not None and is_phantom(text, _confidence_of(words, first, last))


def _confidence_of(words: tuple[_Spoken, ...], first: int, last: int) -> Confidence:
    """The group's most generous reading: doubtful only when no part of it was sure."""
    confidences = [word.confidence for word in words[first : last + 1]]
    logprobs = [c.avg_logprob for c in confidences if c.avg_logprob is not None]
    no_speech = [c.no_speech_prob for c in confidences if c.no_speech_prob is not None]
    return Confidence(
        avg_logprob=max(logprobs) if logprobs else None,
        no_speech_prob=min(no_speech) if no_speech else None,
    )


def _fits(words: tuple[_Spoken, ...], first: int, last: int) -> bool:
    return _fits_text_and_duration(words, first, last) and _fits_reading_speed(words, first, last)


def _fits_text_and_duration(words: tuple[_Spoken, ...], first: int, last: int) -> bool:
    text = _display(words, first, last)
    if text is None or _layout(text) is None:
        return False
    duration = words[last].end + TRAILING_PADDING_S - words[first].start
    return duration <= MAX_CUE_DURATION_S


def _fits_reading_speed(words: tuple[_Spoken, ...], first: int, last: int) -> bool:
    text = _display(words, first, last)
    if text is None:
        return False
    duration = _timed_end(words, first, last) - words[first].start
    if duration <= 0:
        return False
    return len(text) / duration <= MAX_READING_CPS


def _halves(words: tuple[_Spoken, ...], first: int, last: int) -> list[tuple[int, int]]:
    """Recursive halving: cut near the middle until every part satisfies every limit.

    Character and duration limits are hard: a Cue that does not fit the screen cannot be
    shown at all. Reading speed yields to the one-second minimum, because halving cannot
    slow speech down: a range is only split for reading speed when the split actually
    leaves two Cues that are each readable and each on screen for a second. Speech that is
    already faster than the limit stays whole rather than being shredded into flashes.
    """
    if last <= first:
        return [(first, last)]
    if not _fits_text_and_duration(words, first, last):
        middle = _midpoint_break(words, first, last)
        return _halves(words, first, middle) + _halves(words, middle + 1, last)
    if _fits_reading_speed(words, first, last):
        return [(first, last)]
    cut = _readable_break(words, first, last)
    if cut is None:
        return [(first, last)]
    return [(first, cut), (cut + 1, last)]


def _readable_break(words: tuple[_Spoken, ...], first: int, last: int) -> int | None:
    """The best cut that leaves two readable Cues, or ``None`` when no cut would."""
    candidates = [
        index
        for index in range(first, last)
        if _reads_well(words, first, index) and _reads_well(words, index + 1, last)
    ]
    if not candidates:
        return None
    return _best_boundary(words, first, last, candidates)


def _reads_well(words: tuple[_Spoken, ...], first: int, last: int) -> bool:
    """True when this range is both readable at its speed and on screen for a second."""
    return _shows_a_second(words, first, last) and _fits_reading_speed(words, first, last)


def _shows_a_second(words: tuple[_Spoken, ...], first: int, last: int) -> bool:
    """True when this range has enough screen time to reach the one-second minimum."""
    return _timed_end(words, first, last) - words[first].start >= MIN_CUE_DURATION_S


def _midpoint_break(words: tuple[_Spoken, ...], first: int, last: int) -> int:
    """The boundary nearest the middle, from the strongest class that has a balanced one.

    A Sentence end outranks clause punctuation, which outranks a long pause, which
    outranks any word boundary — but a class only wins while its boundary still leaves two
    halves, not a Cue and a scrap. Whichever class wins, its boundary nearest the character
    midpoint is chosen. Never mid-word.
    """
    boundaries = list(range(first, last))
    for applicable in _BOUNDARY_CLASSES:
        preferred = [
            index
            for index in boundaries
            if applicable(words, index)
            and _balanced(_cue_text(words, first, index), _cue_text(words, index + 1, last))
        ]
        if preferred:
            return _nearest_midpoint(words, first, last, preferred)
    return _nearest_midpoint(words, first, last, boundaries)


def _best_boundary(
    words: tuple[_Spoken, ...], first: int, last: int, candidates: Iterable[int]
) -> int:
    """The strongest-class candidate nearest the character midpoint."""
    available = list(candidates)
    for applicable in _BOUNDARY_CLASSES:
        preferred = [index for index in available if applicable(words, index)]
        if preferred:
            return _nearest_midpoint(words, first, last, preferred)
    return _nearest_midpoint(words, first, last, available)


def _ends_sentence_at(words: tuple[_Spoken, ...], index: int) -> bool:
    return ends_sentence(words[index].text)


def _ends_clause_at(words: tuple[_Spoken, ...], index: int) -> bool:
    return ends_clause(words[index].text)


def _paused_at(words: tuple[_Spoken, ...], index: int) -> bool:
    return _pause_after(words, index)


#: Candidate split boundaries, strongest first.
_BOUNDARY_CLASSES: tuple[Callable[[tuple[_Spoken, ...], int], bool], ...] = (
    _ends_sentence_at,
    _ends_clause_at,
    _paused_at,
)


def _nearest_midpoint(
    words: tuple[_Spoken, ...], first: int, last: int, candidates: Iterable[int]
) -> int:
    """The candidate whose two halves differ least in characters."""

    def distance(index: int) -> tuple[int, int]:
        outer = len(_cue_text(words, first, index))
        inner = len(_cue_text(words, index + 1, last))
        return abs(outer - inner), index

    return min(candidates, key=distance)


def _cue_text(words: tuple[_Spoken, ...], first: int, last: int) -> str:
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
                not ends_sentence(tokens[index - 1]),
                not ends_clause(tokens[index - 1]),
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


def _timed_end(words: tuple[_Spoken, ...], first: int, last: int) -> float:
    """The Cue's out: padding, then the one-second minimum, then the inter-Cue gap.

    The minimum outranks the gap: when a Cue's padding cannot fill a second, ``out``
    advances toward the next word and the gap shrinks, possibly to nothing. ``out`` never
    passes the next word's start, so two Cues never overlap.
    """
    start = words[first].start
    next_start = words[last + 1].start if last + 1 < len(words) else None
    end = _clipped_end(words[last].end, next_start)
    if end - start >= MIN_CUE_DURATION_S:
        return end

    target = start + MIN_CUE_DURATION_S
    if next_start is not None:
        target = min(target, next_start)
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