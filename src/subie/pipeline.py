"""One Job: probe, decode, recognise, build Cues, write the Sidecar."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from subie.audio import decode_audio, kept_audio_path, write_wav
from subie.deps import Deps, Transcriber
from subie.errors import SubieError, one_line
from subie.hardware import resolve_device
from subie.media import MediaError
from subie.models import Model, default_for, load_error
from subie.segment import cues_from_transcript
from subie.srt import render_srt


class JobError(SubieError):
    """A Video could not be turned into a Sidecar."""


class JobSkipped(SubieError):
    """A Video produced no Sidecar, but nothing failed: there was no speech in it."""


@dataclass(frozen=True)
class RunSettings:
    """The model, device and compute type a Run resolves once for every Job."""

    model: Model
    device: str
    compute_type: str


@dataclass(frozen=True)
class JobResult:
    """What one successful Job produced, for the summary line."""

    video: Path
    sidecar: Path
    cues: int
    elapsed_s: float
    kept_audio: Path | None = None


def resolve_run_settings(
    deps: Deps,
    *,
    requested_device: str = "auto",
    requested_model: Model | None = None,
) -> RunSettings:
    """Choose the device and model for a Run, failing clearly if a forced device is dead."""
    hardware = deps.device()
    device = resolve_device(hardware, requested_device)
    if not device.usable:
        reason = device.reason or "it cannot be used"
        raise JobError(f"the {device.name} device is not usable: {reason}")
    model = requested_model or default_for(device.name)
    return RunSettings(model=model, device=device.name, compute_type=device.compute_type)


def validate_video(video: Path) -> None:
    """A Video must exist and be a file before any device or model work starts."""
    if not video.exists():
        raise JobError(f"video not found: {video}")
    if not video.is_file():
        raise JobError(f"not a Video file: {video}")


def run_job(
    video: Path,
    settings: RunSettings,
    deps: Deps,
    *,
    sidecar: Path | None = None,
    keep_audio: bool = False,
) -> JobResult:
    """Turn one Video into a Sidecar, or raise :class:`JobError` with a readable reason.

    A Video whose audio contains no speech raises :class:`JobSkipped` instead: no
    Sidecar is written, but the Run has not failed because of it.
    """
    validate_video(video)
    started = time.perf_counter()

    try:
        info = deps.probe(video)
    except MediaError:
        raise
    except Exception as exc:
        raise JobError(f"cannot read {video.name}: {one_line(exc)}") from None
    if not info.has_audio:
        raise JobError(f"{video.name} has no audio stream")

    audio = decode_audio(video)
    kept_audio: Path | None = None
    if keep_audio:
        kept_audio = kept_audio_path(video)
        write_wav(audio, kept_audio)

    transcriber = _build_transcriber(deps, settings)
    try:
        transcript = transcriber.transcribe(audio)
    except SubieError:
        raise
    except Exception as exc:
        raise JobError(f"recognition failed for {video.name}: {one_line(exc)}") from None

    cues = cues_from_transcript(transcript)
    if not cues:
        raise JobSkipped(f"no speech detected in {video.name}; no Sidecar written")

    sidecar = sidecar or video.with_suffix(".srt")
    if sidecar == video:
        raise JobError(f"refusing to overwrite {video.name}: the Sidecar would be the Video")
    try:
        sidecar.write_bytes(render_srt(cues))
    except OSError as exc:
        raise JobError(f"cannot write {sidecar}: {exc.strerror or exc}") from None

    return JobResult(
        video=video,
        sidecar=sidecar,
        cues=len(cues),
        elapsed_s=time.perf_counter() - started,
        kept_audio=kept_audio,
    )


def _build_transcriber(deps: Deps, settings: RunSettings) -> Transcriber:
    try:
        return deps.make_transcriber(
            settings.model.repo_id,
            device=settings.device,
            compute_type=settings.compute_type,
        )
    except Exception as exc:
        raise JobError(load_error(settings.model, exc)) from None
