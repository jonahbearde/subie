"""Helpers shared by the tests that drive a Run through the single seam.

A Run needs a folder of Videos, fakes for `deps`, and a Sidecar old enough to be skipped;
none of that is behaviour under test, so it lives here instead of being repeated per file.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from subie.deps import Deps
from subie.hardware import Hardware
from subie.transcript import Transcript
from tests.fakes import (
    CPU_ONLY,
    FakeMediaProbe,
    FakeTranscriber,
    FakeTranscriberFactory,
    make_deps,
    one_segment,
)
from tests.wav import write_wav


def deps(
    transcript: Transcript | None = None,
    *,
    hardware: Hardware = CPU_ONLY,
    media_probe: FakeMediaProbe | None = None,
    transcriber: FakeTranscriber | None = None,
) -> tuple[Deps, FakeTranscriberFactory, FakeTranscriber]:
    """Fakes for a Run, plus the factory and transcriber a test may inspect."""
    transcriber = transcriber or FakeTranscriber(transcript or one_segment("Hello there."))
    factory = FakeTranscriberFactory(transcriber)
    deps = make_deps(
        hardware=hardware,
        media_probe=media_probe or FakeMediaProbe(),
        transcriber_factory=factory,
    )
    return deps, factory, transcriber


def folder_of_videos(parent: Path, count: int, *, seconds: float = 0.2) -> Path:
    """Create ``parent/Videos`` holding ``count`` short WAV Videos."""
    folder = parent / "Videos"
    folder.mkdir()
    for index in range(count):
        write_wav(folder / f"talk-{index}.wav", seconds=seconds)
    return folder


def make_fresh(video: Path, contents: bytes = b"old sidecar") -> Path:
    """Give ``video`` a Sidecar whose mtime is unambiguously newer."""
    sidecar = video.with_suffix(".srt")
    sidecar.write_bytes(contents)
    stamp = time.time_ns()
    os.utime(video, ns=(stamp, stamp))
    os.utime(sidecar, ns=(stamp + 1_000_000_000, stamp + 1_000_000_000))
    return sidecar
