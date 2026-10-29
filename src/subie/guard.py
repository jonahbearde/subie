"""The hallucination blocklist: invented phrases, filtered only where the engine doubts them.

Whisper invents fluent text over music, silence and applause. The phrase list and the
thresholds are data, documented in ``docs/subtitle-policy.md``; changing one here is a
behaviour change, not a tweak.
"""

from __future__ import annotations

import re

from subie.transcript import Confidence

#: Phrases the engine invents when it hears no speech. Lowercase and unpunctuated:
#: a Cue matches when these words appear in it in this order, whatever the punctuation.
PHANTOM_PHRASES: tuple[str, ...] = (
    "thanks for watching",
    "thank you for watching",
    "thanks for watching and subscribing",
    "please subscribe",
    "subscribe to my channel",
    "like and subscribe",
    "see you in the next video",
)

#: Words no English Sentence ends on: articles, prepositions and conjunctions. A stop
#: after one of these is the engine's mistake, so it is removed and the thought rejoins.
SENTENCE_FINAL_IMPOSSIBILITIES: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "to",
        "by",
        "with",
        "from",
        "for",
        "in",
        "on",
        "at",
        "as",
        "into",
        "onto",
        "upon",
        "between",
        "against",
        "during",
        "within",
        "via",
        "per",
        "than",
        "and",
        "but",
        "or",
        "nor",
        "although",
        "unless",
        "whether",
        "whereas",
        "lest",
    }
)

#: A Segment is low confidence when its average log-probability is at most this.
LOW_AVG_LOGPROB = -1.0
#: A Segment is low confidence when its no-speech probability is at least this.
HIGH_NO_SPEECH_PROB = 0.6

_WORD = re.compile(r"[^\W_]+")
_PHANTOM_TOKENS: tuple[tuple[str, ...], ...] = tuple(
    tuple(word.casefold() for word in _WORD.findall(phrase)) for phrase in PHANTOM_PHRASES
)


def is_low_confidence(confidence: Confidence) -> bool:
    """True when the engine's own numbers say it was guessing."""
    if confidence.avg_logprob is not None and confidence.avg_logprob <= LOW_AVG_LOGPROB:
        return True
    return (
        confidence.no_speech_prob is not None and confidence.no_speech_prob >= HIGH_NO_SPEECH_PROB
    )


def is_phantom(text: str, confidence: Confidence) -> bool:
    """True when a low-confidence Cue says one of the phantom phrases."""
    if not is_low_confidence(confidence):
        return False
    tokens = tuple(word.casefold() for word in _WORD.findall(text))
    return any(_contains(tokens, phantom) for phantom in _PHANTOM_TOKENS)


def _contains(tokens: tuple[str, ...], phrase: tuple[str, ...]) -> bool:
    width = len(phrase)
    return any(tokens[start : start + width] == phrase for start in range(len(tokens) - width + 1))
