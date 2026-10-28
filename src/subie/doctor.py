"""``subie doctor``: report whether this machine is ready, without downloading anything.

Every field is independent: a broken probe or an unreadable GPU must not hide the rest
of the report, and no failure is allowed to become a stack trace.
"""

from __future__ import annotations

import platform
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

from subie import models
from subie.deps import Deps, MediaProbe
from subie.errors import one_line
from subie.exit_codes import EXIT_FAILED, EXIT_OK
from subie.hardware import (
    CudaLibrary,
    Device,
    Hardware,
    cuda_library_versions,
    resolve_device,
)
from subie.media import ffmpeg_summary
from subie.models import Model


@dataclass(frozen=True)
class Diagnosis:
    """Doctor's verdict and the lines to print, in order."""

    exit_code: int
    lines: tuple[str, ...]


def diagnose(
    deps: Deps, *, requested_device: str = "auto", requested_model: Model | None = None
) -> Diagnosis:
    fields: list[tuple[str, str]] = []
    failures: list[str] = []

    fields.append(("python", f"{platform.python_version()} ({platform.python_implementation()})"))

    ffmpeg, ffmpeg_ok = _ffmpeg_line()
    fields.append(("ffmpeg", ffmpeg))
    if not ffmpeg_ok:
        failures.append("the bundled FFmpeg is unavailable")

    media_probe, media_ok = _media_probe_line(deps.probe)
    fields.append(("media probe", media_probe))
    if not media_ok:
        failures.append("the media probe failed")

    hardware: Hardware | None = None
    hardware_error: str | None = None
    try:
        hardware = deps.device()
    except Exception as exc:
        hardware_error = one_line(exc)

    chosen = None
    if hardware_error is not None:
        fields.append(("device", "unknown"))
        fields.append(("gpu", "unknown"))
        fields.append(("cuda libraries", "unknown"))
        fields.append(("compute type", "unknown"))
        failures.append(f"device probe failed: {hardware_error}")
    else:
        assert hardware is not None
        chosen = resolve_device(hardware, requested_device)
        fields.append(("device", chosen.name))
        fields.append(("gpu", _gpu_line(hardware)))
        fields.append(("cuda libraries", _cuda_line(hardware)))
        fields.append(("compute type", chosen.compute_type))
        if not chosen.usable:
            reason = chosen.reason or "it cannot be used"
            failures.append(f"CUDA was requested but is not usable: {reason}")

    model_device = chosen.name if chosen is not None else "cpu"
    if requested_model is not None:
        model_line = f"{requested_model.name} (requested)"
    else:
        model_line = f"{models.default_for(model_device).name} (default for {model_device})"
    fields.append(("model", model_line))
    fields.append(("model cache", str(models.models_dir())))
    fields.append(("models present", _models_present_line()))

    ready = not failures and chosen is not None and chosen.usable
    fields.append(("result", _result_line(failures, chosen, hardware, requested_device)))
    return Diagnosis(EXIT_OK if ready else EXIT_FAILED, _render(fields))


def _ffmpeg_line() -> tuple[str, bool]:
    try:
        return ffmpeg_summary(), True
    except Exception as exc:
        return f"unavailable: {one_line(exc)}", False


def _media_probe_line(probe: MediaProbe) -> tuple[str, bool]:
    """Probe a generated clip, so the media stack is exercised rather than assumed."""
    try:
        with tempfile.TemporaryDirectory(prefix="subie-doctor-") as directory:
            sample = Path(directory) / "sample.wav"
            _write_test_clip(sample)
            info = probe(sample)
    except Exception as exc:
        return f"failed: {one_line(exc)}", False
    if not info.has_audio:
        return "failed: the test clip was read but has no audio stream", False
    duration = f"{info.duration_s:.2f} s " if info.duration_s is not None else ""
    return f"ok: read a {duration}test clip with an audio stream", True


def _write_test_clip(path: Path) -> None:
    """A tenth of a second of 16 kHz mono silence, in the simplest container there is."""
    with wave.open(str(path), "wb") as clip:
        clip.setnchannels(1)
        clip.setsampwidth(2)
        clip.setframerate(16_000)
        clip.writeframes(b"\x00\x00" * 1_600)


def _gpu_line(hardware: Hardware) -> str:
    if hardware.gpu_names:
        names = ", ".join(hardware.gpu_names)
        return names if hardware.cuda_usable else f"{names} - not usable"
    if hardware.cuda_usable:
        return "CUDA device visible (name unavailable)"
    return "none visible"


def _cuda_line(hardware: Hardware) -> str:
    if hardware.cuda_library_checks:
        parts = [_library_line(library) for library in hardware.cuda_library_checks]
        if hardware.cuda_error:
            parts.append(f"CTranslate2: {hardware.cuda_error}")
        return "; ".join(parts)
    if hardware.gpu_names:
        return f"not resolved: {hardware.cuda_library_error or 'reason unknown'}"
    return "not needed (no GPU visible)"


def _library_line(library: CudaLibrary) -> str:
    if library.resolved:
        version = _library_version(library.name)
        return f"{library.name} resolved" + (f" ({version})" if version else "")
    return f"{library.name} not resolved ({library.detail or 'reason unknown'})"


def _library_version(name: str) -> str | None:
    return cuda_library_versions().get(name)


def _models_present_line() -> str:
    try:
        present = models.present_models()
    except Exception as exc:
        return f"unavailable: {one_line(exc)}"
    return ", ".join(model.name for model in present) or "none"


def _result_line(
    failures: list[str],
    chosen: Device | None,
    hardware: Hardware | None,
    requested_device: str,
) -> str:
    if failures:
        return "not ready: " + "; ".join(failures)
    assert chosen is not None and hardware is not None
    if chosen.name == "cuda":
        return "ready: the GPU path is usable"
    if hardware.gpu_names and not hardware.cuda_usable:
        return "ready: CPU path (GPU not usable)"
    if requested_device == "cpu" and hardware.cuda_usable:
        return "ready: CPU path (requested)"
    return "ready: CPU path"


def _render(fields: list[tuple[str, str]]) -> tuple[str, ...]:
    width = max(len(label) for label, _ in fields)
    lines = ["subie doctor", ""]
    lines.extend(f"  {label:<{width}}  {value}" for label, value in fields)
    return tuple(lines)
