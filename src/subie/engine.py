"""Recognition: faster-whisper in-process, English-only, never a subprocess."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from subie.audio import Audio
from subie.models import MODEL_FILES, model_cached, models_dir
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
    name. A model already in :func:`subie.models.models_dir` is used from there without
    touching the network, which is what makes ``subie models pull`` enough to prepare a
    machine for offline use.
    """
    from faster_whisper import BatchedInferencePipeline, WhisperModel

    whisper = WhisperModel(
        model,
        device=device,
        compute_type=compute_type,
        download_root=str(models_dir()),
        local_files_only=model_cached(model),
    )
    # Batching is what makes a GPU run finish in well under real time (ADR-0002);
    # the CPU path keeps the simpler single-stream pipeline.
    engine = BatchedInferencePipeline(whisper) if device == "cuda" else whisper
    return FasterWhisperTranscriber(engine)


def download_model(repo_id: str, *, destination: Path) -> None:
    """Fetch a model repository into the cache, with the downloader's own progress bars.

    The cache layout is Hugging Face's, because that is the layout
    :class:`faster_whisper.WhisperModel` reads from the same directory. Progress goes to
    stderr as the library prints it; nothing here has to know how large a model is.
    """
    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id,
        cache_dir=str(destination),
        allow_patterns=list(MODEL_FILES),
    )


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
