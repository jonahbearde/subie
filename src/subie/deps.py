"""The single seam: everything a test may replace, and nothing else.

``run(argv, deps)`` is the public interface of the tool under test. ``deps`` carries
exactly the abilities that touch the outside world:

* ``probe`` — report a Video's duration and whether it has an audio stream.
* ``device`` — report the machine's visible GPUs and whether CUDA resolves.
* ``make_transcriber`` — build the recognition engine for a model and device.

Argument parsing, device and model resolution, recognition options, cue building,
normalization, SRT rendering, skip logic, output paths, exit codes, reporter output,
``doctor`` and ``models`` are real code under test.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from subie.audio import Audio
from subie.hardware import Hardware
from subie.media import MediaInfo
from subie.transcript import Transcript


class Transcriber(Protocol):
    """The recognition engine: audio in memory, a Transcript out."""

    def transcribe(self, audio: Audio) -> Transcript: ...


class MediaProbe(Protocol):
    def __call__(self, path: Path) -> MediaInfo: ...


class DeviceProbe(Protocol):
    def __call__(self) -> Hardware: ...


class TranscriberFactory(Protocol):
    def __call__(self, model: str, *, device: str, compute_type: str) -> Transcriber: ...


@dataclass(frozen=True)
class Deps:
    """The only thing replaced in tests."""

    probe: MediaProbe
    device: DeviceProbe
    make_transcriber: TranscriberFactory


def default_deps() -> Deps:
    """The real seams: PyAV, the machine's hardware, and faster-whisper."""
    from subie.engine import make_transcriber
    from subie.hardware import probe_hardware
    from subie.media import probe_media

    return Deps(
        probe=probe_media,
        device=probe_hardware,
        make_transcriber=make_transcriber,
    )
