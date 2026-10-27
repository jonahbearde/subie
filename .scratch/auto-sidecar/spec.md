# Spec: automatic English Sidecar subtitles

Status: ready-for-agent
Feature: auto-sidecar

## Problem Statement

I have English-language videos — single files and folders of them, 5 to 30 minutes each —
and watching them without subtitles is worse than watching them with subtitles. Not for
accessibility: for comprehension. Dialogue under music, quiet speech, unfamiliar accents,
and watching at low volume all make me miss words.

Producing subtitles by hand is not worth it, and the existing options don't fit:

- Online tools want my videos uploaded, and some of them are private.
- Every Whisper-based tool I've tried makes me learn its flag set before it will do the
  obvious thing (`subie video.mp4`), or hands me a raw dump of the model's segments, which
  is not the same thing as readable subtitles: cues run too long, lines wrap mid-phrase,
  text moves faster than I can read it.
- Tools that add subtitles by re-encoding the video take minutes, degrade the picture, and
  are irreversible. I only want the subtitle file.

## Solution

A command-line tool, `subie`, that takes one or more videos and writes a `.srt` file next
to each one, named after it.

The common case is a single command with no flags:

```
subie video.mp4
```

That prints one line — `video.mp4 → video.srt  127 cues  18.4s` — and nothing else.
Pointing it at a folder does the same for every video in it, skipping the ones already
subtitled.

The subtitle text is not the recognition engine's raw output. It is segmented into cues
that obey subtitle readability rules — at most two lines of 42 characters, at most 20
characters per second, one to seven seconds each — so the result is something a viewer can
actually follow, rather than a wall of text that appears and disappears too fast.

It runs entirely on my machine. Speech recognition runs on my GPU when there is one and on
the CPU when there isn't, with the model chosen to suit. Nothing is uploaded. The video
bytes are never modified, so a bad result costs me a re-run rather than a lost encode.

It arrives on a machine with no Python and no ffmpeg installed, and tells me — via
`subie doctor` — whether the GPU path is genuinely working on that machine.

## User Stories

### The everyday case

1. As a person with a video and subtitles nowhere, I want to run `subie video.mp4` with no
   arguments beyond the path, so that I get a working subtitle file without reading
   documentation first.
2. As a person watching a folder of episodes, I want to point the tool at a folder and have
   every video in it subtitled, so that I don't have to invoke it once per file.
3. As a person who re-runs things, I want a video that already has an up-to-date subtitle
   file to be skipped rather than re-processed, so that a second run over a big folder is
   fast.
4. As a person who re-runs things, I want `--force` to overwrite existing subtitle files,
   so that I can get a fresh result when I suspect the old one is wrong.
5. As a person with many files, I want the run to tell me, per video, what happened — how
   many cues, how long it took — so that I can see progress and spot the ones that failed.
6. As a person with many files, I want the run to end with a summary — how many subtitled,
   how many skipped, how many failed — so that I know whether to look closer.

### Batches and failures

7. As a person subtitling a folder, I want one broken video not to abort the whole run, so
   that I don't have to sort my folder into good files and bad files before starting.
8. As a person subtitling a folder, I want a final exit code that distinguishes "all good"
   from "something failed" from "you used it wrong", so that I can use it in a script.
9. As a person whose folder has subfolders of videos, I want folders to be scanned
   non-recursively by default and only descend when I ask with `-r`, so that a run doesn't
   surprise me by processing things I'd forgotten were there.
10. As a person whose folder contains non-video files, I want those ignored silently, so
    that I don't get a wall of errors about `.txt` files.
11. As a person subtitling many videos on a big machine, I want to tune how many run at
    once with `--jobs`, so that I can trade memory for throughput — but I want the default
    to be one at a time on a GPU, so that I don't silently get a slower, memory-hungrier
    run.

### Readable subtitles, not raw output

12. As a viewer, I want at most two lines per cue, so that the picture isn't buried.
13. As a viewer, I want at most 42 characters per line, so that lines don't sprawl across
    the screen.
14. As a viewer, I want text to appear no faster than 20 characters per second, so that I
    can finish reading before the cue disappears.
15. As a viewer, I want no cue shorter than one second, so that I'm not made to blink at a
    flash of text.
16. As a viewer, I want no cue longer than seven seconds, so that a stuck cue doesn't leave
    me wondering whether the player has frozen.
17. As a viewer, I want a cue to linger about 200 ms past the last spoken word, so that the
    text doesn't vanish the instant the sound stops.
18. As a viewer, I want a clear gap between consecutive cues, so that two cues don't look
    like one long paragraph.
19. As a viewer, I want cues to never overlap, so that I never see text collide with text.
20. As a viewer, I want lines to break at a comma or at a pause rather than mid-phrase, so
    that the cue reads as language rather than as a truncation.
21. As a viewer, I want the two lines of a cue balanced in length, so that the shape of the
    text isn't lopsided.
22. As a viewer, I want short adjacent sentences kept together when they fit, so that the
    screen isn't constantly flashing.
23. As a viewer, I want sentences too long for one cue to be split at a clause boundary, so
    that the split is invisible.
24. As a viewer, I want the first letter of each cue capitalized and the cue punctuated, so
    that each cue reads like a sentence.
25. As a viewer, I want speech fillers (`um`, `uh`) kept, so that removing them doesn't
    change the sense of what was said.
26. As a viewer, I want stray whitespace and space-before-punctuation cleaned up, so that
    the text doesn't look machine-generated.

### Non-speech and junk

27. As a viewer, I want cues that are nothing but music notes (`♪`) dropped entirely, so
    that my subtitles aren't polluted with symbols.
28. As a viewer of a video with music, I want a lone `[Music]` or `[Applause]` cue kept when
    it is the only thing in the cue, so that I understand why nobody is talking.
29. As a viewer, I want non-speech markers stripped out of cues that also contain speech,
    so that `[Music]Hello there` never appears.
30. As a person with a video that opens with thirty seconds of music and title cards, I
    want the tool not to invent dialogue there, so that the subtitle doesn't claim someone
    said "Thanks for watching!" during the intro.
31. As a person with a video that opens with music, I want silence to be excluded before
    recognition rather than filtered after, so that invented text never gets generated at
    all.
32. As a person whose video has one bad stretch of audio, I want that stretch not to
    contaminate everything after it, so that one hallucination doesn't seed the next
    fifty cues.
33. As a person who knows the tool hallucinates over music, I want a small, documented list
    of phantom phrases filtered out when confidence is also low, so that the obvious junk
    disappears without deleting real speech that happens to contain those words.

### Video handling

34. As a person with a video containing no audio stream at all, I want a clear warning and a
    skip, so that I'm not left wondering why nothing appeared.
35. As a person with a video whose audio is entirely music or silence, I want a warning and
    no subtitle file at all, so that I don't end up with an empty file that a player treats
    as a broken subtitle track.
36. As a person with a video in a format I didn't think the tool supported, I want it to
    just work, so that I don't have to convert containers first.
37. As a person running this on a laptop, I want the audio decoded in memory with no
    intermediate files left behind, so that my video folders don't fill with `.wav` litter.
38. As a person debugging a recognition problem, I want the option to keep the extracted
    audio, so that I can listen to what the engine actually heard.
39. As a person with an oddly named video, I want the subtitle file to follow the video's
    name and location, so that players find it automatically.
40. As a person who cares about not corrupting my library, I want the video file itself to
    never be modified, so that a bad run is always recoverable.

### Where subtitles go

41. As a person with a folder of episodes, I want subtitle files written beside their videos
    rather than into a separate output tree, so that players auto-load them without config.
42. As a person who wants them elsewhere, I want `--out-dir` to redirect the output, so that
    I can keep my media folders clean.

### Hardware

43. As a person with an RTX 3070 Ti, I want the tool to use my GPU automatically, so that a
    30-minute video is done in under a minute without me choosing anything.
44. As a person with an RTX 3070 Ti, I want the GPU path to install without me hand-installing
    a CUDA toolkit, so that I don't lose an afternoon to DLL errors.
45. As a person running the tool on a machine with no usable GPU, I want it to fall back to
    the CPU automatically, so that the tool still works.
46. As a person running on CPU, I want a smaller model chosen automatically, so that the run
    is minutes rather than an hour.
47. As a person with a better GPU than mine, I want `--model` to let me ask for a heavier
    model, so that I can trade speed for accuracy.
48. As a person who wants a faster run, I want `--model` to let me ask for a lighter model,
    so that I can trade accuracy for speed.
49. As a person who suspects the GPU is not being used, I want `subie doctor` to tell me the
    resolved device, the GPU name, whether the CUDA libraries actually resolved, and which
    compute type is in use, so that I can see the difference between "detected" and
    "working".
50. As a person installing on the GPU machine, I want `subie doctor` to report the Python
    version, the bundled ffmpeg, the model cache location, and the models present, so that
    one command tells me whether the machine is ready.
51. As a person with no internet on the target machine, I want recognition to fail with a
    clear message about the missing model rather than a stack trace from a download library.
52. As a person using two machines, I want the model downloaded once per machine into a
    predictable location, so that a stale or missing download is something I can reason
    about.
53. As a person who wants to pre-download before going offline, I want a `subie models`
    command to list, pull, and remove models.

### Output discipline

54. As a person running a batch, I want one compact line per video and nothing else, so that
    a 40-file run produces 40 readable lines.
55. As a person debugging a bad result, I want `--verbose` to show the engine's own logging,
    so that I can see what it was doing.
56. As a person scripting this, I want `--quiet` to suppress everything but errors, so that
    my script's output isn't polluted.
57. As a person scripting this, I want the exit code to be 0 for success, non-zero for a
    failed video, and distinct for a usage error, so that I can branch on it.

### Subtitle file format

58. As a person using a normal player, I want standard SRT — numbering from one,
    `hh:mm:ss,mmm` timestamps, one blank line between cues — so that it loads anywhere.
59. As a Windows user, I want CRLF line endings and UTF-8 without a byte-order mark, so that
    Notepad and my player both show it correctly.
60. As a person with accented names in the dialogue, I want UTF-8 preserved end to end, so
    that names aren't mangled.

### Trust and verification

61. As a person relying on this, I want the cue-building rules covered by tests with fixed
    inputs and exact expected subtitle text, so that a change in the rules is a visible diff
    rather than a quiet regression.
62. As a person relying on this, I want an end-to-end test that runs a real short clip
    through the real engine, so that "the pieces work" is verified, not just assumed.
63. As a person with a GPU machine I can't test from here, I want the tool to report its own
    GPU status, so that the GPU path has an acceptance test that doesn't require the CPU
    machine to have a GPU.

## Implementation Decisions

### Shape of the tool

- A Python package with a console entry point named `subie`, laid out as a `uv` project with
  a `src/` layout, `requires-python >=3.12`.
- Subcommands: the default action (positional paths) plus `doctor` and `models`.
- Vocabulary throughout the code and tests follows `CONTEXT.md`: **Video**, **Transcript**,
  **Cue**, **Sidecar**, **Job**, **Run**. The word "caption", "line", and "subtitle file"
  are not used to mean Cue or Sidecar.

### Pipeline for a Job

1. Probe the Video for an audio stream and duration.
2. Skip if a Sidecar exists and is newer than the Video, unless forced.
3. Resolve device and model (unless overridden).
4. Decode audio in memory: 16 kHz mono float32, via PyAV. No temporary files.
5. Recognize: `task="transcribe"`, `language="en"`, word timestamps on, VAD on,
   `condition_on_previous_text=False`, producing a Transcript.
6. Segment the Transcript into Cues by the readability rules.
7. Normalize cue text.
8. Render SRT and write the Sidecar.
9. Report one line.

Each Job is isolated: an exception in one becomes a reported failure for that Job and the
Run continues.

### Recognition

- `faster-whisper` with CTranslate2, running in-process.
- Device probe picks CUDA when the CUDA libraries resolve and a device is visible,
  otherwise CPU.
- Defaults derived from the resolved device, not from a required flag: GPU → `turbo` at
  `float16`; CPU → `small.en` at `int8`.
- `--model` overrides; `--device` forces `auto`/`cuda`/`cpu`.
- GPU inference uses `faster-whisper`'s batched pipeline; the batching window and batch size
  are internal, not flags.
- English-only is enforced in code: the language and task are constants, not options (see
  ADR-0003). There is no language detection, no `--lang`, no `--translate`.
- Model resolution: model names map to a `faster-whisper` model id; download happens on
  first use into a predictable per-machine cache directory, with a clear error if the model
  is absent and the network is unavailable.

### Cue segmentation (the core logic)

- A pure function from Transcript to Cue list: no I/O, no model, deterministic.
- Hybrid greedy-fill: pack words until a limit is hit; break preferentially at sentence
  end, then clause punctuation, then longest pause, then anywhere; never merge across a
  sentence end unless both sentences fit within one cue's limits.
- Timing: in = first word's start; out = last word's end + 200 ms, clipped to the next cue's
  in, extended forward to reach one second minimum where that doesn't violate the clip.
- Reading-speed overflow is handled by splitting, not by stretching: a cue that would
  exceed 20 CPS at its true duration is split into more cues.
- Line breaking balances the two lines and prefers clause boundaries.
- The exact numbers and the precedence when limits conflict are recorded in
  `docs/subtitle-policy.md`; that file is the reference for this module's behaviour and its
  numbers are not duplicated in code comments.

### Text normalization

- Drop cues that are only music notes.
- Keep a bracketed non-speech marker only when it is the sole content of the cue; strip
  markers from cues that contain speech.
- Collapse whitespace, remove space before punctuation, trim.
- Capitalize the first character of the cue and ensure terminal punctuation; leave the
  engine's remaining casing alone.
- Fillers are preserved.

### Hallucination guards

- Silence excluded by VAD before decoding, not filtered afterwards.
- No conditioning on previous text.
- A small blocklist of phantom phrases applied only to low-confidence cues, defined as data
  rather than inline literals so it is testable and documented.

### Sidecar output

- Named after the Video, same directory by default, or `--out-dir`.
- UTF-8 without BOM, CRLF, numbering from 1, `hh:mm:ss,mmm`, one blank line between cues,
  trailing newline.
- Never written when no cues were found: the Job warns and produces nothing.
- The Video file is opened read-only and never written to.

### CLI surface

- Positional paths: files or directories; directories non-recursive unless `-r`.
- `--force`, `--out-dir`, `--jobs`, `--quiet`, `--verbose`, `--model`, `--device`.
- `--keep-audio` to retain decoded audio for debugging; absent by default.
- Exit codes: 0 success (including "all skipped"), 1 any Job failed, 2 usage error.
- Human output: a progress indicator while a Job runs, then one summary line per Job, then a
  Run summary when more than one Job ran. `--verbose` adds engine logs; `--quiet` leaves only
  errors.
- `doctor` and `models` accept the same device/model resolution so they report what the tool
  would actually do.

### Packaging and native dependencies

- Delivered via `uv tool install` from the repository; `uv` supplies the interpreter, so no
  system Python is required (ADR-0004).
- CUDA libraries come from pip as an optional extra (`cuda`), with library directories
  registered before the inference library is imported; a manual CUDA toolkit install is not
  part of the documented path.
- All media I/O goes through PyAV; nothing shells out to `ffmpeg`.
- `doctor` is the acceptance surface for the GPU machine: interpreter, bundled ffmpeg,
  probe, resolved device, GPU name, CUDA library resolution, compute type, cache path,
  models present.

## Testing Decisions

### What makes a good test here

Tests assert **external behaviour**: given these inputs and this environment, the tool
reports this and writes these bytes. No test reaches into the segmenter's internals, counts
internal calls, or asserts on log strings produced by private helpers. The unit of
observation is (exit code, stdout, files on disk).

Fixtures are **transcripts in, subtitle text out** — the seam is high enough that a test
never needs to know how many words a cue holds or what intermediate structure exists.

### The seam

One seam, at the top:

```
run(argv, deps) -> exit code
```

`deps` is the only thing replaced in tests and carries exactly two abilities: a factory that
produces a Transcriber for a given model/device, and a media probe that reports a Video's
duration and audio-stream presence. Everything else — argument parsing, device and model
resolution, recognition options, cue segmentation, normalization, SRT rendering, skip and
freshness logic, output paths, exit codes, reporter output, `doctor`, `models` — is the real
code under test.

A second, lower seam inside the segmenter was considered and deliberately not taken:
golden-SRT assertions through the top seam cover the rules and their rendering together. If
the segmenter later needs randomized or property-based testing for line-breaking invariants,
that lower seam gets added then, not now.

### Test layers

1. **Unit / golden tests (default run, seconds, no model).** Feed a fixture Transcript through
   `run`, assert exit code, exit-summary output, and the exact bytes of the written Sidecar.
   One fixture per behaviour: limit breaches, clause-boundary breaks, sentence merging,
   min/max duration, non-overlap, gap, padding, music-only cue, bracketed marker, fillers,
   whitespace and punctuation cleanup, capitalization.
2. **CLI and filesystem behaviour tests (default run).** Same seam: single file, directory,
   non-recursive vs `-r`, non-video files ignored, skip-when-fresh, `--force`, `--out-dir`,
   missing file, no-audio-stream Video, no-speech Video, one failing Job among successes,
   exit codes 0/1/2, `--quiet`/`--verbose`, SRT encoding and line endings.
3. **`doctor` and `models` tests (default run).** Through the same seam with a fake probe and
   fake transcriber factory, asserting the reported fields — in particular that a device that
   resolves but whose libraries do not is reported as *not working*, not as available.
4. **End-to-end (`-m slow`, excluded by default).** A generated ~15 s clip with known speech
   through the real engine and the real Transcriber: assert the Sidecar is well-formed, its
   cue count is plausible, and its text contains the words that were spoken. Skipped when the
   model is not present.

### Prior art

The repository has no tests yet, so these establish the convention: `pytest`, golden-file
fixtures kept as small text files next to the tests that use them, and a `slow` marker for
anything that downloads a model.

### The GPU path

Not testable on the CPU machine and not faked beyond the library-resolution boundary. Its
test is `subie doctor` on the GPU machine reporting a resolved device, a GPU name, resolved
cuBLAS/cuDNN, and the expected compute type — plus a real run whose reported per-Job time is
consistent with GPU throughput.

## Out of Scope

- **Burn-in** and **soft track** output — only the Sidecar is produced (ADR-0001).
- **Translation**, language detection, and any non-English speech (ADR-0003).
- **Diarization** (who said it) and **SDH** conventions (sound descriptions, speaker labels).
- **Subtitle styling**: fonts, sizes, colours, positions — meaningless without burn-in.
- **Karaoke/highlight** subtitles and word-level animation.
- **Timing repair tools**: global offset/sync adjustment, manual editing, or a review UI.
- **Objective/cue-level quality metrics** against reference subtitles.
- **A config file.** Flags only in v1; revisit if the same flag gets repeated.
- **Cloud recognition APIs** and any network upload of video content.
- **GUI, web UI, watch mode, or a daemon.**
- **Subtitle formats other than SRT** (VTT, ASS) — trivially addable later, unnecessary now.

## Further Notes

- **Order of work is risk order.** The GPU machine cannot be inspected from the CPU machine,
  and CUDA library resolution on Windows is the most likely thing to fail. `doctor` should
  therefore exist early, not last, so the GPU machine can be certified before the rest of the
  pipeline depends on it.
- **The segmenter is where the tuning will happen.** The readability numbers in
  `docs/subtitle-policy.md` are the broadcast defaults and were chosen conservatively; real
  material with fast dialogue and crosstalk will show where they fight. Because they live in
  one documented place and the segmenter is pure, tuning is a fixture change plus a re-run,
  not a refactor.
- **42 characters per line is a deliberate bet against current taste.** Web players handle 50+
  comfortably. Broadcast-standard 42 is easier to relax later than 50 is to walk back once
  people have seen it.
- **Confidence for the blocklist** comes from the engine's per-segment no-speech and average
  log-probability values; the threshold is a documented constant, not a magic number inline
  in the filter.
- **Accepted quality ceiling:** the engine will still mishear proper nouns, and no
  post-processing fixes that. The tool's job is to make the transcript that exists readable,
  not to make it correct.