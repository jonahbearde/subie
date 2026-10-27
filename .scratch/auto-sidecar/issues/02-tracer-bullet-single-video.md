# 02: Tracer bullet — one Video in, one Sidecar out

**What to build:** The whole path, as thinly as it can be cut. `subie video.mp4` probes the Video, decodes its audio in memory at 16 kHz mono, recognizes the speech as English, and writes `video.srt` beside it. Cue construction at this stage is deliberately naive — one Cue per engine segment, no readability rules yet — because the point of this ticket is to prove the layers connect and to make failures visible early. The Run prints one compact line per Video and nothing else, and exits non-zero if the Video failed. Pipelines silence-exclusion and no-previous-text conditioning are switched on now, not later, since they are engine options rather than cue logic.

**Blocked by:** 01.

Status: ready-for-agent

- [ ] `subie video.mp4` writes `video.srt` beside the Video and prints one summary line containing the Video name, the Sidecar name, the cue count, and elapsed time.
- [ ] The Video file is opened read-only; its bytes are unchanged after a Run (verified by hashing before and after).
- [ ] The Sidecar is valid SRT: numbering from 1, `hh:mm:ss,mmm` timestamps, one blank line between cues, UTF-8 without BOM, CRLF line endings, trailing newline.
- [ ] No temporary audio file is left on disk after a Run.
- [ ] `--keep-audio` retains the decoded audio in a predictable place for debugging; without it, nothing is retained.
- [ ] Recognition runs with VAD enabled, previous-text conditioning disabled, and the English language and transcribe task fixed in code with no flag to change them.
- [ ] The default model and compute type are derived from the resolved device, and `--model` and `--device` override them.
- [ ] A missing model on a machine with no network produces a clear message naming the model and the cache location, with no download-library stack trace.
- [ ] A Video path that does not exist produces a clear message and the failure exit code.
- [ ] An end-to-end test marked `slow` generates a short clip with known speech, runs it through the real engine, and asserts that the Sidecar is well-formed, has a plausible cue count, and contains the spoken words; the test skips cleanly when the model is absent.