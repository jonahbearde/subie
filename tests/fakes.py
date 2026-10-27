"""Fakes for the single seam. Nothing here touches a GPU, a model or the network."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from subie.audio import Audio
from subie.deps import Deps, Transcriber
from subie.hardware import Hardware
from subie.media import MediaInfo
from subie.transcript import Segment, Transcript, Word

#: A machine whose RTX 3070 Ti works: CUDA resolves and a device is visible.
GPU_READY = Hardware(
    gpu_names=("NVIDIA GeForce RTX 3070 Ti",),
    cuda_libraries_ok=True,
    cuda_device_count=1,
    cuda_compute_types=("float16", "float32", "int8_float16"),
    cpu_compute_types=("float32", "int8", "int8_float32"),
)

#: A machine with no usable GPU at all and no CUDA libraries resolved.
CPU_ONLY = Hardware(cpu_compute_types=("float32", "int8", "int8_float32"))

#: CUDA resolves, but there is no device: the libraries are not the problem.
NO_GPU_LIBRARIES_OK = Hardware(
    cuda_libraries_ok=True,
    cuda_device_count=0,
    cuda_compute_types=("float16", "float32", "int8_float16"),
    cpu_compute_types=("float32", "int8", "int8_float32"),
)

#: The dangerous case: a GPU the driver can see, whose CUDA libraries do not resolve.
GPU_UNUSABLE = Hardware(
    gpu_names=("NVIDIA GeForce GT 710",),
    cuda_libraries_ok=False,
    cuda_library_error="Could not load library cudnn_ops_infer64_8.dll. Error code 126",
    cuda_device_count=0,
    cpu_compute_types=("float32", "int8", "int8_float32"),
)


@dataclass
class FakeMediaProbe:
    info: MediaInfo = field(default_factory=lambda: MediaInfo(duration_s=0.1, has_audio=True))
    error: Exception | None = None
    seen: list[Path] = field(default_factory=list)

    def __call__(self, path: Path) -> MediaInfo:
        self.seen.append(path)
        if self.error is not None:
            raise self.error
        return self.info


@dataclass
class FakeDeviceProbe:
    hardware: Hardware = field(default_factory=Hardware)
    error: Exception | None = None

    def __call__(self) -> Hardware:
        if self.error is not None:
            raise self.error
        return self.hardware


class FakeTranscriber:
    """A Transcriber that returns a fixed Transcript and records the audio it saw."""

    def __init__(self, transcript: Transcript | None = None) -> None:
        self.transcript = transcript or Transcript(segments=())
        self.error: Exception | None = None
        self.seen: list[Audio] = []

    def transcribe(self, audio: Audio) -> Transcript:
        self.seen.append(audio)
        if self.error is not None:
            raise self.error
        return self.transcript


class FakeTranscriberFactory:
    """Builds a :class:`FakeTranscriber`; by default it refuses to build anything.

    Doctor must never construct the engine: doing so would download a model.
    """

    def __init__(
        self,
        transcriber: FakeTranscriber | None = None,
        error: Exception | None = None,
    ) -> None:
        self.transcriber = transcriber
        self.error = error
        self.calls: list[tuple[str, str, str]] = []

    def __call__(self, model: str, *, device: str, compute_type: str) -> Transcriber:
        self.calls.append((model, device, compute_type))
        if self.error is not None:
            raise self.error
        if self.transcriber is None:
            raise AssertionError("doctor must not construct a Transcriber")
        return self.transcriber


def make_deps(
    *,
    hardware: Hardware | None = None,
    device_probe: FakeDeviceProbe | None = None,
    media_probe: FakeMediaProbe | None = None,
    transcriber_factory: FakeTranscriberFactory | None = None,
) -> Deps:
    return Deps(
        probe=media_probe or FakeMediaProbe(),
        device=device_probe or FakeDeviceProbe(hardware or Hardware()),
        make_transcriber=transcriber_factory or FakeTranscriberFactory(),
    )


def one_segment(text: str = "Hello there.", *, start: float = 0.0, end: float = 1.5) -> Transcript:
    """The simplest Transcript for a Job test."""
    return Transcript(
        segments=(
            Segment(
                start=start,
                end=end,
                text=text,
                words=(Word(start=start, end=end, text=text),),
            ),
        )
    )
