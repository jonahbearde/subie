# 03: GPU certification on the RTX 3070 Ti machine

**What to build:** A working GPU path on the machine that has the GPU, established before the cue logic starts being tuned against it. Installing from the repository with the CUDA extra, running `doctor`, and running one real Video must together demonstrate that inference actually executed on the GPU: the GPU visible, cuBLAS and cuDNN resolved, the expected compute type in use, and a per-Video time consistent with GPU throughput rather than CPU throughput. Whatever DLL-registration or library-version problems this surfaces get fixed here.

**Blocked by:** 01, 02.

Status: ready-for-agent

- [ ] The tool installs on a Windows machine with no Python and no ffmpeg installed, using the documented command only.
- [ ] `subie doctor` on that machine reports the GPU name, cuBLAS resolved, cuDNN resolved, and the expected compute type.
- [ ] A real Video of a few minutes is transcribed in a time consistent with GPU throughput, and the reported elapsed time is evidence of it.
- [ ] If the CUDA extra is not installed, the tool still runs on the CPU and doctor says plainly that the GPU path is unavailable and why.
- [ ] Any library-resolution failure encountered here is fixed in the tool, not by instructions telling the user to modify their system.
- [ ] The certification evidence (doctor output and the timing of a real Run) is recorded on this ticket.