"""Recognition: faster-whisper in-process, English-only, never a subprocess."""

from __future__ import annotations

from typing import Any

from subie.models import models_dir


def make_transcriber(model: str, *, device: str, compute_type: str) -> Any:
    """Build a faster-whisper engine for a resolved model id, device and compute type.

    ``model`` is a Hugging Face repo id from :mod:`subie.models`, never a user-facing
    name. The model is downloaded into :func:`subie.models.models_dir` on first use.
    """
    from faster_whisper import WhisperModel

    return WhisperModel(
        model,
        device=device,
        compute_type=compute_type,
        download_root=str(models_dir()),
    )
