# Distribution: uv-managed interpreter, pip CUDA runtime, PyAV instead of system ffmpeg

The tool must install and run on a Windows machine with **no Python, no ffmpeg, and no
CUDA toolkit** — while still running on a CPU-only machine. Three linked choices follow.

- **`uv tool install`, not a PyInstaller exe.** `uv` is a single static binary that needs
  no admin rights and can fetch and pin its own CPython, so `subie.exe` lands on `PATH`
  without the user installing an interpreter. A frozen exe was rejected: bundling
  CTranslate2 plus the PyAV and CUDA native libraries is fragile, the artifact is 300 MB+
  before models, and first-run extraction is slow. Compiling a lower Python version from
  source was rejected because CTranslate2 4.8 ships `cp313` and `cp314` wheels — the
  historical "3.13 is unsupported" constraint no longer holds.
- **CUDA runtime from pip wheels**, as the `subie[cuda]` extra
  (`nvidia-cublas-cu12`, `nvidia-cudnn-cu12`) with the DLL directories registered before
  CTranslate2 is imported, instead of a documented manual CUDA Toolkit + cuDNN install. The
  manual path is the single most common way this class of tool fails on Windows, and we
  cannot debug the GPU machine in person.
- **PyAV for all media I/O**, not `ffmpeg` on `PATH`. PyAV bundles the FFmpeg libraries in
  its own wheel, so audio decoding and stream probing stop being an external prerequisite.
  This is a locked-in dependency (LGPL FFmpeg build inside the wheel) accepted for the
  install story; `subie doctor` reports the bundled FFmpeg version.

Because the CUDA path cannot be exercised on a machine without a GPU, `subie doctor` is the
acceptance test for the GPU machine: it reports interpreter, bundled FFmpeg, probe results,
resolved device and GPU name, whether cuBLAS/cuDNN actually resolved, and the cache path.

One install-time dependency is worth stating rather than leaving implicit: uv fetches a git
dependency with the system `git` executable, so the one-command install from the repository
URL needs Git on `PATH`, even though the installed tool never does. `docs/install.md`
documents the repository-ZIP and local-path install for a machine without Git. With that
path, uv is the only thing the user must add; Python, FFmpeg and the CUDA runtime arrive
with the tool.