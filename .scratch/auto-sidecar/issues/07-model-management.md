# 07: Model management

**What to build:** Control over the models the tool downloads and uses, so that a machine can be prepared before it goes offline and a stale cache can be reasoned about. `subie models list` shows what is present with sizes, `subie models pull <name>` downloads one ahead of time, and `subie models rm <name>` removes one. The cache lives in a predictable per-machine location that doctor already reports. Asking for a model that cannot be fetched produces a clear message naming the model and the cache path, never a download-library traceback, and `--model` rejects an unknown name before any work starts.

**Blocked by:** 02.

Status: done

- [x] `subie models list` reports each model present in the cache with its size, and says so plainly when the cache is empty.
- [x] `subie models pull <name>` downloads the model, reports progress, and the model then appears in `list` and is used by a Run without further network access.
- [x] `subie models rm <name>` removes it, and a later Run reports the clear missing-model message.
- [x] Pulling with no network fails with a message naming the model and the cache location, and no stack trace.
- [x] `--model` with a name that is neither cached nor pullable fails before any decoding starts.
- [x] The cache location reported by `subie doctor` and the location used by `models` and by a Run are the same one.
- [x] Tests cover list, pull, remove, and the offline failure through the single agreed seam, with the download step faked so no test needs the network.

## Comments

Implemented as `subie models list|pull|rm`, with the download itself added to the existing
`Deps` seam as a fourth ability.

**One cache, one layout.** `models.models_dir()` stays the only answer to "where do models
live", and the layout inside it is Hugging Face's own cache layout
(`models--<org>--<repo>/snapshots/<rev>/…`), because that is exactly what
`faster_whisper.WhisperModel(download_root=…)` reads. `pull` therefore calls
`huggingface_hub.snapshot_download(cache_dir=models_dir(), allow_patterns=…)` — the same
call faster-whisper would have made for itself — so a pulled model is not a second copy
of a model, it is *the* model. `MODEL_FILES` in `models.py` names the file set, mirroring
faster-whisper's downloader.

**Presence means usable.** `present_models()` now requires a snapshot directory holding
`config.json`, `model.bin` and `tokenizer.json` rather than merely a directory with the
right name — the three files a load needs with no network to fetch a missing tokenizer.
A download that died halfway used to be reported as present, which would have made
`models list`, `doctor` and a Run disagree; doctor's `models present` test was updated to
build a realistic snapshot, and a test pins every rung: no snapshot, snapshot without a
tokenizer, snapshot that loads.

**Offline by construction.** When a model is present, `engine.make_transcriber` passes
`local_files_only=True`, so a Run never even looks at the network for a model it already
has. That is what makes `pull` a genuine preparation step rather than a warm-up.

**Where the model is guaranteed.** `pipeline.ensure_model` is called once per Run, right
after device/model resolution and before the first Job. An uncached model is downloaded
there, and presence is checked again afterwards, so both a failed download and one that
"completes" without leaving a usable model fail before a single frame is decoded (verified
by `--keep-audio`: no WAV is written). A failure is cached in the Run's existing
`settings_failure` slot, so a 40-Video folder does not attempt the download 40 times. Ticket 02's "keep-audio survives a model failure" is deliberately
narrowed by this: the trade is that an unpullable model now costs nothing at all.

**Output.** `models list` prints the cache path and a `model / size / repository` table, or
`none in the cache; pull one with 'subie models pull <name>'`. `pull` prints a start line,
lets the download library draw its own progress bars on stderr, then prints
`pulled <name>  <size>`; pulling a model that is already there is a no-op that says so.
`rm` prints `removed <name>  <size>`, and removing something absent is an error naming
the model and the cache. Failures flush stdout first, so a redirected run cannot print the
error above the line it refers to. `list` speaks the catalog's vocabulary, exactly as
`doctor`'s "models present" always has: a cache entry that is not one of the known models
is not listed (and so not removable through `rm`), rather than appearing as an unnamed
blob.

**Deviation from the spec, deliberately.** The spec originally said "`doctor` and
`models` accept the same device/model resolution". `models` takes no `--device`/`--model`:
the cache is per machine, not per device, and making `models list` probe the GPU would
put a CUDA probe in front of a directory listing. `doctor` remains the command that
reports the resolved device, the model it would use, and the cache; a test pins that
doctor and `models` report the same cache path and that a Run uses it.

**Seam.** `Deps` gained `download_model(repo_id, *, destination)`. Tests replace only it:
`FakeModelDownloader` writes a small, complete cache entry (or raises, globally or per
repository), and nothing in the suite touches the network. The fake builds its directory
through `models.cache_path_for`, so the layout rule lives in one place;
`huggingface_hub` is now a declared dependency rather than one inherited from
faster-whisper.

**Review.** The commit was reviewed on two axes (standards and spec). Findings, all
addressed in it: a snapshot without `tokenizer.json` was reported present but could only
load by fetching a tokenizer; `ensure_model` did not re-check presence after a download;
`huggingface_hub` was an undeclared import; one test computed `re.fullmatch(...)` without
asserting it, and the half-download test only exercised the missing-directory rung; the
cache helpers used "repo" where the glossary says **Model**, and the test fake duplicated
the cache layout. `.scratch/auto-sidecar/spec.md` was amended where it had drifted (the
seam's abilities and the `doctor`/`models` sentence) instead of leaving the contradiction
in this comment alone.

### Evidence

Default suite: 125 passed, 1 deselected (`slow`). `ruff check` clean, `ruff format
--check .` clean (two files that were already unformatted at HEAD were reformatted
incidentally), `mypy` clean (35 files).

The real path was exercised on this Windows machine, with `SUBIE_HOME` pointed at a
scratch directory:

```
$ subie models pull tiny.en
Fetching 4 files: 100%|##########| 4/4 [00:23<00:00,  5.97s/it]
pulled tiny.en  74.5 MB

$ subie models list
subie models

  cache  C:\Users\...\subie-model-check\models

  model    size     repo
  tiny.en  74.5 MB  Systran/faster-whisper-tiny.en

$ subie doctor --device cpu
  model cache     C:\Users\...\subie-model-check\models
  models present  tiny.en
```

A Run with the network genuinely switched off (`HF_HUB_OFFLINE=1`) used that pulled model
on a locally synthesised clip:

```
clip.wav → clip.srt  1 cue  1.4s

1
00:00:00,000 --> 00:00:02,780
The quick brown fox
jumps over the lazy dog.
```

Pulling offline:

```
$ HF_HUB_OFFLINE=1 subie models pull small.en
pulling small.en (Systran/faster-whisper-small.en) into C:\Users\...\models
subie: error: cannot download model 'small.en' (Systran/faster-whisper-small.en) into the
cache at C:\Users\...\models: Cannot find an appropriate cached snapshot folder for the
specified revision on the local disk and outgoing traffic has been disabled. …
EXIT=1
```

And a Run asked for a model that is neither cached nor pullable, with `--keep-audio`: the
model error above appeared, exit 1, no Sidecar and no `*.keep-audio.wav` — nothing was
decoded. `subie models rm tiny.en` then reported `removed tiny.en  74.5 MB`, `list` said
`none in the cache`, and removing it again was a clear error.
