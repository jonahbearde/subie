# 01: Walking skeleton + `subie doctor`

**What to build:** An installable `subie` command that can be run on both machines and tell its user whether the machine is ready — before any speech recognition exists. `subie doctor` reports the interpreter, the bundled ffmpeg that PyAV provides, a media probe result, the device the tool would actually choose, the GPU name, whether the CUDA libraries resolved, the compute type that would be used, the model cache location, and which models are present. The command is honest about the difference between "a device is visible" and "the libraries needed to use it resolved".

**Blocked by:** None (can start immediately).

Status: done

- [x] A fresh clone can be installed and run as `subie`, with no system Python or ffmpeg assumed.
- [x] `subie doctor` exits 0 on a healthy machine and prints every field listed above.
- [x] On a machine with no usable GPU, doctor reports the CPU device, the CPU model and compute type it would use, and does not claim a GPU is available.
- [x] On a machine where a GPU is visible but the CUDA libraries fail to resolve, doctor reports the GPU as **not usable** and names the missing library, rather than reporting the GPU as available.
- [x] `subie` with no arguments prints usage and exits with the usage-error code.
- [x] `subie --help` documents the subcommands and every flag that exists at this point.
- [x] Doctor output contains no stack traces, for any failure mode above.
- [x] Tests drive doctor through the single agreed seam with a fake device probe and fake transcriber factory; no test requires a real GPU or a model download.

## Comments

Implemented as a `uv` project with a `src/` layout and a `subie` console script. `doctor`
is the only command so far; the default (path) action arrives with 02.

**Seam note.** The spec describes `deps` as two abilities (media probe, transcriber
factory); this ticket requires a fake *device* probe, so `deps` carries three: `probe`,
`device`, `make_transcriber`. Everything else — parsing, resolution, reporting, exit
codes — is real code under test. Doctor never calls the transcriber factory (that would
download a model); the fake raises if it is called.

**Real-machine evidence (the author's Windows box).** The GPU is visible to the driver
but CTranslate2's CUDA runtime cannot start against this driver, which is exactly the
"detected but not working" case:

```
subie doctor

  python          3.13.0 (CPython)
  ffmpeg          9.0.2 (PyAV 19.0.2)
  media probe     ok: read a 0.10 s test clip with an audio stream
  device          cpu
  gpu             NVIDIA GeForce GT 710 - not usable
  cuda libraries  not resolved: CUDA failed with error CUDA driver version is insufficient for CUDA runtime version
  compute type    int8
  model           small.en (default for cpu)
  model cache     C:\Users\...\AppData\Local\subie\models
  models present  none
  result          ready: CPU path (GPU not usable)
```

Exit code 0 because the CPU path works; the GPU is never described as available. The
missing-library case is covered by a fake device probe whose error names
`cudnn_ops_infer64_8.dll`, and the real parser extracts that name for the report.

The report keeps three facts apart: the driver's GPU list, whether the CUDA libraries
load, and whether CTranslate2 can see a device. A GPU-less machine with working
libraries therefore says `cuda libraries: resolved`, while a visible GPU with broken
libraries says `not usable`.

Install was verified with `uv tool install --python 3.13 --managed-python .` into an
isolated tool directory, then running `subie --help` and `subie doctor` from it.

Tests: 19 passing, no GPU and no model download required. `ruff` and `mypy` clean.