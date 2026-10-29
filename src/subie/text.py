"""Cue text: what a Sidecar shows, given what the engine heard.

The rules are stated in ``docs/subtitle-policy.md``; nothing here knows about timing,
confidence or the file format.
"""

from __future__ import annotations

import re
from collections.abc import Collection

#: Characters that carry no speech. A Cue made of nothing else is dropped.
MUSIC_NOTES = frozenset("♪♫♬♩♭♮♯")

#: Tokens the engine writes with a capital wherever they sit, so a Fragment keeps them.
#: The pronoun and its contractions are always here; proper nouns join per Transcript.
ALWAYS_CAPITALIZED: frozenset[str] = frozenset(
    {"I", "I'm", "I've", "I'll", "I'd", "I’m", "I’ve", "I’ll", "I’d"}
)

_SENTENCE_END = frozenset(".?!")
_CLAUSE_END = frozenset(",;:")
_CLOSERS = frozenset("\"')]}\u2019\u201d\u00bb")
_SPACE = re.compile(r"\s+")
_SPACE_BEFORE_PUNCTUATION = re.compile(r"\s+([,.;:?!…%])")
_BRACKETED_MARKER = re.compile(r"\[[^\]]*\]")
_ONLY_MARKERS = re.compile(r"(?:\[[^\]]*\]\s*)+")
_WORD = re.compile(r"[^\W_]+(?:['\u2019][^\W_]+)*")
_TERMINAL = frozenset(".?!…")
_REPLACEABLE = frozenset(",;:-" + "\u2013\u2014")


def ends_sentence(text: str) -> bool:
    """True when the token ends a sentence, ignoring any closing quote."""
    return _last_significant(text) in _SENTENCE_END


def ends_clause(text: str) -> bool:
    """True when the token ends a clause, ignoring any closing quote."""
    return _last_significant(text) in _CLAUSE_END


def is_music_only(text: str) -> bool:
    """True when the text is music notes and nothing else."""
    stripped = text.strip()
    return bool(stripped) and all(
        character in MUSIC_NOTES or character.isspace() for character in stripped
    )


def is_bracketed(text: str) -> bool:
    """True when the whole text is one or more ``[bracketed]`` non-speech markers."""
    stripped = text.strip()
    return bool(stripped) and _ONLY_MARKERS.fullmatch(stripped) is not None


def normalize(
    text: str,
    *,
    begins_sentence: bool = True,
    ends_sentence: bool = True,
    keep_capitals: Collection[str] = (),
) -> str | None:
    """The text a Cue shows, or ``None`` when it shows nothing at all.

    ``begins_sentence`` and ``ends_sentence`` say whether the Cue's word range opens and
    closes its Sentence; a Cue that does neither edge of a Sentence is a Fragment and is
    neither capitalized nor terminated. ``keep_capitals`` names the tokens the Transcript
    itself capitalizes mid-Sentence, which a Fragment leaves alone.
    """
    collapsed = _collapse(text)
    if not collapsed or is_music_only(collapsed):
        return None
    if is_bracketed(collapsed):
        # A marker is not a sentence: it is shown as the engine wrote it.
        return collapsed
    speech = _collapse(_BRACKETED_MARKER.sub(" ", collapsed))
    if not speech or is_music_only(speech):
        return None
    speech = _capitalized(speech) if begins_sentence else lowercase_start(speech, keep_capitals)
    return _terminated(speech) if ends_sentence else _unterminated(speech)


def token(text: str) -> str:
    """The first word-shaped token in ``text``, apostrophes inside it kept."""
    match = _WORD.search(text)
    return match.group(0) if match else ""


def final_token(text: str) -> str:
    """The last word-shaped token in ``text``, punctuation around it discarded."""
    matches = _WORD.findall(text)
    return matches[-1] if matches else ""


def lowercase_start(text: str, keep_capitals: Collection[str] = ()) -> str:
    """Lower the first letter, unless the token is one the Transcript capitalizes.

    A token that starts with a digit has no letter to lower, and a token that is entirely
    uppercase is left as written.
    """
    for index, character in enumerate(text):
        if character.isdigit():
            return text
        if character.isalpha():
            candidate = token(text)
            if candidate in keep_capitals or candidate.isupper():
                return text
            return text[:index] + character.lower() + text[index + 1 :]
    return text


def strip_terminal_stop(text: str) -> str:
    """Remove a Sentence's terminal punctuation, keeping any closing quotes."""
    body, closers = _split_closers(text)
    while body and body[-1] in _TERMINAL:
        body = body[:-1]
    return f"{body}{closers}"


def _collapse(text: str) -> str:
    return _SPACE_BEFORE_PUNCTUATION.sub(r"\1", _SPACE.sub(" ", text)).strip()


def _capitalized(text: str) -> str:
    """Uppercase the Cue's first letter, leaving the engine's remaining casing alone.

    Leading punctuation and quotes are stepped over; a Cue that starts with a digit has
    no lowercase start to fix and is returned untouched.
    """
    for index, character in enumerate(text):
        if character.isdigit():
            return text
        if character.isalpha():
            return text[:index] + character.upper() + text[index + 1 :]
    return text


def _terminated(text: str) -> str:
    """Ensure the Cue ends in terminal punctuation, inside any closing quotes."""
    body, closers = _split_closers(text)
    if not body or body[-1] in _TERMINAL:
        return text
    if body[-1] in _REPLACEABLE:
        body = body[:-1]
    return f"{body}.{closers}"


def _unterminated(text: str) -> str:
    """A Fragment adds no stop, and drops the clause punctuation a cut left dangling."""
    body, closers = _split_closers(text)
    while body and body[-1] in _REPLACEABLE:
        body = body[:-1]
    return f"{body}{closers}"


def _split_closers(text: str) -> tuple[str, str]:
    index = len(text)
    while index and text[index - 1] in _CLOSERS:
        index -= 1
    return text[:index], text[index:]


def _last_significant(text: str) -> str:
    for character in reversed(text):
        if character not in _CLOSERS:
            return character
    return ""
