"""The models the tool knows about, and the per-machine cache they live in.

The cache location reported by ``subie doctor``, used by ``subie models`` and used by a
Run must all be this one directory.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from subie.errors import one_line


@dataclass(frozen=True)
class Model:
    """A recognisable name and the CTranslate2 model it resolves to."""

    name: str
    repo_id: str


#: English-capable models, smallest first. ``turbo`` is the GPU default and
#: ``small.en`` the CPU default (see the spec's recognition section).
_KNOWN_MODELS: tuple[Model, ...] = (
    Model("tiny.en", "Systran/faster-whisper-tiny.en"),
    Model("base.en", "Systran/faster-whisper-base.en"),
    Model("small.en", "Systran/faster-whisper-small.en"),
    Model("medium.en", "Systran/faster-whisper-medium.en"),
    Model("distil-small.en", "Systran/faster-distil-whisper-small.en"),
    Model("distil-medium.en", "Systran/faster-distil-whisper-medium.en"),
    Model("distil-large-v3", "Systran/faster-distil-whisper-large-v3"),
    Model("distil-large-v3.5", "distil-whisper/distil-large-v3.5-ct2"),
    Model("large-v3", "Systran/faster-whisper-large-v3"),
    Model("turbo", "mobiuslabsgmbh/faster-whisper-large-v3-turbo"),
)

_BY_NAME = {model.name: model for model in _KNOWN_MODELS}

_ALIASES = {"large-v3-turbo": "turbo"}

DEFAULT_MODEL_FOR_DEVICE = {"cuda": "turbo", "cpu": "small.en"}


def known_models() -> tuple[Model, ...]:
    return _KNOWN_MODELS


def lookup(name: str) -> Model | None:
    return _BY_NAME.get(_ALIASES.get(name, name))


def default_for(device: str) -> Model:
    return _BY_NAME[DEFAULT_MODEL_FOR_DEVICE[device]]


def models_dir() -> Path:
    """Where models are cached on this machine.

    ``SUBIE_HOME`` overrides the base directory, which keeps tests off the real cache.
    """
    override = os.environ.get("SUBIE_HOME")
    if override:
        return Path(override) / "models"
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
        return Path(base) / "subie" / "models"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "subie" / "models"
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "subie" / "models"


def present_models(root: Path | None = None) -> tuple[Model, ...]:
    """The known models already downloaded into the cache."""
    cache = models_dir() if root is None else root
    found: list[Model] = []
    for model in _KNOWN_MODELS:
        hub_name = "models--" + model.repo_id.replace("/", "--")
        direct_name = model.repo_id.rsplit("/", 1)[-1]
        if (cache / hub_name).is_dir() or (cache / direct_name).is_dir():
            found.append(model)
    return tuple(found)


def load_error(model: Model, cause: BaseException) -> str:
    """One user-facing line explaining why a model could not be loaded."""
    cache = models_dir()
    try:
        cached = model in present_models(cache)
    except Exception:
        cached = False
    if cached:
        return (
            f"model '{model.name}' is in the cache at {cache}, "
            f"but the engine could not start: {one_line(cause)}"
        )
    return (
        f"model '{model.name}' ({model.repo_id}) is not in the cache at {cache} "
        f"and could not be downloaded: {one_line(cause)}"
    )
