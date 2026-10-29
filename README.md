# subie

Writes English `.srt` subtitles for English-language videos. It runs on your machine:
nothing is uploaded, and the Video is never modified — the only artifact is the Sidecar.

## Start here

```console
subie video.mp4
```

That is the whole command. It writes `video.srt` beside `video.mp4` and prints one line:

```text
video.mp4 → video.srt  127 cues  18.4s
```

Point it at a folder and it subtitles every Video directly inside it. Videos that already
have an up-to-date Sidecar are skipped, so a second run is cheap:

```console
subie Videos              # every Video directly in Videos/
subie Videos -r           # ... and in its subfolders
```

## Install

`subie` needs [uv](https://docs.astral.sh/uv/), a single binary that supplies its own
Python. You do **not** need Python, `ffmpeg`, or a CUDA Toolkit.

On Windows PowerShell, install uv once:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### GPU machine

One command installs the tool and the CUDA runtime wheels:

```console
uv tool install "subie[cuda] @ git+https://github.com/jonahbearde/subie.git"
```

Then verify the GPU path:

```console
subie doctor
```

`subie doctor` downloads nothing. It prints one field per fact and ends with `result`. An
abridged GPU-ready report:

```text
subie doctor

  python          …
  ffmpeg          …
  media probe     ok: read a 0.10 s test clip with an audio stream
  device          cuda
  gpu             NVIDIA GeForce RTX 3070 Ti
  cuda libraries  cuBLAS resolved (…); cuDNN resolved (…)
  compute type    float16
  model           turbo (default for cuda)
  model cache     …
  models present  none
  result          ready: the GPU path is usable
```

If `doctor` reports the GPU path as unavailable:

- **`gpu ... not usable` and `cuda libraries ... not resolved`.** The CUDA runtime wheels
  are missing or a DLL failed to load. Reinstall with the same one-command install plus
  `--force` (the exact line is in [`docs/install.md`](docs/install.md)). The
  `cuda libraries` line names the DLL that failed. If it still fails, update the NVIDIA
  driver and check that `nvidia-smi` lists the GPU.
- **`gpu none visible`.** The driver does not expose an NVIDIA GPU to this machine. The
  CPU path still works: `device` will be `cpu` and the model `small.en`.
- **`doctor` exits 0 when the CPU path is ready, even if the GPU is not.** For a script
  that requires CUDA, run `subie doctor --device cuda`, which exits 1 when CUDA is not
  usable. A normal Run with `--device cuda` also fails rather than silently falling back;
  `--device cpu` accepts the CPU path on purpose.

These commands use Git, which uv needs to fetch the repository. If Git is unavailable,
[`docs/install.md`](docs/install.md) gives the repository-ZIP and local-path install,
offline model preparation, updating and more detailed troubleshooting.

### CPU-only machine

```console
uv tool install "subie @ git+https://github.com/jonahbearde/subie.git"
subie doctor
```

The CPU path is ready when `doctor` reports `device cpu`, `compute type int8`,
`model small.en (default for cpu)` and a `result` starting `ready`. No CUDA libraries are
needed.

If `subie` is not found after installing, run `uv tool update-shell` and open a new
terminal.

### The first run downloads a model

The first Run fetches its model into the per-machine Model cache (`doctor` prints the exact
path). On a GPU that is `turbo`; on the CPU it is `small.en`. To prepare a machine before
going offline, pull the model explicitly:

```console
subie models pull turbo      # or small.en on a CPU machine
subie models list            # what is cached, and how large
```

The cache is per machine and predictable: `%LOCALAPPDATA%\subie\models` on Windows,
`~/Library/Caches/subie/models` on macOS, and `$XDG_CACHE_HOME/subie/models` (or
`~/.cache/subie/models`) on Linux. `doctor` reports the resolved path; nothing else needs
to know it.

## Use it

```text
subie [options] VIDEO [VIDEO ...]
```

A path may be a Video file or a folder. Folders are scanned non-recursively unless `-r` is
given, and non-video files in them are ignored silently. A Sidecar is written beside its
Video by default, named after it.

| Flag | What it changes |
|---|---|
| `-r`, `--recursive` | Also process Videos in subfolders. |
| `--force` | Re-process Videos whose Sidecar is already up to date. |
| `--out-dir DIR` | Write every Sidecar into `DIR`, named after its Video, instead of beside it. Two same-named Videos from different folders would collide and are a usage error. |
| `--jobs N` | Keep up to `N` Jobs in flight. Defaults to 1 on CUDA and `max(2, cores // 4)` capped at 8 on CPU. More Jobs cost more memory (one model each); Sidecar bytes never change. |
| `--model NAME` | Use a named model instead of the device default. `subie models --help` lists the known names. A heavier model is slower and more accurate; a lighter one is faster. |
| `--device auto\|cuda\|cpu` | `auto` (the default) uses CUDA only when it genuinely works, otherwise CPU. `cuda` fails if CUDA is not usable; `cpu` forces the CPU. |
| `--keep-audio` | Keep the decoded audio for inspection. See below. |
| `--quiet` | Print errors only: no per-Video lines, warnings or Run summary. |
| `--verbose` | Add the recognition engine's own logging on stderr. |
| `--version` | Print the version and exit. |

The defaults follow the device that was actually resolved, not a flag you must remember:
GPU → `turbo` at `float16`; CPU → `small.en` at `int8`. `--model` changes only the model,
not the device. `.en` models are English-only and are the better choice per unit of
compute.

### Inspect what the engine heard: `--keep-audio`

```console
subie video.mp4 --keep-audio
```

This writes `video.keep-audio.wav` beside the Video: 16 kHz mono PCM, the exact audio the
recognition engine was given. Open it in any player when a Cue is wrong and you need to
know whether the engine misheard the Video or the words were never clear. It is written
before recognition, so it survives a no-speech warning or a recognition failure, and it is
never written by a normal run. With `--out-dir` the Sidecar moves; the kept audio still
sits beside the Video. Delete it when you are done — it is not a product artifact.

## What it writes

The Sidecar is standard SRT: UTF-8 without a BOM, CRLF line endings, numbering from 1,
`hh:mm:ss,mmm` timestamps, one blank line between Cues, and a trailing newline. The Video
is opened read-only and is never modified; a bad result costs a re-run, not a lost encode.

A Video with no speech produces a warning and **writes no Sidecar** — never an empty file
that a player would treat as a broken subtitle track.

## Skipping, forcing and exit codes

- A Video with a Sidecar at least as new as the Video is skipped with
  `video.mp4 → video.srt  skipped (up to date)`. No model is loaded and the Video is not
  decoded.
- `--force` ignores that freshness check and writes a fresh Sidecar.
- A Video with no detected speech is skipped with a warning, writes nothing, and does not
  make the Run fail. A Video with no audio stream is a failure, not a skip: it is reported
  on stderr and the Run exits 1. Audio that is only silence or music is a skip.
- A failed Job is reported on stderr and does not stop the other Jobs. A Run over more than
  one Video ends with `N subtitled, N skipped, N failed`.

| Exit code | Meaning |
|---|---|
| 0 | Every Job succeeded or was skipped. All-skipped is success. |
| 1 | At least one Job failed, or `subie doctor` found the machine not ready. |
| 2 | Usage error: bad flag or value, unknown model or device, a missing path argument, two Videos that would write one Sidecar, or an unusable `--out-dir`. |

Branch on the code in PowerShell:

```powershell
subie .\Videos -r
switch ($LASTEXITCODE) {
    0 { Write-Host "all Videos are subtitled" }
    1 { Write-Error "at least one Video failed; see the errors above" }
    2 { Write-Error "subie was invoked incorrectly" }
    default { Write-Error "subie exited with $LASTEXITCODE" }
}
```

The same thing in a POSIX shell:

```bash
subie ./Videos -r
code=$?
case $code in
  0) echo "all Videos are subtitled" ;;
  1) echo "at least one Video failed; see the errors above" >&2 ;;
  2) echo "subie was invoked incorrectly" >&2 ;;
  *) echo "subie exited with $code" >&2 ;;
esac
exit "$code"
```

`--quiet` suppresses stdout entirely but keeps errors and the exit code, so it is the
right flag for a script that reads stderr on failure.

## How the Cues are built

The recognition engine's own segments are not the output. A Cue holds **one sentence**, the
way a subtitler shapes it: a run of words ending at punctuation, or at a silence long
enough to end the thought. Two full sentences never share a Cue; a one-word Cue never
flashes by itself either — a sentence too slight to read alone joins a neighbour. A sentence
too long for one Cue is cut in half near its middle, at a sentence or clause boundary where
one exists, and each half is cut again if it is still too long.

Every Cue still obeys the readability limits: at most 2 lines of 42 characters, at most 20
characters per second, 1 to 7 seconds each, a 100 ms gap between Cues and 200 ms of
trailing padding. The 1-second minimum outranks both the gap and the reading-speed limit, so
a Cue that needs room to be read takes it and speech that is itself faster than 20 CPS stays
one Cue instead of flashing past word by word. The two lines of a Cue are balanced rather
than leaving one word stranded. Expect a faster reading pace and many more Cues than the old
packing produced.

[`docs/subtitle-policy.md`](docs/subtitle-policy.md) is the reference for those numbers and
for the text rules: music-only Cues are dropped, bracketed non-speech markers are kept only
when they are the whole Cue, fillers such as `um` are preserved, and a small documented
blocklist removes invented phrases only when the engine also reports low confidence.
Changing a number there is a behaviour change, not a tweak.

## Known limitations

- **Proper nouns and names can be misheard.** There is no name correction and no editing
  pass; the tool makes the Cues readable, not correct.
- **Music, applause and heavy effects can confuse the engine.** Voice-activity detection
  and the phantom-phrase blocklist reduce invented lines, but cannot eliminate them. A
  confident-sounding invention can still survive.
- **English only.** The language is fixed, not detected. A non-English Video is
  unsupported and will produce nonsense rather than a translated result. There is **no translation**.
- **The Sidecar is the only output.** No burn-in, no muxed subtitle track, no styling,
  fonts or positions. Your player must load the `.srt` beside the Video (or you must point
  it at the file).
- **No speaker labels, SDH or karaoke.** There is no diarization, no sound description, no
  word highlighting, no timing repair or offset tool, and no editing UI.
- **Cue limits are conservative broadcast defaults.** Fast crosstalk or overlapping speech
  may be split more than you would like. The numbers are a policy decision, not a flag.
- **The first run needs the model.** Without a network, pull it first with
  `subie models pull`; on a truly offline machine, copy the model cache from a connected
  one using the path `doctor` reports.
- **CPU is much slower than GPU.** `--jobs` trades memory for throughput; it does not make
  the model smaller. The GPU path is only as good as the installed driver and CUDA
  libraries, and a driver is not bundled.
- **No config file.** Every choice is a flag in this version.

## Commands

```console
subie doctor                 # is this machine ready? (downloads nothing)
subie models list            # what is in the cache, and how large
subie models pull small.en   # download a model before going offline
subie models rm small.en     # delete one from the cache
```

`doctor` reports the interpreter, the bundled FFmpeg (from PyAV), a live media probe, the
resolved device, the GPU name, whether cuBLAS and cuDNN actually resolved, the compute
type, the model that device would use, the cache path and the models present. It is the
acceptance surface for a GPU machine: "detected" and "working" are deliberately separate
lines.

`models` works on that same cache and is device-independent: it lists what is present with
sizes, pulls one ahead of time, and removes one. A model already cached is used without
touching the network.

## Development

```console
uv sync
uv run pytest                 # fast tests: no model, no GPU, no network
uv run pytest -m slow         # real engine, real audio; skips without a cached model
uv run ruff check .
uv run mypy
uv run subie doctor
```

## Project docs

- [`docs/subtitle-policy.md`](docs/subtitle-policy.md) — the cue limits and text rules.
- [`docs/install.md`](docs/install.md) — install details, offline machines and
  troubleshooting.
- [`CONTEXT.md`](CONTEXT.md) — the vocabulary used in the code and tests.
- Architecture decisions:
  - [`docs/adr/0001-sidecar-only.md`](docs/adr/0001-sidecar-only.md)
  - [`docs/adr/0002-python-faster-whisper.md`](docs/adr/0002-python-faster-whisper.md)
  - [`docs/adr/0003-english-only.md`](docs/adr/0003-english-only.md)
  - [`docs/adr/0004-distribution-and-native-deps.md`](docs/adr/0004-distribution-and-native-deps.md)
  - [`docs/adr/0005-parallel-jobs.md`](docs/adr/0005-parallel-jobs.md)
  - [`docs/adr/0006-one-sentence-per-cue.md`](docs/adr/0006-one-sentence-per-cue.md)
- [`.scratch/auto-sidecar/spec.md`](.scratch/auto-sidecar/spec.md) — the full specification
  the tool was built from.