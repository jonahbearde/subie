# 08: Parallel Jobs (`--jobs`)

**What to build:** Throughput control for a batch, so that a machine with spare memory can process more than one Video at a time. `--jobs` sets how many Jobs run concurrently; the default is one Job at a time on a GPU, and a small fraction of the core count on a CPU. Concurrency must not change what any individual Sidecar contains: two runs over the same folder at different `--jobs` values produce byte-identical Sidecars.

**Blocked by:** 06.

Status: done

- [x] `--jobs 1` and `--jobs 4` over the same folder produce byte-identical Sidecars for every Video.
- [x] The default on a GPU machine is one Job at a time; the default on a CPU machine is greater than one.
- [x] Progress reporting remains readable with more than one Job in flight: lines for different Videos never interleave mid-line.
- [x] The Run summary counts are correct under concurrency, including failures and skips.
- [x] A failure in one concurrent Job does not corrupt or truncate another Job's Sidecar.
- [x] An invalid `--jobs` value is a usage error.
- [x] Tests exercise concurrency through the single agreed seam, using a fake Transcriber with a controlled delay to force overlap deterministically.

## Comments

Implemented as a thread pool over the existing Job, with the default chosen from the
resolved device. The concurrency model is recorded in ADR-0005.

**Where the flag lives.** `--jobs` joins the other Run flags in `cli.py`, as a positive
whole number. Argparse's own type error makes `0`, `-1`, `two` and `1.5` a usage error
(exit 2) before any Video is touched; `_VALUE_FLAGS` knows about it so `subie --jobs 4
doctor` still finds its subcommand.

**The default.** `runs.default_jobs(device)` is the one place that decides: CUDA 1 (a
second model would cost memory for no throughput), CPU `max(2, cores // 4)` capped at 8.
The floor of 2 is deliberate: the ticket asks for a CPU default greater than one, and
`cores // 4` alone would give 1 on a small machine. The model is resolved once per Run,
before any Job, so the default is derived from the device the Run will actually use, not
from what the hardware might have.

**Shape of a concurrent Run.** `_sidecar` first plans every target without doing work:
bad paths and fresh Sidecars are reported immediately, the rest become `_PendingJob`s.
Then `_run_pending` resolves device/model, ensures the model is present, and works through
the pending Jobs. At `--jobs 1` the Jobs run inline on the calling thread; above that they
go to a `ThreadPoolExecutor` and results arrive via `as_completed`. Each Job still builds
its own Transcriber through the existing seam, so N Jobs cost N models — the trade the
flag exists to let the user make, and the reason the GPU default stays at 1.

**Reporting.** Jobs never print. `_attempt` turns each Job into a `_JobLine`,
`_JobWarning` or `_JobFailure` (with the message the reporter needs), and the collecting
thread prints it. Lines are whole by construction, and they appear in completion order.
`_Reporter.warning`/`error` now take messages rather than exceptions, because the
exception has already been flattened where the Job ended. `videos_in`'s docstring no
longer promises reproducible *output* order: the scan order is stable, the report order
under several Jobs is finishing order.

**Sidecar ownership.** Two Videos can resolve to one Sidecar through `--out-dir` plus
`-r` (same-named files in different folders), and the same Video can be passed twice. A
Run now rejects any shared Sidecar path as a usage error before a Job starts. Serially
that case silently kept the last write; concurrently it was a truncate-then-write race,
and which Video won would depend on `--jobs` — exactly the invariant this ticket adds. The
comparison goes through `os.path.normcase(os.path.abspath(...))`, so Windows'
case-insensitivity is respected.

**Interruption.** An interrupted Run cancels Jobs still queued and returns promptly; one
already inside CTranslate2 finishes, because inference cannot be cancelled mid-decode.
Without this, `ThreadPoolExecutor`'s context manager would have drained the whole queue
after Ctrl-C.

**Tests.** `tests/test_parallel.py` runs everything through `run(argv, deps)`:
`--jobs` validation; explicit `--jobs 4` overlapping and `--jobs 1` not; GPU default 1 and
CPU default > 1 (via `max_in_flight`); summary counts with two subtitled, one fresh skip,
one no-speech skip and one no-audio failure all in flight; whole lines plus every Video
present and the summary last; byte-identical Sidecars at 1 and 4 Jobs over a real
segmenter fixture; a recognition failure overlapping a successful Job with the successful
Sidecar byte-exact; shared-Sidecar usage error; Ctrl-C not starting the third queued Job.
`FakeTranscriber` gained a controlled `delay_s`, `max_in_flight`, and an overridable
`transcript_for` so a test can vary one Video inside the same counted call. Shared
`_deps`/`_folder`/`_make_fresh` helpers moved to `tests/support.py`; `test_runs.py`'s
probe-order assertion now compares sorted names, because completion order is no longer
target order.

**Review.** Two-axis review found: shared-Sidecar collision (fixed, see above); a stale
"reproducible output order" docstring (fixed); Ctrl-C draining the queue (fixed); an
`_Attempt.notice` string that duplicated status alongside unreachable fallbacks (replaced
by the three report types); `_run_pending`'s parameter clump (now `_RunOptions`);
`_print_error` as a one-call wrapper (inlined); duplicated test helpers (moved to
`tests/support.py`); and the missing concurrency rationale (ADR-0005). Rejected: dispatch
on `JobStatus` instead of a report type — SKIPPED covers both an up-to-date Sidecar (a
line) and no speech (a warning), so status is not the same partition; and capping
`--jobs` on GPU — the ticket's premise is that the user trades memory for throughput, and
the help text and ADR say so.