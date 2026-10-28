# 06: Batch Runs and failure semantics

**What to build:** A folder as input. `subie ~/Videos` subtitles every Video in it, ignoring non-video files silently, not descending into subfolders unless `-r` is given, and skipping Videos whose Sidecar is already newer than the Video itself. `--force` overwrites; `--out-dir` redirects output. A Video with no audio stream, and a Video whose audio contains no speech, both warn and produce **no** Sidecar rather than an empty one. One failing Video does not abort the Run: it is reported, the rest proceed, and the exit code reflects that something failed. A Run of more than one Video ends with a summary of subtitled, skipped, and failed counts. `--quiet` leaves only errors; `--verbose` adds engine logging.

**Blocked by:** 04.

Status: done

- [x] A directory argument subtitles every Video directly inside it and ignores non-video files without mentioning them.
- [x] Subfolders are not entered by default; `-r` enters them, and a Video in a subfolder gets its Sidecar in that same subfolder.
- [x] A Video whose Sidecar is newer than itself is reported as skipped and is not re-processed; `--force` re-processes it.
- [x] `--out-dir` places every Sidecar in that directory, named after its Video.
- [x] A Video with no audio stream warns, produces no Sidecar, and counts as failed.
- [x] A Video whose audio has no detectable speech warns, produces no Sidecar, and counts as a skip rather than a silent success.
- [x] One Video failing mid-Run does not prevent later Videos from being processed, and the Run summary reflects the failure.
- [x] Exit codes distinguish all-success, any-failure, and usage error, and "everything was skipped" counts as success.
- [x] `--quiet` prints only errors; `--verbose` includes engine logging; the default stays one line per Video plus the Run summary.
- [x] The single-Video case still behaves exactly as it did before this ticket, with no Run summary printed for it.
- [x] Tests cover each behaviour above through the single agreed seam, including a folder containing a good Video, a broken Video, a non-video file, and an already-subtitled Video.
## Comments

Ticket 02's tracer bullet currently reports both "no audio stream" and "no speech detected"
as a failed single Video, because it has no skip status yet. This ticket is where
no-speech becomes a skip (warning, no Sidecar) while no-audio remains a failure.

Implemented as a Run-planning layer around the existing Job, plus one new Job outcome.

**`src/subie/runs.py`** owns everything that is true across Jobs: `VIDEO_SUFFIXES`,
`videos_in` (non-recursive by default, stable order), `sidecar_for`, `is_fresh`,
`JobStatus`/`JobOutcome`, and `RunSummary`. A directory scan accepts both video containers
and audio-only media, because a Video is anything with an audio stream; every other file is
skipped without being mentioned. Explicit file paths are not filtered by extension, so an
intentionally named file still reaches the probe. Freshness is checked in the Sidecar's
*actual* location, so `--out-dir` is not skipped because a stale beside-the-Video file
exists; an equal timestamp counts as fresh, and `--force` bypasses the check.

**`src/subie/cli.py`** expands folders into targets, keeps bad paths as failed targets, and
reports each outcome. Model/device resolution is lazy: a Run whose Videos are all skipped
never touches the engine. If that resolution fails, the failure is reported once and
remaining unprocessed targets count as failed. `-r`/`--recursive`, `--force`, `--out-dir`,
`--quiet` and `--verbose` join the existing flags; `--out-dir` is created if needed and a
non-directory target is a usage error. The summary is printed only when the Run covered more
than one Video, so the single-Video output is unchanged. Exit code is 0 when nothing failed
(including all-skipped), 1 when any Job failed, and 2 for usage errors.

**Exit statuses.** A no-audio-stream Video remains a failed Job and is reported on stderr. A
Video with no detectable speech (including music-only audio) raises `JobSkipped` instead of
`JobError`: it warns on stderr, writes no Sidecar, and counts as skipped. `--quiet` suppresses
both the per-Video lines and warnings, but never suppresses errors. `--verbose` installs a
scoped `faster_whisper`/`ctranslate2` log handler on stderr for the duration of the Run, then
restores the previous logging levels.

**Tests.** `tests/test_runs.py` drives every behaviour through `run(argv, deps)`: directory
scanning and silent ignoring of non-video files, non-recursive vs `-r`, freshness and
`--force`, `--out-dir`, no-audio failure, no-speech skip, mid-Run failure isolation, exit
codes, all-skipped success, quiet/verbose, single-Video output, and a folder mixing a good
Video, a broken Video, a non-video file and an already-subtitled Video. The no-speech
expectations in `test_job.py` and `test_cleaning.py` moved from failure to skip.

**Domain vocabulary.** `CONTEXT.md` gained **Skip** and now records that a Sidecar can be
redirected by `--out-dir` and that a Run summary appears only when more than one Video is
covered.
