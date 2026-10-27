"""Fakes for the single seam. Nothing here touches a GPU, a model or the network."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from subie.deps import Deps
from subie.hardware import Hardware
from subie.media import MediaInfo

#: A machine whose RTX 3070 Ti works: CUDA resolves and a device is visible.
GPU_READY = Hardware(
    gpu_names=("NVIDIA GeForce RTX 3070 Ti",),
    cuda_usable=True,
    cuda_compute_types=("float16", "float32", "int8_float16"),
    cpu_compute_types=("float32", "int8", "int8_float32"),
)

#: A machine with no usable GPU at all.
CPU_ONLY = Hardware(cpu_compute_types=("float32", "int8", "int8_float32"))

#: The dangerous case: a GPU the driver can see, whose CUDA libraries do not resolve.
GPU_UNUSABLE = Hardware(
    gpu_names=("NVIDIA GeForce GT 710",),
    cuda_usable=False,
    cuda_error="Could not load library cudnn_ops_infer64_8.dll. Error code 126",
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


class FakeTranscriberFactory:
    """Doctor must never build the engine: doing so would download a model."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def __call__(self, model: str, *, device: str, compute_type: str) -> object:
        self.calls.append((model, device, compute_type))
        raise AssertionError("doctor must not construct a Transcriber")


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
