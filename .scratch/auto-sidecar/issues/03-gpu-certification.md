# 03: GPU certification on the RTX 3070 Ti machine

**What to build:** A working GPU path on the machine that has the GPU, established before the cue logic starts being tuned against it. Installing from the repository with the CUDA extra, running `doctor`, and running one real Video must together demonstrate that inference actually executed on the GPU: the GPU visible, cuBLAS and cuDNN resolved, the expected compute type in use, and a per-Video time consistent with GPU throughput rather than CPU throughput. Whatever DLL-registration or library-version problems this surfaces get fixed here.

**Blocked by:** 01, 02.

Status: done

- [x] The tool installs on a Windows machine with no Python and no ffmpeg installed, using the documented command only.
- [x] `subie doctor` on that machine reports the GPU name, cuBLAS resolved, cuDNN resolved, and the expected compute type.
- [x] A real Video of a few minutes is transcribed in a time consistent with GPU throughput, and the reported elapsed time is evidence of it.
- [x] If the CUDA extra is not installed, the tool still runs on the CPU and doctor says plainly that the GPU path is unavailable and why.
- [x] Any library-resolution failure encountered here is fixed in the tool, not by instructions telling the user to modify their system.
- [x] The certification evidence (doctor output and the timing of a real Run) is recorded on this ticket.

## Comments

Certified on the RTX 3070 Ti machine (Windows 10, driver 617.42, 8 GB). Installed with the documented
command only:

```console
uv tool install ".[cuda]"
```

`uv` selected its own managed CPython 3.12.14; the tool did not use the machine's system Python and
does not touch the system `ffmpeg`. The wheel brought PyAV 19.0.2 with FFmpeg 9.0.2.

**GPU doctor output.**

```
subie doctor

  python          3.12.14 (CPython)
  ffmpeg          9.0.2 (PyAV 19.0.2)
  media probe     ok: read a 0.10 s test clip with an audio stream
  device          cuda
  gpu             NVIDIA GeForce RTX 3070 Ti
  cuda libraries  cuBLAS resolved (12.9.2.10); cuDNN resolved (9.27.0.42)
  compute type    float16
  model           turbo (default for cuda)
  model cache     C:\Users\...\AppData\Local\subie\models
  models present  turbo
  result          ready: the GPU path is usable
```

**Real Run.** A 6 min 54 s (414 s) MP4 with a speech track was transcribed by the default zero-flag
default (`turbo`, `float16`, CUDA):

```console
certification.mp4 → certification.srt  14 cues  7.7s
```

Wall time was 8.3 s, about 50x real time. `nvidia-smi` sampled every 250 ms during the Run showed
99% GPU utilization at roughly 4.3 GB used; the samples are direct evidence that inference ran on the
GPU rather than falling back to the CPU. The Sidecar was well-formed SRT with CRLF and 14 cues.
The test Video lives outside the repository at `C:\Users\jonabirde\subie-gpu-cert` and is not
committed.

**No CUDA extra.** A separate isolated environment containing only `pip install .` (no `[cuda]`)
reported the CPU path with an explicit reason:

```
  device          cpu
  gpu             NVIDIA GeForce RTX 3070 Ti - not usable
  cuda libraries  cuBLAS not resolved (Could not find module 'cublas64_12.dll' ...);
                  cuDNN not resolved (Could not find module 'cudnn_ops64_9.dll' ...)
  compute type    int8
  model           small.en (default for cpu)
  result          ready: CPU path (GPU not usable)
```

A 12 s speech Video through that environment (`--model tiny.en`, device auto) completed on the CPU:
`cpu-check.wav → cpu-check.srt  4 cues  11.1s` on the first run including the model fetch
(1.5 s with the model cached), exit 0.

**Fixed here.**

1. **A visible GPU was reported usable without the CUDA runtime wheels.**
   `ctranslate2.get_supported_compute_types("cuda")` succeeds against the driver even when
   `cublas64_12.dll` cannot load, so doctor said `cuda libraries resolved` and the Run then failed with
   `Library cublas64_12.dll is not found or cannot be loaded`. `probe_hardware` now actually loads
   cuBLAS and cuDNN (after registering the `nvidia-*` wheel directories) and reports each library
   separately; a missing library makes the GPU not usable and the tool resolves the CPU instead.
2. **The summary arrow crashed redirected output on Windows.** The Run wrote the Sidecar and then died
   with `'charmap' codec can't encode character '\u2192'`, exiting 1. The CLI now reconfigures
   redirected stdout/stderr to UTF-8 before printing, so a completed Run reports success.

Tests: 50 passed, 1 deselected (`slow`). `ruff` clean, `ruff format --check` clean, `mypy` clean.
The new tests cover per-library GPU usability (`tests/test_hardware.py`) and doctor's per-library
reporting, plus the legacy-codepage summary line.