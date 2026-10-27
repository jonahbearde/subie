"""Recognition: faster-whisper in-process, English-only, never a subprocess."""

from __future__ import annotations

from typing import Any

from subie.audio import Audio
from subie.models import models_dir
from subie.transcript import Segment, Transcript, Word

#: English-only and transcription-only are code constants, not options (ADR-0003).
LANGUAGE = "en"
TASK = "transcribe"

#: Hallucination guards and word timings are fixed for every run (docs/subtitle-policy.md).
VAD_FILTER = True
CONDITION_ON_PREVIOUS_TEXT = False
WORD_TIMESTAMPS = True


class FasterWhisperTranscriber:
    """Adapt faster-whisper's generator API to the Transcript the pipeline understands."""

    def __init__(self, engine: Any) -> None:
        self._engine = engine

    def transcribe(self, audio: Audio) -> Transcript:
        segments, _info = self._engine.transcribe(
            audio.samples,
            language=LANGUAGE,
            task=TASK,
            vad_filter=VAD_FILTER,
            condition_on_previous_text=CONDITION_ON_PREVIOUS_TEXT,
            word_timestamps=WORD_TIMESTAMPS,
            log_progress=False,
        )
        return Transcript(segments=tuple(_segment(segment) for segment in segments))


def make_transcriber(model: str, *, device: str, compute_type: str) -> FasterWhisperTranscriber:
    """Build a faster-whisper engine for a resolved model id, device and compute type.

    ``model`` is a Hugging Face repo id from :mod:`subie.models`, never a user-facing
    name. The model is downloaded into :func:`subie.models.models_dir` on first use.
    """
    from faster_whisper import BatchedInferencePipeline, WhisperModel

    whisper = WhisperModel(
        model,
        device=device,
        compute_type=compute_type,
        download_root=str(models_dir()),
    )
    # Batching is what makes a GPU run finish in well under real time (ADR-0002);
    # the CPU path keeps the simpler single-stream pipeline.
    engine = BatchedInferencePipeline(whisper) if device == "cuda" else whisper
    return FasterWhisperTranscriber(engine)


def _segment(segment: Any) -> Segment:
    words = tuple(
        Word(
            start=word.start,
            end=word.end,
            text=word.word,
            probability=getattr(word, "probability", None),
        )
        for word in (segment.words or ())
    )
    return Segment(
        start=segment.start,
        end=segment.end,
        text=segment.text,
        words=words,
        avg_logprob=getattr(segment, "avg_logprob", None),
        no_speech_prob=getattr(segment, "no_speech_prob", None),
    )
