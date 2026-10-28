# Install

`subie` is delivered as a Python package installed by [uv](https://docs.astral.sh/uv/).
uv is a single binary that downloads and pins its own CPython, so the machine needs no
system Python. PyAV bundles the FFmpeg libraries inside its wheel, so it needs no system
`ffmpeg`. The optional `cuda` extra installs the cuBLAS and cuDNN runtime wheels, so it
needs no CUDA Toolkit.

The installed `subie` console command is normal: uv is needed to install and update it,
and Git is needed only for the git-URL form below, not to run it.

## 1. Install uv

On Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

No administrator rights are required. On macOS or Linux, use the installer on the
[uv installation page](https://docs.astral.sh/uv/getting-started/installation/).

After installing uv, open a new terminal so its tool directory is on `PATH`. If `subie` is
not found later, `uv tool update-shell` prints what to do.

## 2. Install the tool

### GPU machine

One command installs `subie` plus the CUDA runtime wheels:

```console
uv tool install "subie[cuda] @ git+https://github.com/jonahbearde/subie.git"
```

Then verify the GPU path:

```console
subie doctor
```

A working GPU machine reports `device cuda`, the GPU name, `cuBLAS resolved`, `cuDNN
resolved`, `compute type float16`, `model turbo (default for cuda)` and a `result` of
`ready: the GPU path is usable`.

### CPU-only machine

```console
uv tool install "subie @ git+https://github.com/jonahbearde/subie.git"
subie doctor
```

A working CPU machine reports `device cpu`, `compute type int8`, `model small.en (default
for cpu)` and a `result` starting `ready`. It may also report a visible GPU as `not usable`
when the CUDA extra was not installed; that is expected on a CPU-only install.

### The machine has no Git

uv fetches a Git URL with the system `git` executable. If Git is not installed, download
the repository ZIP from GitHub, extract it, and run one of these from the folder that
contains `pyproject.toml`:

```console
uv tool install ".[cuda]"     # GPU machine
uv tool install .             # CPU-only machine
```

### Install from a clone

If you already have a clone, the local path works the same way:

```console
git clone https://github.com/jonahbearde/subie.git
cd subie
uv tool install ".[cuda]"     # GPU machine
uv tool install .             # CPU-only machine
```

The `cuda` extra is a packaging choice, not a runtime switch. Installing without it and
later running on a GPU machine gives `device cpu`; reinstall with the extra to add the CUDA
wheels.

## 3. Read `subie doctor`

`doctor` never downloads a model and never starts recognition. It reports one field per
fact:

| Field | What it means |
|---|---|
| `python` | The interpreter uv supplied for the tool. No system Python is involved. |
| `ffmpeg` | The FFmpeg version bundled inside the PyAV wheel, plus the PyAV version. |
| `media probe` | A generated 0.1 s WAV was decoded through the real media stack. |
| `device` | The device a Run would use: `cuda` or `cpu`. |
| `gpu` | The GPU names the driver reports, or `none visible`, with `- not usable` when CUDA cannot be used. |
| `cuda libraries` | Whether cuBLAS and cuDNN actually loaded, with the failing DLL's error when they did not. |
| `compute type` | `float16` on a usable GPU, `int8` on CPU. |
| `model` | The model a Run would use, or the one requested with `--model`. |
| `model cache` | The one per-machine directory models live in. |
| `models present` | The known models already usable from that cache, or `none`. |
| `result` | `ready` or `not ready`, with the reason. |

`doctor` exits 0 when the CPU path is ready, even when a GPU is visible but unusable. To
make an unusable GPU a non-zero exit, ask for it explicitly:

```console
subie doctor --device cuda
```

That exits 1 unless CUDA genuinely works. A normal Run with `--device cuda` behaves the
same way: it fails rather than silently dropping to the CPU.

## When the GPU path is unavailable

### `gpu` says `... - not usable`

The driver can see the GPU, but CTranslate2 cannot load the CUDA libraries. This is what a
CPU-only install looks like on a machine that happens to have an NVIDIA card.

```console
uv tool install --force "subie[cuda] @ git+https://github.com/jonahbearde/subie.git"
subie doctor
```

`--force` makes uv reinstall an existing tool with the extra. Look at the `cuda libraries`
line if it still fails:

- `cublas64_12.dll` (or `libcublas.so.12`) not resolved: the cuBLAS wheel is missing or
  the driver is too old for CUDA 12.
- `cudnn_ops64_9.dll` (or `libcudnn_ops.so.9`) not resolved: the cuDNN wheel is missing,
  or an old cuDNN 8 install is shadowing it.
- A CTranslate2 error after the library lines: the driver and the CUDA 12 runtime disagree.

Update the NVIDIA driver, confirm `nvidia-smi` lists the GPU, then reinstall the extra. If
the GPU remains unusable, the CPU path is still a working tool: `device cpu` and
`compute type int8` are expected, and `--device cpu` makes that choice explicit.

### `gpu` says `none visible`

The driver does not expose an NVIDIA GPU. Either the machine has no NVIDIA GPU, or the
driver is not installed. Install or update the driver from NVIDIA if CUDA was expected;
otherwise use the CPU path with no further setup. `subie doctor --device cuda` exits 1 in
this state.

### `doctor` says `not ready` for another reason

The `result` line names the failing field. A failed `media probe` or a failed device probe
is an installation problem: reinstall the tool, then run `subie doctor` again. A `model
cache` or `models present` problem is a cache-permissions problem; the path is printed so
it can be inspected or removed.

## Preparing an offline machine

The model cache is the only thing a Run needs beyond the installed tool. Prepare it while
the machine still has network access:

```console
subie models pull turbo        # GPU default; small.en is the CPU default
subie models list              # verify the model and its size
```

A Run uses a cached model without touching the network. If the model is missing and the
network is unavailable, the Run fails with a message naming the model and the cache path,
rather than a download-library stack trace.

To move a prepared cache to another machine, copy the whole `models--*` directories into the
cache path printed by `doctor` on the target. The model files are platform-independent, but
the Hugging Face cache may use symlinks, so use a copy that preserves them or copy the
`blobs` directory as well. The CUDA wheels themselves are platform-specific, so install the
tool with the `cuda` extra on the target rather than copying its virtual environment.

## Updating and removing

Reinstall with the same command and `--force`:

```console
uv tool install --force "subie[cuda] @ git+https://github.com/jonahbearde/subie.git"
```

Remove the console command:

```console
uv tool uninstall subie
```

Remove a cached model, freeing its space:

```console
subie models rm turbo
```

Removing the model cache directory by hand also works; the next Run downloads what it needs
again. Removing the tool does not remove the cache.

## Performance expectations

On the RTX 3070 Ti this was built for, a 30-minute Video is normally finished in well under
a minute: the GPU path uses faster-whisper's batched inference. On a CPU-only machine,
expect minutes rather than seconds; the default `small.en` model at `int8` is chosen for
that trade. `--model` can trade accuracy for speed in either direction, and `--jobs` can
keep several CPU Jobs in flight at the cost of one model's memory each. Sidecar bytes do
not depend on either flag.