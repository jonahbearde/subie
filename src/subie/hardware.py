"""What the machine can do: visible GPUs, whether CUDA resolves, compute types.

Two independent facts decide the GPU path: whether the driver exposes a GPU at all, and
whether the CUDA libraries CTranslate2 needs actually load. Keeping them apart is the
point of this module: a visible GPU with broken libraries is not a usable GPU, and a
machine with no GPU has not "failed to resolve" anything.
"""

from __future__ import annotations

import contextlib
import importlib.metadata
import importlib.util
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from subie.errors import one_line

#: Compute types preferred for CUDA, best first. float16 is the documented default.
CUDA_COMPUTE_TYPES = ("float16", "int8_float16", "float32")

#: Compute types preferred for CPU, best first. int8 is the documented default.
CPU_COMPUTE_TYPES = ("int8", "int8_float32", "float32")

_LIBRARY_PATTERN = re.compile(r"[A-Za-z0-9_.+\-]+\.(?:dll|so(?:\.\d+)*|dylib)", re.IGNORECASE)

_NVIDIA_PIP_PACKAGES = {
    "cuBLAS": "nvidia-cublas-cu12",
    "cuDNN": "nvidia-cudnn-cu12",
}

_NVIDIA_NAMESPACES = ("nvidia.cublas", "nvidia.cudnn")


@dataclass(frozen=True)
class Hardware:
    """The machine's GPU situation, as observed rather than assumed.

    ``cuda_libraries_ok`` and ``cuda_device_count`` are deliberately separate facts:
    libraries can resolve on a machine with no GPU, and a GPU can be visible to the
    driver while the libraries it needs fail to load.
    """

    #: Names of GPUs the driver reports, even when CUDA cannot be used.
    gpu_names: tuple[str, ...] = ()
    #: True when CTranslate2 could load its CUDA libraries.
    cuda_libraries_ok: bool = False
    #: One-line reason the CUDA libraries did not resolve.
    cuda_library_error: str | None = None
    #: CUDA devices CTranslate2 can see.
    cuda_device_count: int = 0
    #: Compute types CTranslate2 supports on CUDA; empty when unknown.
    cuda_compute_types: tuple[str, ...] = ()
    #: Compute types CTranslate2 supports on CPU; empty when unknown.
    cpu_compute_types: tuple[str, ...] = ()

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
    libraries_ok, library_error, device_count, cuda_types = _probe_cuda()
    return Hardware(
        gpu_names=_gpu_names(),
        cuda_libraries_ok=libraries_ok,
        cuda_library_error=library_error,
        cuda_device_count=device_count,
        cuda_compute_types=cuda_types,
        cpu_compute_types=_supported_compute_types("cpu"),
    )


def missing_library_from(message: str) -> str | None:
    """The shared library named in a loader error, if it names one."""
    match = _LIBRARY_PATTERN.search(message)
    return match.group(0) if match else None


def cuda_library_versions() -> tuple[str, ...]:
    """Versions of the CUDA runtime wheels installed via the ``cuda`` extra."""
    versions: list[str] = []
    for label, package in _NVIDIA_PIP_PACKAGES.items():
        try:
            versions.append(f"{label} {importlib.metadata.version(package)}")
        except importlib.metadata.PackageNotFoundError:
            continue
    return tuple(versions)


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


def _probe_cuda() -> tuple[bool, str | None, int, tuple[str, ...]]:
    """Return (libraries resolved, library error, device count, compute types)."""
    try:
        import ctranslate2
    except Exception as exc:
        return False, f"ctranslate2 is unavailable: {one_line(exc)}", 0, ()

    try:
        compute_types = tuple(sorted(ctranslate2.get_supported_compute_types("cuda")))
    except Exception as exc:
        return False, one_line(exc), 0, ()

    try:
        device_count = int(ctranslate2.get_cuda_device_count())
    except Exception:
        # The libraries resolved; a failed device query means no usable device.
        device_count = 0
    return True, None, device_count, compute_types


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
