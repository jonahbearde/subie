"""Fakes for the single seam. Nothing here touches a GPU, a model or the network."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from subie.audio import Audio
from subie.deps import Deps, Transcriber
from subie.hardware import CudaLibrary, Hardware
from subie.media import MediaInfo
from subie.models import cache_path_for
from subie.transcript import Segment, Transcript, Word

#: A machine whose RTX 3070 Ti works: CUDA resolves and a device is visible.
GPU_READY = Hardware(
    gpu_names=("NVIDIA GeForce RTX 3070 Ti",),
    cuda_library_checks=(CudaLibrary("cuBLAS", True), CudaLibrary("cuDNN", True)),
    cuda_device_count=1,
    cuda_compute_types=("float16", "float32", "int8_float16"),
    cpu_compute_types=("float32", "int8", "int8_float32"),
)

#: A machine with no usable GPU at all and no CUDA libraries resolved.
CPU_ONLY = Hardware(cpu_compute_types=("float32", "int8", "int8_float32"))

#: CUDA resolves, but there is no device: the libraries are not the problem.
NO_GPU_LIBRARIES_OK = Hardware(
    cuda_library_checks=(CudaLibrary("cuBLAS", True), CudaLibrary("cuDNN", True)),
    cuda_device_count=0,
    cuda_compute_types=("float16", "float32", "int8_float16"),
    cpu_compute_types=("float32", "int8", "int8_float32"),
)

#: The dangerous case: a GPU the driver can see, whose CUDA libraries do not resolve.
GPU_UNUSABLE = Hardware(
    gpu_names=("NVIDIA GeForce GT 710",),
    cuda_library_checks=(
        CudaLibrary("cuBLAS", True),
        CudaLibrary(
            "cuDNN", False, "Could not load library cudnn_ops_infer64_8.dll. Error code 126"
        ),
    ),
    cuda_device_count=0,
    cpu_compute_types=("float32", "int8", "int8_float32"),
)

#: A GPU the driver can see, with cuDNN installed but cuBLAS missing: the
#: machine looks GPU-ready to CTranslate2 until inference actually starts.
GPU_MISSING_CUBLAS = Hardware(
    gpu_names=("NVIDIA GeForce RTX 3070 Ti",),
    cuda_library_checks=(
        CudaLibrary("cuBLAS", False, "Library cublas64_12.dll is not found or cannot be loaded"),
        CudaLibrary("cuDNN", True),
    ),
    cuda_device_count=1,
    cuda_compute_types=("float16", "int8_float16"),
    cpu_compute_types=("float32", "int8", "int8_float32"),
)


@dataclass
class FakeMediaProbe:
    info: MediaInfo = field(default_factory=lambda: MediaInfo(duration_s=0.1, has_audio=True))
    error: Exception | None = None
    by_name: dict[str, MediaInfo] = field(default_factory=dict)
    errors_by_name: dict[str, Exception] = field(default_factory=dict)
    seen: list[Path] = field(default_factory=list)

    def __call__(self, path: Path) -> MediaInfo:
        self.seen.append(path)
        if path.name in self.errors_by_name:
            raise self.errors_by_name[path.name]
        if self.error is not None:
            raise self.error
        return self.by_name.get(path.name, self.info)


@dataclass
class FakeDeviceProbe:
    hardware: Hardware = field(default_factory=Hardware)
    error: Exception | None = None

    def __call__(self) -> Hardware:
        if self.error is not None:
            raise self.error
        return self.hardware


class FakeTranscriber:
    """A Transcriber that returns a fixed Transcript and records the audio it saw.

    ``delay_s`` holds every call for a controlled time, so a test can force Jobs to
    overlap instead of racing the scheduler. ``in_flight`` and ``max_in_flight`` record
    how many calls were inside :meth:`transcribe` at once. A test that needs one Video
    to behave differently overrides :meth:`transcript_for`, which runs inside that same
    counted, delayed call.
    """

    def __init__(self, transcript: Transcript | None = None, *, delay_s: float = 0.0) -> None:
        self.transcript = transcript or Transcript(segments=())
        self.error: Exception | None = None
        self.delay_s = delay_s
        self.seen: list[Audio] = []
        self.in_flight = 0
        self.max_in_flight = 0
        self._lock = threading.Lock()

    def transcribe(self, audio: Audio) -> Transcript:
        with self._lock:
            self.seen.append(audio)
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            if self.delay_s:
                time.sleep(self.delay_s)
            if self.error is not None:
                raise self.error
            return self.transcript_for(audio)
        finally:
            with self._lock:
                self.in_flight -= 1

    def transcript_for(self, audio: Audio) -> Transcript:
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


def cached_model(cache: Path, repo_id: str, *, model_bytes: bytes = b"\0" * 4096) -> Path:
    """Write the files a finished download leaves in the cache, and return the snapshot."""
    snapshot = cache_path_for(repo_id, cache) / "snapshots" / ("0" * 40)
    snapshot.mkdir(parents=True, exist_ok=True)
    (snapshot / "config.json").write_text("{}", encoding="utf-8")
    (snapshot / "tokenizer.json").write_text("{}", encoding="utf-8")
    (snapshot / "model.bin").write_bytes(model_bytes)
    return snapshot


@dataclass
class FakeModelDownloader:
    """A network that always succeeds, unless it is told to fail for a model."""

    error: Exception | None = None
    errors_by_repo: dict[str, Exception] = field(default_factory=dict)
    model_bytes: bytes = b"\0" * 4096
    calls: list[tuple[str, Path]] = field(default_factory=list)

    def __call__(self, repo_id: str, *, destination: Path) -> None:
        self.calls.append((repo_id, destination))
        error = self.errors_by_repo.get(repo_id, self.error)
        if error is not None:
            raise error
        cached_model(destination, repo_id, model_bytes=self.model_bytes)


def make_deps(
    *,
    hardware: Hardware | None = None,
    device_probe: FakeDeviceProbe | None = None,
    media_probe: FakeMediaProbe | None = None,
    downloader: FakeModelDownloader | None = None,
    transcriber_factory: FakeTranscriberFactory | None = None,
) -> Deps:
    return Deps(
        probe=media_probe or FakeMediaProbe(),
        device=device_probe or FakeDeviceProbe(hardware or Hardware()),
        download_model=downloader or FakeModelDownloader(),
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
