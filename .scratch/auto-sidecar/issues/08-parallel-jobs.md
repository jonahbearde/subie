# 08: Parallel Jobs (`--jobs`)

**What to build:** Throughput control for a batch, so that a machine with spare memory can process more than one Video at a time. `--jobs` sets how many Jobs run concurrently; the default is one Job at a time on a GPU, and a small fraction of the core count on a CPU. Concurrency must not change what any individual Sidecar contains: two runs over the same folder at different `--jobs` values produce byte-identical Sidecars.

**Blocked by:** 06.

Status: ready-for-agent

- [ ] `--jobs 1` and `--jobs 4` over the same folder produce byte-identical Sidecars for every Video.
- [ ] The default on a GPU machine is one Job at a time; the default on a CPU machine is greater than one.
- [ ] Progress reporting remains readable with more than one Job in flight: lines for different Videos never interleave mid-line.
- [ ] The Run summary counts are correct under concurrency, including failures and skips.
- [ ] A failure in one concurrent Job does not corrupt or truncate another Job's Sidecar.
- [ ] An invalid `--jobs` value is a usage error.
- [ ] Tests exercise concurrency through the single agreed seam, using a fake Transcriber with a controlled delay to force overlap deterministically.