# 01: Walking skeleton + `subie doctor`

**What to build:** An installable `subie` command that can be run on both machines and tell its user whether the machine is ready — before any speech recognition exists. `subie doctor` reports the interpreter, the bundled ffmpeg that PyAV provides, a media probe result, the device the tool would actually choose, the GPU name, whether the CUDA libraries resolved, the compute type that would be used, the model cache location, and which models are present. The command is honest about the difference between "a device is visible" and "the libraries needed to use it resolved".

**Blocked by:** None (can start immediately).

Status: ready-for-agent

- [ ] A fresh clone can be installed and run as `subie`, with no system Python or ffmpeg assumed.
- [ ] `subie doctor` exits 0 on a healthy machine and prints every field listed above.
- [ ] On a machine with no usable GPU, doctor reports the CPU device, the CPU model and compute type it would use, and does not claim a GPU is available.
- [ ] On a machine where a GPU is visible but the CUDA libraries fail to resolve, doctor reports the GPU as **not usable** and names the missing library, rather than reporting the GPU as available.
- [ ] `subie` with no arguments prints usage and exits with the usage-error code.
- [ ] `subie --help` documents the subcommands and every flag that exists at this point.
- [ ] Doctor output contains no stack traces, for any failure mode above.
- [ ] Tests drive doctor through the single agreed seam with a fake device probe and fake transcriber factory; no test requires a real GPU or a model download.