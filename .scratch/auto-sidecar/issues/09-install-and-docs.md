# 09: Install story and docs

**What to build:** The thing a person can actually follow, on both machines. A documented install that works on a Windows machine with no Python and no ffmpeg, a README that leads with the zero-argument case, and an honest list of what the tool will not do well. Someone who has never seen this conversation should be able to install it, subtitle a video, understand what the flags change, and know the limits they should expect.

**Blocked by:** 03, 05, 06, 07, 08.

Status: done

- [x] The README's first example is the zero-argument case, and every subsequent example matches a behaviour that actually exists.
- [x] Install instructions cover both machines: the GPU machine with no Python or ffmpeg, and a CPU-only machine.
- [x] The GPU setup is documented as one command, with what to do when `doctor` reports the GPU path as unavailable.
- [x] Known limitations are stated plainly: proper nouns and names can be misheard, music and heavy effects can confuse the engine, English only, and there is no translation.
- [x] The subtitle policy document is linked from the README as the reference for cue limits, and its numbers match the implementation.
- [x] `--keep-audio` is documented as the way to inspect what the engine actually heard.
- [x] Exit codes and the skip/force behaviour are documented, with an example script that branches on the exit code.
- [x] The four architecture decision records are consistent with the shipped behaviour, or amended where reality diverged.

## Comments

**README.** Rewritten around the zero-argument case: `subie video.mp4` is the first
console block, then a one-line output example, then folder and `-r` usage. The install
section has the one-command GPU install
(`uv tool install "subie[cuda] @ git+https://github.com/jonahbearde/subie.git"`), the
CPU-only install without the extra, the `doctor` fields that prove either path, and the
three GPU-unavailable cases (`not usable`, `none visible`, and `doctor` exiting 0 because
the CPU path is ready). It also records that the git-URL install needs Git, with the ZIP
and local-path alternatives.

**Install notes.** New `docs/install.md` covers the no-Git install from a repository ZIP,
installing from a clone, a field-by-field reading of `doctor`, GPU troubleshooting
(reinstall the `cuda` extra, read the failing DLL, update the driver, fall back to CPU),
preparing and moving an offline model cache, updating and uninstalling, and the expected
performance difference between GPU and CPU.

**Flags and outcomes.** The README documents every flag, the device-derived defaults
(`turbo`/`float16` vs `small.en`/`int8`), the `--jobs` defaults and memory cost,
`--out-dir` collisions, and `--keep-audio` as `<stem>.keep-audio.wav` beside the Video
(16 kHz mono PCM, written before recognition, not a normal-run artifact). Skipping is
described by the mtime rule and the literal `skipped (up to date)` line; `--force` is the
override. Exit codes 0/1/2 are tabulated, with both a PowerShell and a POSIX script that
branch on them.

**Limitations.** The README states the quality ceiling plainly: proper nouns and names
misheard, music and heavy effects confusing the engine, English only with no language
detection and no translation, Sidecar-only output with no burn-in or styling, no
diarization/SDH/karaoke/timing repair, conservative cue limits, first-run network
requirement, CPU speed and the driver not being bundled.

**Policy numbers.** `docs/subtitle-policy.md` is linked as the reference and its table
numbers match `subie.segment`: 42 characters, 2 lines, 20 CPS, 1–7 s, 100 ms gap, 200 ms
padding. Two wording divergences were corrected while checking it against the code:
breaking after the longest pause falls back to a balanced word boundary (not "anywhere"),
and a range is low-confidence only when even its most generous reading trips a threshold.
The timing step now records the shipped precedence when word timings overlap (no overlap
wins over padding).

**ADRs and spec.** All five ADRs were checked against the shipped behaviour. ADR-0004 now
says the CUDA DLL directories are registered before CTranslate2 is imported (not "at
import"), and records that the git-URL install needs Git while the ZIP path does not.
ADR-0005's CPU default is written as the implemented `max(2, min(8, cores // 4))`. The
spec's CLI surface no longer promises a progress indicator that was never built, and its
exit-code line now includes an unready `doctor`.

**Tests.** `tests/test_docs.py` guards the promises: the first console block is the
zero-argument invocation; both install commands, `doctor`, `--device cuda` and the
unavailable-GPU advice are present; no-Git and offline paths are documented; every flag,
`--keep-audio`, the skip/force wording, the 0/1/2 table and both branching scripts exist;
the limitations name proper nouns, music, English-only and no translation; the policy and
every ADR are linked; the policy's cue-limit table matches the segmenter constants. This
is the documentation counterpart to the existing blocklist-is-documented test.

**Verification.** `uv run pytest` (145 tests), `uv run mypy` and `uv run ruff check .`
are clean. The direct-reference install syntax was resolved with
`uv pip install --dry-run` for both the git URL and the `cuda` extra, and a wheel was
installed into a temporary tool directory with `uv tool install` to prove the console
script lands and runs. The GPU one-command path could not be installed end-to-end here
without downloading the CUDA wheels; its syntax, extra resolution and the `doctor`
behaviour it documents are covered by the checks above and the existing hardware tests.