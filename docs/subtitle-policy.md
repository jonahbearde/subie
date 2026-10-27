# Subtitle policy

Numbers and rules, not vocabulary — see `CONTEXT.md` for terms. This file is the reference
for the cue segmenter and its tests; changing a number here is a behaviour change.

## Readability limits

A Cue must satisfy all of these, in this precedence order when they conflict:

| Limit | Value | Why |
|---|---|---|
| Characters per line | 42 | Broadcast/Netflix default (EBU). Chosen over 46 for wide player compatibility |
| Lines per cue | 2 | Never three |
| Reading speed | 20 CPS | Adults, subtitle standard |
| Cue duration | 1 s min, 7 s max | Below ~0.8 s the eye cannot land; above 7 s the cue feels stuck |
| Trailing padding | 200 ms past last word | Perceptual comfort |
| Gap between cues | 100 ms | Stops players merging adjacent cues visually |
| Minimum room | out never overlaps next cue's in | Overlap reads as a glitch |

When a sentence cannot fit within 2 × 42 characters at 20 CPS, split it — at a clause
boundary, never mid-phrase.

## Cue construction (hybrid greedy-fill)

1. Start from word timings (`word_timestamps=True`).
2. Fill a cue word by word until adding the next word would break any limit above.
3. Prefer to break at, in order: sentence end (`.` `?` `!`), clause boundary (`,` `;` `:`),
   the longest inter-word pause, then anywhere.
4. Never merge across a sentence end unless *both* sentences fit inside one cue's limits.
5. `in` = first word's start; `out` = last word's end + 200 ms, clipped to the next cue's
   `in`, and extended forward to 1 s if the cue would be shorter.
6. Balance the two lines rather than filling line 1 to 42 characters and leaving line 2
   with one word.

## Text normalization

- Strip bare `♪` and cues consisting only of music notes — delete the cue entirely.
- Keep bracketed non-speech markers (`[Music]`, `[Applause]`) only when the cue contains
  nothing else; otherwise strip them from mixed speech.
- Collapse repeated whitespace; remove space before punctuation; trim ends.
- Capitalize the first character of the cue's first line; ensure terminal punctuation.
  Leave Whisper's remaining casing untouched.
- Keep fillers (`um`, `uh`) — removing them desyncs the meaning of the rest.

## Hallucination guards

Whisper invents fluent text over music, silence, and applause. All three guards are on by
default:

- Silero VAD (`vad_filter=True`) so silence never reaches the decoder.
- `condition_on_previous_text=False` so one bad segment cannot seed the next.
- A small documented blocklist (`Thanks for watching`, `Subscribe to my channel`, …)
  applied only to low-confidence cues, so genuine speech containing those phrases survives.

A Video with no detected speech produces a warning and no Sidecar — never an empty file.

## Output format

UTF-8 without BOM, CRLF line endings, numbering from 1, `hh:mm:ss,mmm` timestamps, one
blank line after each cue, file ends with a single newline.