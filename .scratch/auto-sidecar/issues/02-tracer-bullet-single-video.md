# 02: Tracer bullet — one Video in, one Sidecar out

**What to build:** The whole path, as thinly as it can be cut. `subie video.mp4` probes the Video, decodes its audio in memory at 16 kHz mono, recognizes the speech as English, and writes `video.srt` beside it. Cue construction at this stage is deliberately naive — one Cue per engine segment, no readability rules yet — because the point of this ticket is to prove the layers connect and to make failures visible early. The Run prints one compact line per Video and nothing else, and exits non-zero if the Video failed. Pipelines silence-exclusion and no-previous-text conditioning are switched on now, not later, since they are engine options rather than cue logic.

**Blocked by:** 01.

Status: done

- [x] `subie video.mp4` writes `video.srt` beside the Video and prints one summary line containing the Video name, the Sidecar name, the cue count, and elapsed time.
- [x] The Video file is opened read-only; its bytes are unchanged after a Run (verified by hashing before and after).
- [x] The Sidecar is valid SRT: numbering from 1, `hh:mm:ss,mmm` timestamps, one blank line between cues, UTF-8 without BOM, CRLF line endings, trailing newline.
- [x] No temporary audio file is left on disk after a Run.
- [x] `--keep-audio` retains the decoded audio in a predictable place for debugging; without it, nothing is retained.
- [x] Recognition runs with VAD enabled, previous-text conditioning disabled, and the English language and transcribe task fixed in code with no flag to change them.
- [x] The default model and compute type are derived from the resolved device, and `--model` and `--device` override them.
- [x] A missing model on a machine with no network produces a clear message naming the model and the cache location, with no download-library stack trace.
- [x] A Video path that does not exist produces a clear message and the failure exit code.
- [x] An end-to-end test marked `slow` generates a short clip with known speech, runs it through the real engine, and asserts that the Sidecar is well-formed, has a plausible cue count, and contains the spoken words; the test skips cleanly when the model is absent.
## Comments

Implemented as the default CLI action: `subie VIDEO...` with no subcommand. The parser
surface is split because argparse cannot mix an optional positional path with required
subcommands; `build_parser()` is the `--help`/`doctor` surface and `build_sidecar_parser()`
parses the default action. Both share `--device` and `--model`.

**Modules.** `audio.py` decodes in memory through PyAV (`AudioResampler` to 16 kHz mono
float32) and only writes a WAV when asked. `transcript.py` is the engine-independent
Transcript shape. `srt.py` builds the deliberately naive one-Cue-per-segment list and
renders UTF-8 without BOM, CRLF, blank line between blocks, trailing newline. `pipeline.py`
runs the Job in the order probe → decode → optional keep → build engine → recognise →
segment → render → write. `engine.py` pins `language="en"`, `task="transcribe"`,
`vad_filter=True`, `condition_on_previous_text=False`, and `word_timestamps=True`; there
is no flag that can change any of them.

**`--keep-audio`** writes `<stem>.keep-audio.wav` beside the Video (the suffix already
matched `.gitignore`). It is written before the engine is built, so the audio survives a
model failure and can be listened to. The Wave file is 16-bit PCM, 16 kHz mono.

**Model resolution.** The device comes from the existing hardware probe; CUDA is used only
when it is genuinely usable, otherwise CPU. Model and compute type then come from the same
table `doctor` uses (`turbo`/`float16` on CUDA, `small.en`/`int8` on CPU). `--device` and
`--model` override them; `--device cuda` on an unusable machine is a failure rather than a
silent fallback. A failure to build the engine is turned into one line that names the model
and `models.models_dir()`, chosen between "not in the cache and could not be downloaded"
and "in the cache but the engine could not start", never a download-library stack trace.

**No-speech.** No Cues means no Sidecar is written. At this stage no-speech is reported as
an error; ticket 06 reclassifies it as a skip with no Sidecar. Explicit multiple Video paths
are isolated per Job (one failure does not stop the next), but folder discovery, skip
freshness, `--force`/`--out-dir` and the Run summary remain ticket 06.

### Evidence

CUDA builds `BatchedInferencePipeline` around the model, as ADR-0002 requires for GPU
throughput; CPU uses the plain `WhisperModel`. ADR-0001 was amended to record that the
opt-in `--keep-audio` WAV is debug output, not a product artifact.

Default suite: 46 passed, 1 deselected (`slow`). `ruff` clean, `ruff format --check` clean,
`mypy` clean (24 files).

The real no-network path was exercised on this Windows machine with `HF_HUB_OFFLINE=1` and
an empty `SUBIE_HOME`, against a generated 1 s WAV:

```
subie: error: model 'small.en' (Systran/faster-whisper-small.en) is not in the cache at
C:\Users\...\subie-offline-check\home\models and could not be downloaded: Cannot find an
appropriate cached snapshot folder ... outgoing traffic has been disabled.
EXIT=1
```

With `--keep-audio`, the same run also produced `clip.keep-audio.wav` (1 channel, 16 kHz,
16 000 frames) before reporting the model failure.

The `slow` test could not be executed here: no known model is cached and Hugging Face is
unreachable from this machine, so it skips with "no recognition model is cached on this
machine" as required. It synthesises the spoken clip locally (Windows SAPI, `espeak`, or
macOS `say`) and skips when no offline synthesiser exists.
