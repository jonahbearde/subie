"""Decode a Video's audio into memory: 16 kHz mono float32, via PyAV.

Nothing is written to disk unless the caller explicitly keeps a copy for debugging.
"""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from subie.errors import SubieError

SAMPLE_RATE = 16_000


class AudioError(SubieError):
    """A Video's audio could not be decoded."""


@dataclass(frozen=True)
class Audio:
    """Decoded audio, ready for recognition."""

    samples: np.ndarray
    sample_rate: int = SAMPLE_RATE

    @property
    def duration_s(self) -> float:
        return len(self.samples) / self.sample_rate


def decode_audio(path: Path) -> Audio:
    """Decode the first audio stream of a Video, resampled to 16 kHz mono float32."""
    try:
        import av
    except Exception as exc:  # pragma: no cover - installation damage
        raise AudioError(f"PyAV is unavailable: {exc}") from None

    try:
        with av.open(str(path), mode="r") as container:
            stream = next((s for s in container.streams if s.type == "audio"), None)
            if stream is None:
                raise AudioError(f"{path.name} has no audio stream")

            resampler = av.AudioResampler(format="flt", layout="mono", rate=SAMPLE_RATE)
            chunks: list[np.ndarray] = []
            for frame in container.decode(stream):
                chunks.extend(_resampled_chunks(resampler, frame))
            chunks.extend(_resampled_chunks(resampler, None))
    except AudioError:
        raise
    except av.error.FFmpegError as exc:
        raise AudioError(f"cannot decode audio from {path.name}: {exc}") from None
    except OSError as exc:
        raise AudioError(f"cannot open {path.name}: {exc.strerror or exc}") from None

    samples = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
    return Audio(samples=samples.astype(np.float32, copy=False))


def kept_audio_path(video: Path) -> Path:
    """Where ``--keep-audio`` keeps the decoded audio: beside the Video, clearly named.

    The suffix matches ``.gitignore`` so a debugging run cannot accidentally commit it.
    """
    candidate = video.with_name(f"{video.stem}.keep-audio.wav")
    if candidate == video:
        candidate = video.with_name(f"{video.name}.keep-audio.wav")
    return candidate


def write_wav(audio: Audio, path: Path) -> None:
    """Write decoded audio as a 16-bit PCM WAV that any player can open."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.rint(np.clip(audio.samples, -1.0, 1.0) * 32767.0).astype(np.int16)
    try:
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(audio.sample_rate)
            wav.writeframes(pcm.tobytes())
    except OSError as exc:
        raise AudioError(f"cannot keep audio at {path}: {exc.strerror or exc}") from None


def _resampled_chunks(resampler: Any, frame: Any | None) -> list[np.ndarray]:
    frames = resampler.resample(frame)
    return [f.to_ndarray().reshape(-1) for f in frames]
