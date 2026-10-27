# Python with faster-whisper, not a Node wrapper around a whisper.cpp binary

Recognition runs in-process through `faster-whisper` (CTranslate2), in Python.

## Considered Options

- **Node/TypeScript driving the prebuilt `whisper-cublas-12.4.0-bin-x64.zip`.** Attractive
  because it is one self-contained binary with no interpreter, and because this project's
  author works in TS by default. Rejected because everything interesting afterwards —
  Silero VAD integration, word-timestamp access, cue segmentation and line-breaking — would
  have been reimplemented in TS around a process boundary, while still requiring a 429 MB
  manual download and a system `ffmpeg`.
- **Cloud API** (OpenAI, Deepgram, AssemblyAI). Better accuracy on hard audio, but uploads
  private video and adds a per-minute cost for a task a local GPU does in under a minute.
- **Python with openai-whisper.** Same models, ~4× slower, no batched inference, worse
  performance ceiling on the RTX 3070 Ti.

## Consequences

- Silero VAD (`vad_filter`) comes for free, which is the main defence against Whisper
  inventing text over music and applause.
- `BatchedInferencePipeline` is what makes a 30-minute video finish in well under a minute
  on the GPU; it is a faster-whisper-only facility.
- The tool is a Python package, so delivery needs an interpreter on machines that may have
  none — handled in ADR-0004.