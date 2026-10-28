"""The models the tool knows about, and the per-machine cache they live in.

The cache location reported by ``subie doctor``, used by ``subie models`` and used by a
Run must all be this one directory.
"""

from __future__ import annotations

import os
import shutil
import stat
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

#: What a CTranslate2 Whisper model is made of. Downloading this set, rather than the whole
#: repository, is the same choice faster-whisper's own downloader makes, so a model pulled
#: here is exactly the model a Run would have fetched for itself.
MODEL_FILES = (
    "config.json",
    "preprocessor_config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.*",
)

#: The files whose presence means a cached model can actually be loaded, in particular
#: with no network to fetch a missing tokenizer.
_REQUIRED_FILES = ("config.json", "model.bin", "tokenizer.json")


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


def cache_path_for(repo_id: str, root: Path | None = None) -> Path:
    """The cache directory one model repository occupies, whether or not it is there yet.

    The name is the Hugging Face cache convention, because that is what the download
    library and the recognition engine both look for.
    """
    cache = models_dir() if root is None else root
    return cache / ("models--" + repo_id.replace("/", "--"))


def model_dir(model: Model, root: Path | None = None) -> Path:
    """The directory in the cache that belongs to ``model``."""
    return cache_path_for(model.repo_id, root)


def model_cached(repo_id: str, root: Path | None = None) -> bool:
    """Whether a model repository is already usable from the cache."""
    return _is_usable(cache_path_for(repo_id, root))


def present_models(root: Path | None = None) -> tuple[Model, ...]:
    """The known models actually usable from the cache on this machine.

    A directory is not enough: a download that died halfway leaves one behind, and
    reporting it as present would make ``models list`` and a Run disagree.
    """
    return tuple(model for model in _KNOWN_MODELS if _is_usable(model_dir(model, root)))


def _is_usable(directory: Path) -> bool:
    snapshots = directory / "snapshots"
    if not snapshots.is_dir():
        return False
    return any(
        all((snapshot / name).is_file() for name in _REQUIRED_FILES)
        for snapshot in snapshots.iterdir()
    )


def model_size(model: Model, root: Path | None = None) -> int:
    """How many bytes the model occupies in the cache, counting shared files once.

    The download library deduplicates by symlinking snapshot files to blobs, so a
    snapshot entry that is a link is not counted again.
    """
    directory = model_dir(model, root)
    if not directory.is_dir():
        return 0
    total = 0
    for path in directory.rglob("*"):
        try:
            info = path.lstat()
        except OSError:
            continue
        if stat.S_ISREG(info.st_mode):
            total += info.st_size
    return total


def remove_model(model: Model, root: Path | None = None) -> int | None:
    """Delete the model from the cache, returning the bytes freed, or ``None`` if absent."""
    directory = model_dir(model, root)
    if not directory.is_dir():
        return None
    freed = model_size(model, root)
    shutil.rmtree(directory)
    return freed


def human_size(size: int) -> str:
    """A byte count the way a person reads it: ``462 MB``, ``1.6 GB``."""
    value = float(size)
    units = ("B", "KB", "MB", "GB", "TB")
    index = 0
    while value >= 1024 and index < len(units) - 1:
        value /= 1024
        index += 1
    if units[index] == "B":
        return f"{int(value)} B"
    return f"{value:.1f}".rstrip("0").rstrip(".") + f" {units[index]}"


def size_text(model: Model, root: Path | None = None) -> str:
    """How large a cached model is, for a report."""
    return human_size(model_size(model, root))


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


def pull_error(model: Model, cause: BaseException) -> str:
    """One user-facing line explaining why a model could not be downloaded."""
    return (
        f"cannot download model '{model.name}' ({model.repo_id}) "
        f"into the cache at {models_dir()}: {one_line(cause)}"
    )
