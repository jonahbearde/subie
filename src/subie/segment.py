"""Readability segmentation: a pure function from a Transcript to Cues.

A Sentence is the unit a Cue is built from, so the engine's Segment boundaries never bear
on where a Cue starts or ends. The limits and the construction rules live in
``docs/subtitle-policy.md``; this module carries the values, not another explanation of
them. It does no I/O, touches no model and reads no clock, so the same Transcript always
produces the same Cue list.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace

from subie.guard import SENTENCE_FINAL_IMPOSSIBILITIES, is_phantom
from subie.text import (
    ALWAYS_CAPITALIZED,
    ends_clause,
    ends_sentence,
    final_token,
    is_bracketed,
    is_music_only,
    lowercase_start,
    normalize,
    strip_terminal_stop,
    token,
)
from subie.transcript import Confidence, Transcript

#: Readability limits. docs/subtitle-policy.md is the reference for their meaning.
MAX_LINE_CHARS = 90
MAX_LINES_PER_CUE = 1
MAX_READING_CPS = 20.0
MIN_CUE_DURATION_S = 1.0
MAX_CUE_DURATION_S = 7.0
TRAILING_PADDING_S = 0.2
INTER_CUE_GAP_S = 0.1
SENTENCE_PAUSE_S = 0.5
RESCUE_MIN_CHARS = 40
RESCUE_MIN_SPEECH_S = 1.0

#: The shorter half of a cut must be at least this fraction of the longer half, except
#: when the cut lands on a Sentence end.
MIN_CUT_BALANCE = 0.5


@dataclass(frozen=True)
class Cue:
    """One on-screen subtitle event: a start, an end, and one line of text."""

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


@dataclass(frozen=True)
class _Context:
    """Where each word sits in its Sentence, and the capitals the engine vouched for."""

    sentence_starts: frozenset[int]
    sentence_ends: frozenset[int]
    capitals: frozenset[str]


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

    capitals = _capitals(words, _sentences(words))
    words, sentences = _repaired(words, capitals)
    context = _context(sentences, capitals)

    cues: list[Cue] = []
    for first, last in _cue_groups(words, sentences, context):
        text = _display(words, first, last, context)
        if text is None:
            continue
        cues.append(
            Cue(
                start=words[first].start,
                end=_timed_end(words, first, last),
                text=text,
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


def _repaired(
    words: tuple[_Spoken, ...], capitals: frozenset[str]
) -> tuple[tuple[_Spoken, ...], list[tuple[int, int]]]:
    """Join Sentences the engine ended on a word no Sentence can end on.

    The stop after such a word is provably the engine's mistake, so it disappears, the
    following word loses the capital the engine gave it, and the joined range is laid out
    by the normal rules. A lone marker is never taken in: it is not part of the thought.
    """
    sentences = _sentences(words)
    repaired: list[_Spoken] = list(words)
    joined: list[tuple[int, int]] = []
    index = 0
    while index < len(sentences):
        first, last = sentences[index]
        while index + 1 < len(sentences) and not repaired[last].standalone:
            next_first, next_last = sentences[index + 1]
            if repaired[next_first].standalone or not _spurious_stop(repaired[last].text):
                break
            repaired[last] = replace(
                repaired[last],
                text=strip_terminal_stop(repaired[last].text),
            )
            repaired[next_first] = replace(
                repaired[next_first],
                text=lowercase_start(repaired[next_first].text, capitals),
            )
            last = next_last
            index += 1
        joined.append((first, last))
        index += 1
    return tuple(repaired), joined


def _spurious_stop(text: str) -> bool:
    """True when a Sentence's lone reason to end is a word no Sentence can end on."""
    return ends_sentence(text) and final_token(text).casefold() in SENTENCE_FINAL_IMPOSSIBILITIES


def _capitals(words: tuple[_Spoken, ...], sentences: list[tuple[int, int]]) -> frozenset[str]:
    """The tokens the engine itself capitalizes away from a Sentence start.

    Those are its confident proper nouns, plus the pronoun ``I`` and its contractions,
    which are always kept whatever the Transcript happens to contain.
    """
    capitals = set(ALWAYS_CAPITALIZED)
    for first, last in sentences:
        for word in words[first + 1 : last + 1]:
            candidate = token(word.text)
            if candidate and candidate[0].isupper():
                capitals.add(candidate)
    return frozenset(capitals)


def _context(sentences: list[tuple[int, int]], capitals: frozenset[str]) -> _Context:
    return _Context(
        sentence_starts=frozenset(first for first, _ in sentences),
        sentence_ends=frozenset(last for _, last in sentences),
        capitals=capitals,
    )


def _cue_groups(
    words: tuple[_Spoken, ...], sentences: list[tuple[int, int]], context: _Context
) -> list[tuple[int, int]]:
    """Choose inclusive word ranges for Cues, then split the ones over a limit.

    Grouping is one Sentence per Cue. Merging survives only as a rescue for a Sentence too
    slight to read on its own, and as the way out of a Sentence with too little screen time
    to reach the minimum. The phantom-phrase guard runs on each Sentence before any
    merging, so a doubtful invention is dropped on its own and never takes confident speech
    with it.
    """
    kept = [
        (first, last) for first, last in sentences if not _invented(words, first, last, context)
    ]
    groups: list[tuple[int, int]] = []
    single: int | None = None
    index = 0
    while index < len(kept):
        first, last = kept[index]
        if index + 1 < len(kept):
            next_first, next_last = kept[index + 1]
            if _joins_forward(words, first, last, next_first, next_last, context):
                groups.append((first, next_last))
                single = None
                index += 2
                continue
        if _joins_backward(words, index, first, last, groups, single, context):
            groups[-1] = (groups[-1][0], last)
            single = None
            index += 1
            continue
        groups.append((first, last))
        single = index
        index += 1

    split: list[tuple[int, int]] = []
    for first, last in groups:
        split.extend(_halves(words, first, last, context))
    return split


def _joins_forward(
    words: tuple[_Spoken, ...],
    first: int,
    last: int,
    next_first: int,
    next_last: int,
    context: _Context,
) -> bool:
    """True when this Sentence should absorb the Sentence after it."""
    if words[first].standalone or words[next_first].standalone:
        return False
    return _absorbs(words, first, last, first, next_last, context)


def _joins_backward(
    words: tuple[_Spoken, ...],
    index: int,
    first: int,
    last: int,
    groups: list[tuple[int, int]],
    single: int | None,
    context: _Context,
) -> bool:
    """True when this Sentence should absorb the Sentence before it.

    Only an untouched single-Sentence Cue can be absorbed: a rescue never grows into three
    Sentences.
    """
    if not groups or single != index - 1:
        return False
    previous_first = groups[-1][0]
    if words[first].standalone or words[previous_first].standalone:
        return False
    return _absorbs(words, first, last, previous_first, last, context)


def _absorbs(
    words: tuple[_Spoken, ...],
    first: int,
    last: int,
    merged_first: int,
    merged_last: int,
    context: _Context,
) -> bool:
    """True when this Sentence takes a neighbour into its Cue, limits permitting."""
    if not _shows_a_second(words, first, last):
        return True
    return _is_slight(words, first, last, context) and _fits(
        words, merged_first, merged_last, context
    )


def _is_slight(words: tuple[_Spoken, ...], first: int, last: int, context: _Context) -> bool:
    """True when this Sentence is too short in text or in speech to stand on screen."""
    text = _display(words, first, last, context)
    if text is None:
        return False
    if len(text) <= RESCUE_MIN_CHARS:
        return True
    return words[last].end - words[first].start < RESCUE_MIN_SPEECH_S


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


def _display(words: tuple[_Spoken, ...], first: int, last: int, context: _Context) -> str | None:
    """The cleaned text this word range would show, or ``None`` if it shows nothing."""
    return normalize(
        _cue_text(words, first, last),
        begins_sentence=first in context.sentence_starts,
        ends_sentence=last in context.sentence_ends,
        keep_capitals=context.capitals,
    )


def _invented(words: tuple[_Spoken, ...], first: int, last: int, context: _Context) -> bool:
    """True when this sentence is an invention rather than something that was said."""
    text = _display(words, first, last, context)
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


def _fits(words: tuple[_Spoken, ...], first: int, last: int, context: _Context) -> bool:
    return _fits_text_and_duration(words, first, last, context) and _fits_reading_speed(
        words, first, last, context
    )


def _fits_text_and_duration(
    words: tuple[_Spoken, ...], first: int, last: int, context: _Context
) -> bool:
    text = _display(words, first, last, context)
    if text is None or len(text) > MAX_LINE_CHARS:
        return False
    duration = words[last].end + TRAILING_PADDING_S - words[first].start
    return duration <= MAX_CUE_DURATION_S


def _fits_reading_speed(
    words: tuple[_Spoken, ...], first: int, last: int, context: _Context
) -> bool:
    text = _display(words, first, last, context)
    if text is None:
        return False
    duration = _timed_end(words, first, last) - words[first].start
    if duration <= 0:
        return False
    return len(text) / duration <= MAX_READING_CPS


def _halves(
    words: tuple[_Spoken, ...], first: int, last: int, context: _Context
) -> list[tuple[int, int]]:
    """Halve a range over a limit until every part fits, or cannot be improved further."""
    if last <= first:
        return [(first, last)]
    if not _fits_text_and_duration(words, first, last, context):
        middle = _midpoint_break(words, first, last)
        return _halves(words, first, middle, context) + _halves(words, middle + 1, last, context)
    if _fits_reading_speed(words, first, last, context):
        return [(first, last)]
    cut = _readable_break(words, first, last, context)
    if cut is None:
        return [(first, last)]
    return [(first, cut), (cut + 1, last)]


def _readable_break(
    words: tuple[_Spoken, ...], first: int, last: int, context: _Context
) -> int | None:
    """The best cut that leaves two readable Cues, or ``None`` when no cut would."""
    candidates = [
        index
        for index in range(first, last)
        if _reads_well(words, first, index, context)
        and _reads_well(words, index + 1, last, context)
    ]
    if not candidates:
        return None
    return _strongest_boundary(words, first, last, candidates)


def _reads_well(words: tuple[_Spoken, ...], first: int, last: int, context: _Context) -> bool:
    """True when this range is both readable at its speed and on screen for a second."""
    return _shows_a_second(words, first, last) and _fits_reading_speed(words, first, last, context)


def _shows_a_second(words: tuple[_Spoken, ...], first: int, last: int) -> bool:
    """True when this range has enough screen time to reach the one-second minimum."""
    return _timed_end(words, first, last) - words[first].start >= MIN_CUE_DURATION_S


def _midpoint_break(words: tuple[_Spoken, ...], first: int, last: int) -> int:
    """The boundary nearest the middle, from the strongest class with one."""
    return _strongest_boundary(words, first, last, range(first, last))


def _strongest_boundary(
    words: tuple[_Spoken, ...], first: int, last: int, candidates: Iterable[int]
) -> int:
    """The strongest-class candidate nearest the character midpoint. Never mid-word.

    A Sentence end always wins, even when the two halves are badly unbalanced: a Fragment
    is better than a Cue that straddles two thoughts. Every other class must leave two
    halves of comparable size before it is used.
    """
    available = list(candidates)
    sentence_ends = [index for index in available if _ends_sentence_at(words, index)]
    if sentence_ends:
        return _nearest_midpoint(words, first, last, sentence_ends)

    balanced = [
        index
        for index in available
        if _balanced(_cue_text(words, first, index), _cue_text(words, index + 1, last))
    ]
    pool = balanced or available
    for applicable in _BOUNDARY_CLASSES:
        preferred = [index for index in pool if applicable(words, index)]
        if preferred:
            return _nearest_midpoint(words, first, last, preferred)
    return _nearest_midpoint(words, first, last, pool)


def _ends_sentence_at(words: tuple[_Spoken, ...], index: int) -> bool:
    return ends_sentence(words[index].text)


def _ends_clause_at(words: tuple[_Spoken, ...], index: int) -> bool:
    return ends_clause(words[index].text)


def _paused_at(words: tuple[_Spoken, ...], index: int) -> bool:
    return _pause_after(words, index)


#: Candidate split boundaries weaker than a Sentence end, strongest first.
_BOUNDARY_CLASSES: tuple[Callable[[tuple[_Spoken, ...], int], bool], ...] = (
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


def _balanced(left: str, right: str) -> bool:
    shorter, longer = sorted((len(left), len(right)))
    return longer == 0 or shorter >= MIN_CUT_BALANCE * longer


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
