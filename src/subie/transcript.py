"""The engine's raw output: a Transcript, never shown to a user directly.

The Cue list is derived from this, so the recogniser's segment boundaries are input to
segmentation rather than the thing written to a Sidecar.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Word:
    """One recognised word with its timing and confidence."""

    start: float
    end: float
    text: str
    probability: float | None = None


@dataclass(frozen=True)
class Confidence:
    """The engine's own doubt about a Segment, where ``None`` means it reported nothing."""

    avg_logprob: float | None = None
    no_speech_prob: float | None = None


@dataclass(frozen=True)
class Segment:
    """One engine segment, including the words that made it up."""

    start: float
    end: float
    text: str
    words: tuple[Word, ...] = ()
    avg_logprob: float | None = None
    no_speech_prob: float | None = None

    @property
    def confidence(self) -> Confidence:
        """This Segment's doubt, as the hallucination blocklist reads it."""
        return Confidence(avg_logprob=self.avg_logprob, no_speech_prob=self.no_speech_prob)


@dataclass(frozen=True)
class Transcript:
    """Everything the engine heard in one Video."""

    segments: tuple[Segment, ...]
