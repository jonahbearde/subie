"""What the machine can do: visible GPUs, whether CUDA resolves, compute types.

Two independent facts decide the GPU path: whether the driver exposes a GPU at all, and
whether the CUDA libraries CTranslate2 needs actually load. Keeping them apart is the
point of this module: a visible GPU with broken libraries is not a usable GPU, and a
machine with no GPU has not "failed to resolve" anything.
"""

from __future__ import annotations

import contextlib
import ctypes
import importlib.metadata
import importlib.util
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from subie.errors import one_line

#: Compute types preferred for CUDA, best first. float16 is the documented default.
CUDA_COMPUTE_TYPES = ("float16", "int8_float16", "float32")

#: Compute types preferred for CPU, best first. int8 is the documented default.
CPU_COMPUTE_TYPES = ("int8", "int8_float32", "float32")

_NVIDIA_PIP_PACKAGES = {
    "cuBLAS": "nvidia-cublas-cu12",
    "cuDNN": "nvidia-cudnn-cu12",
}

_NVIDIA_NAMESPACES = ("nvidia.cublas", "nvidia.cudnn")


def _cuda_library_candidates() -> tuple[tuple[str, tuple[str, ...]], ...]:
    """The shared libraries CTranslate2 loads, by platform. Any candidate counts."""
    if sys.platform == "win32":
        return (
            ("cuBLAS", ("cublas64_12.dll", "cublas64_11.dll")),
            (
                "cuDNN",
                (
                    "cudnn_ops64_9.dll",
                    "cudnn_ops_infer64_9.dll",
                    "cudnn_ops_infer64_8.dll",
                ),
            ),
        )
    return (
        ("cuBLAS", ("libcublas.so.12", "libcublas.so.11")),
        (
            "cuDNN",
            ("libcudnn_ops.so.9", "libcudnn_ops_infer.so.9", "libcudnn_ops_infer.so.8"),
        ),
    )


@dataclass(frozen=True)
class CudaLibrary:
    """One shared library CTranslate2 needs, and whether it actually loaded."""

    name: str
    resolved: bool
    detail: str | None = None


@dataclass(frozen=True)
class Hardware:
    """The machine's GPU situation, as observed rather than assumed.

    ``cuda_libraries_ok`` and ``cuda_device_count`` are deliberately separate facts:
    libraries can resolve on a machine with no GPU, and a GPU can be visible to the
    driver while the libraries it needs fail to load.
    """

    #: Names of GPUs the driver reports, even when CUDA cannot be used.
    gpu_names: tuple[str, ...] = ()
    #: Per-library resolution, so doctor can name cuBLAS and cuDNN separately.
    cuda_library_checks: tuple[CudaLibrary, ...] = ()
    #: A CTranslate2 or driver failure that is not a missing shared library.
    cuda_error: str | None = None
    #: CUDA devices CTranslate2 can see.
    cuda_device_count: int = 0
    #: Compute types CTranslate2 supports on CUDA; empty when unknown.
    cuda_compute_types: tuple[str, ...] = ()
    #: Compute types CTranslate2 supports on CPU; empty when unknown.
    cpu_compute_types: tuple[str, ...] = ()

    @property
    def cuda_libraries_ok(self) -> bool:
        """True when every library CTranslate2 needs loaded and it reported no error."""
        return (
            bool(self.cuda_library_checks)
            and all(library.resolved for library in self.cuda_library_checks)
            and self.cuda_error is None
        )

    @property
    def cuda_library_error(self) -> str | None:
        """One line naming what stopped the CUDA libraries from working, if anything."""
        missing = [
            f"{library.name}: {library.detail}"
            for library in self.cuda_library_checks
            if not library.resolved
        ]
        if missing:
            return "; ".join(missing)
        return self.cuda_error

    @property
    def cuda_usable(self) -> bool:
        """A GPU is usable only when the libraries resolve *and* a device is visible."""
        return self.cuda_libraries_ok and self.cuda_device_count > 0


@dataclass(frozen=True)
class Device:
    """The device the tool would actually use, and why."""

    name: str
    compute_type: str
    usable: bool
    reason: str | None = None


def resolve_device(hardware: Hardware, requested: str = "auto") -> Device:
    """Choose the device for a run: CUDA when it works, CPU otherwise."""
    if requested == "cpu":
        return Device("cpu", _pick(CPU_COMPUTE_TYPES, hardware.cpu_compute_types, "int8"), True)
    if requested == "cuda":
        compute_type = _pick(CUDA_COMPUTE_TYPES, hardware.cuda_compute_types, "float16")
        if hardware.cuda_usable:
            return Device("cuda", compute_type, True)
        reason = hardware.cuda_library_error or "no CUDA device is visible to CTranslate2"
        return Device("cuda", compute_type, False, reason)
    if hardware.cuda_usable:
        compute_type = _pick(CUDA_COMPUTE_TYPES, hardware.cuda_compute_types, "float16")
        return Device("cuda", compute_type, True)
    return Device("cpu", _pick(CPU_COMPUTE_TYPES, hardware.cpu_compute_types, "int8"), True)


def probe_hardware() -> Hardware:
    """Inspect the machine. Never raises: failures become part of the result."""
    _register_nvidia_libraries()
    device_count, cuda_types, cuda_error = _probe_cuda()
    return Hardware(
        gpu_names=_gpu_names(),
        cuda_library_checks=_check_cuda_libraries(),
        cuda_error=cuda_error,
        cuda_device_count=device_count,
        cuda_compute_types=cuda_types,
        cpu_compute_types=_supported_compute_types("cpu"),
    )


def cuda_library_versions() -> dict[str, str]:
    """Versions of the CUDA runtime wheels installed via the ``cuda`` extra."""
    versions: dict[str, str] = {}
    for label, package in _NVIDIA_PIP_PACKAGES.items():
        try:
            versions[label] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            continue
    return versions


def _pick(preferred: tuple[str, ...], supported: tuple[str, ...], fallback: str) -> str:
    if not supported:
        return fallback
    for candidate in preferred:
        if candidate in supported:
            return candidate
    return fallback


def _supported_compute_types(device: str) -> tuple[str, ...]:
    try:
        import ctranslate2
    except Exception:
        return ()
    try:
        return tuple(sorted(ctranslate2.get_supported_compute_types(device)))
    except Exception:
        return ()


def _check_cuda_libraries() -> tuple[CudaLibrary, ...]:
    """Load each library CTranslate2 needs. A loadable file is the only proof."""
    checks: list[CudaLibrary] = []
    for name, candidates in _cuda_library_candidates():
        resolved, detail = _load_first(candidates)
        checks.append(CudaLibrary(name, resolved, detail))
    return tuple(checks)


def _load_first(candidates: tuple[str, ...]) -> tuple[bool, str | None]:
    first_error: str | None = None
    for candidate in candidates:
        try:
            _load_library(candidate)
        except OSError as exc:
            if first_error is None:
                first_error = one_line(exc)
            continue
        return True, None
    return False, first_error or f"{candidates[0]} is not found"


def _load_library(name: str) -> None:
    """Load one shared library by name, using the directories registered above."""
    if sys.platform == "win32":
        ctypes.WinDLL(name)
    else:
        ctypes.CDLL(name)


def _probe_cuda() -> tuple[int, tuple[str, ...], str | None]:
    """Return (device count, compute types, a CTranslate2 or driver error)."""
    try:
        import ctranslate2
    except Exception as exc:
        return 0, (), f"ctranslate2 is unavailable: {one_line(exc)}"

    cuda_error: str | None = None
    try:
        compute_types = tuple(sorted(ctranslate2.get_supported_compute_types("cuda")))
    except Exception as exc:
        compute_types = ()
        cuda_error = one_line(exc)

    try:
        device_count = int(ctranslate2.get_cuda_device_count())
    except Exception:
        # The driver-level query failed; no device is usable in practice.
        device_count = 0
    return device_count, compute_types, cuda_error


def _gpu_names() -> tuple[str, ...]:
    """Ask the driver which GPUs exist, independently of CUDA library resolution."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ()
    if result.returncode != 0:
        return ()
    return tuple(line.strip() for line in result.stdout.splitlines() if line.strip())


def _register_nvidia_libraries() -> None:
    """Make the pip-installed CUDA runtime findable before CTranslate2 is imported."""
    for namespace in _NVIDIA_NAMESPACES:
        try:
            spec = importlib.util.find_spec(namespace)
        except (ImportError, ValueError):
            continue
        if spec is None or not spec.submodule_search_locations:
            continue
        for location in spec.submodule_search_locations:
            base = Path(location)
            for candidate in (base / "bin", base / "lib"):
                if candidate.is_dir():
                    _add_dll_directory(candidate)


def _add_dll_directory(directory: Path) -> None:
    if sys.platform == "win32":
        with contextlib.suppress(OSError):
            os.add_dll_directory(str(directory))
    entries = os.environ.get("PATH", "").split(os.pathsep)
    if str(directory) not in entries:
        os.environ["PATH"] = f"{directory}{os.pathsep}{os.environ.get('PATH', '')}"
