# subie

A command-line tool that writes English subtitles for English-language videos.

## Language

**Video**:
An input media file with an audio stream, whose speech is assumed to be English.
_Avoid_: clip, input, media file, source

**Transcript**:
The speech-recognition engine's raw output: words with timings, plus confidence. Never
shown to a user directly; it is the material a Cue list is derived from.
_Avoid_: raw text, speech-to-text result, recognition output

**Cue**:
One on-screen subtitle event — a start time, an end time, and at most two lines of text.
The unit that is written to a Sidecar. A Cue is shaped by readability, not by whatever
boundaries the engine produced, so many Cues never match a Transcript segment 1:1.
_Avoid_: line, caption, block, entry, subtitle event

**Sidecar**:
The `.srt` file this tool writes for a Video, named after it. Beside the Video by
default; `--out-dir` redirects it. The only artifact produced. Bytes of the Video are
never modified.
_Avoid_: subtitle file, output file, subs, captions file

**Job**:
One Video's passage through the pipeline, from probe to written Sidecar. Fails and
skips are per-Job and never abort the others.
_Avoid_: task, item, unit of work, file

**Skip**:
A Job that wrote no Sidecar and did not fail: either a current Sidecar already existed
or the Video's audio contained no speech. A Skip never makes a Run fail.
_Avoid_: ignore, no-op

**Run**:
One invocation of the tool, covering zero or more Jobs. It ends in a summary of
subtitled, skipped, and failed counts when it covers more than one Video.
_Avoid_: session, batch

**Zero-arg Run**:
A Run with only a path — no model, device, or output flags. The preset every other
behaviour descends from.