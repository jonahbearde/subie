"""A silent WAV the real decoder can open; the fake engine ignores what it hears."""

from __future__ import annotations

import wave
from pathlib import Path


def write_wav(
    path: Path,
    *,
    seconds: float = 0.2,
    rate: int = 16_000,
    channels: int = 1,
) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * int(seconds * rate) * channels)
