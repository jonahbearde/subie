# 06: Batch Runs and failure semantics

**What to build:** A folder as input. `subie ~/Videos` subtitles every Video in it, ignoring non-video files silently, not descending into subfolders unless `-r` is given, and skipping Videos whose Sidecar is already newer than the Video itself. `--force` overwrites; `--out-dir` redirects output. A Video with no audio stream, and a Video whose audio contains no speech, both warn and produce **no** Sidecar rather than an empty one. One failing Video does not abort the Run: it is reported, the rest proceed, and the exit code reflects that something failed. A Run of more than one Video ends with a summary of subtitled, skipped, and failed counts. `--quiet` leaves only errors; `--verbose` adds engine logging.

**Blocked by:** 04.

Status: ready-for-agent

- [ ] A directory argument subtitles every Video directly inside it and ignores non-video files without mentioning them.
- [ ] Subfolders are not entered by default; `-r` enters them, and a Video in a subfolder gets its Sidecar in that same subfolder.
- [ ] A Video whose Sidecar is newer than itself is reported as skipped and is not re-processed; `--force` re-processes it.
- [ ] `--out-dir` places every Sidecar in that directory, named after its Video.
- [ ] A Video with no audio stream warns, produces no Sidecar, and counts as failed.
- [ ] A Video whose audio has no detectable speech warns, produces no Sidecar, and counts as a skip rather than a silent success.
- [ ] One Video failing mid-Run does not prevent later Videos from being processed, and the Run summary reflects the failure.
- [ ] Exit codes distinguish all-success, any-failure, and usage error, and "everything was skipped" counts as success.
- [ ] `--quiet` prints only errors; `--verbose` includes engine logging; the default stays one line per Video plus the Run summary.
- [ ] The single-Video case still behaves exactly as it did before this ticket, with no Run summary printed for it.
- [ ] Tests cover each behaviour above through the single agreed seam, including a folder containing a good Video, a broken Video, a non-video file, and an already-subtitled Video.