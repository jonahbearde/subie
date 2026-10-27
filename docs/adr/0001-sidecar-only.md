# Sidecar only: no burn-in, no soft track

The tool's only artifact is a `.srt` **Sidecar** beside the **Video**. We do not render
subtitles into pixels (burn-in) and do not mux a subtitle stream into the container
(soft track).

The trade-off is real, because burn-in is what most people picture when they say "add
subtitles": it survives any player, any upload, any screenshot, while a sidecar needs a
player that will load it. The cost of burn-in is a full video re-encode — minutes of GPU
time, a quality decision (codec, CRF), and a styling subsystem (font, size, outline,
position) that can never be undone once written. A soft track avoids re-encoding but is
invisible in many players, so it fails the same "just works everywhere" test in a
different way.

Choosing sidecar keeps the whole pipeline non-destructive and lets a bad transcript be
stimulus for a re-run instead of a lost encode. If burn-in is ever wanted, it belongs as
a second renderer over the same Cue list — a decision to be revisited then, not smuggled
in as an option of the transcription pipeline.

One debug-side exception is recorded here rather than left implicit: `--keep-audio`
deliberately writes a `<stem>.keep-audio.wav` beside the Video so a recognition problem
can be listened to. It is off by default, is not a product artifact, and never replaces or
modifies the Sidecar. The guarantee this ADR makes is about subtitle output: normal runs
produce the Sidecar and nothing else.
