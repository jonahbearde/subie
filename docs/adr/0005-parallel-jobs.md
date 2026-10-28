# Parallel Jobs: threads, one recognition engine per Job

`--jobs N` runs up to N Jobs at once in one process, one Python thread per Job. Every Job
builds its own Transcriber — its own `faster-whisper` model, decoder state and CUDA
context. Nothing model-shaped is shared.

## Considered Options

- **One engine per Job, on threads (chosen).** CTranslate2's `num_workers` defaults to 1,
  so concurrent `transcribe()` calls on one `WhisperModel` queue behind each other. Real
  overlap therefore needs either one engine per Job or a shared engine configured with
  `num_workers = --jobs`. One engine per Job keeps each Job as isolated as the rest of the
  pipeline promised, makes the memory cost of `--jobs N` exactly N models, and lets a
  fake Transcriber at the test seam observe the same overlap the real engine produces.
- **One shared engine with `num_workers = --jobs`.** The least memory, but it hides a
  second concurrency control inside the engine, couples Jobs that are supposed to be
  independent, and changes what `make_transcriber` means. Worth revisiting only if the
  memory cost of N models becomes the thing that hurts.
- **A process pool.** Full isolation, but every worker re-imports CTranslate2 and re-loads
  the model anyway, and audio would cross a process boundary for no gain. Threads share
  nothing mutable except the reporter, which prints on the collecting thread.

## Consequences

- Memory grows with `--jobs`: N models in RAM or VRAM. The defaults keep that sane — 1 on
  CUDA, where one model already saturates the GPU, and a small fraction of the cores on
  CPU (`max(2, cores // 4)`, capped at 8). `--jobs` is the explicit trade, and its help
  text says it costs memory.
- A Sidecar's bytes never depend on `--jobs`. Segmentation is pure given a Transcript and
  each Job writes only its own Sidecar. Two Videos that would resolve to one Sidecar path
  are a usage error rather than a race, which is what makes that invariant hold.
- Progress lines are printed by the thread that collects finished Jobs, so two Jobs cannot
  write halves of one line. They appear in completion order, not target order.
- An interrupted Run stops starting queued Jobs. A Job already inside CTranslate2 still
  finishes, because inference cannot be cancelled mid-decode.
- `make_transcriber` is called once per Job, not once per Run. That is what makes Jobs
  independent, and it is why the fake Transcriber can count overlapping calls.