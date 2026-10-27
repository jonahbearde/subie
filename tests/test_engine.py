"""The engine adapter: the options fixed in code, and the mapping to a Transcript."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np

from subie import engine, models
from subie.audio import Audio


class SpyWhisper:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    def transcribe(self, audio: Any, **kwargs: Any) -> tuple[list[Any], Any]:
        self.calls.append((audio, kwargs))
        segment = SimpleNamespace(
            start=0.25,
            end=1.75,
            text=" Hello there.",
            avg_logprob=-0.2,
            no_speech_prob=0.01,
            words=[SimpleNamespace(start=0.25, end=1.75, word=" Hello", probability=0.9)],
        )
        info = SimpleNamespace(language="en")
        return [segment], info


def test_recognition_options_are_fixed_in_code():
    spy = SpyWhisper()
    transcriber = engine.FasterWhisperTranscriber(spy)
    audio = Audio(samples=np.zeros(1600, dtype=np.float32))

    transcript = transcriber.transcribe(audio)

    _, kwargs = spy.calls[0]
    assert kwargs["language"] == "en"
    assert kwargs["task"] == "transcribe"
    assert kwargs["vad_filter"] is True
    assert kwargs["condition_on_previous_text"] is False
    assert kwargs["word_timestamps"] is True
    assert kwargs["log_progress"] is False
    assert transcript.segments[0].text == " Hello there."
    assert transcript.segments[0].words[0].text == " Hello"
    assert transcript.segments[0].words[0].probability == 0.9
    assert transcript.segments[0].avg_logprob == -0.2


def test_make_transcriber_passes_device_compute_type_and_the_one_model_cache(
    monkeypatch, subie_home
):
    import faster_whisper

    seen: dict[str, Any] = {}

    class RecordingModel:
        def __init__(self, model: str, **kwargs: Any) -> None:
            seen["model"] = model
            seen.update(kwargs)

    monkeypatch.setattr(faster_whisper, "WhisperModel", RecordingModel)

    engine.make_transcriber("Systran/faster-whisper-small.en", device="cpu", compute_type="int8")

    assert seen == {
        "model": "Systran/faster-whisper-small.en",
        "device": "cpu",
        "compute_type": "int8",
        "download_root": str(subie_home / "models"),
    }
    assert models.models_dir() == subie_home / "models"


def test_make_transcriber_uses_the_batched_pipeline_on_cuda(monkeypatch, subie_home):
    import faster_whisper

    class RecordingModel:
        def __init__(self, model: str, **kwargs: Any) -> None:
            self.model = model
            self.kwargs = kwargs

    created: dict[str, Any] = {}

    class RecordingBatched:
        def __init__(self, model: Any) -> None:
            created["batched"] = model

    monkeypatch.setattr(faster_whisper, "WhisperModel", RecordingModel)
    monkeypatch.setattr(faster_whisper, "BatchedInferencePipeline", RecordingBatched)

    engine.make_transcriber(
        "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
        device="cuda",
        compute_type="float16",
    )

    underlying = created["batched"]
    assert isinstance(underlying, RecordingModel)
    assert underlying.kwargs["device"] == "cuda"
    assert underlying.kwargs["download_root"] == str(subie_home / "models")
