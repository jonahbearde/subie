# subie

Writes English `.srt` subtitles for English-language videos.

```console
subie video.mp4             # writes video.srt beside it
subie doctor                # is this machine ready?
subie models list           # what is in the model cache, and how large
subie models pull small.en  # download a model before going offline
```

See `.scratch/auto-sidecar/spec.md` for the full specification and `docs/` for the
decisions behind it.

## Install

Requires [uv](https://docs.astral.sh/uv/). Neither a system Python nor a system `ffmpeg`
is needed: `uv` supplies the interpreter and PyAV bundles the FFmpeg libraries.

```console
uv tool install .            # CPU
uv tool install ".[cuda]"    # plus the CUDA runtime wheels
subie doctor
```

## Development

```console
uv sync
uv run pytest
uv run subie doctor
```