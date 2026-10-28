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
| Minimum room | out never overlaps next cue's in | Overlap reads as a glitch |
| Gap between cues | 100 ms | Stops players merging adjacent cues visually |
| Trailing padding | 200 ms past last word | Perceptual comfort |

When a sentence cannot fit within 2 × 42 characters at 20 CPS, split it — at a clause
boundary, never mid-phrase.

Reading speed is the Cue's characters divided by its on-screen duration (`out - in`), so the
trailing padding and the 1 s minimum count as reading time.

## Cue construction (hybrid greedy-fill)

1. Start from word timings (`word_timestamps=True`).
2. Fill a Cue word by word until adding the next word would break a line or duration
   limit. If the resulting Cue would exceed the reading-speed limit, split it at the best
   boundary below and repeat on each part; never stretch it.
3. Prefer to break at, in order: sentence end (`.` `?` `!`), clause boundary (`,` `;` `:`),
   the longest inter-word pause, then anywhere.
4. Never merge across a sentence end unless *both* sentences fit inside one cue's limits.
5. `in` = first word's start; `out` = last word's end + 200 ms, clipped to
   `next_in - 100 ms` to reserve the gap but never earlier than the last word's end. Where
   the silence is shorter than the gap, `out` is clipped to `next_in` and the gap shrinks.
   The 1 s minimum may extend `out` into the gap.
6. Balance the two lines rather than filling line 1 to 42 characters and leaving line 2
   with one word. A sentence or clause boundary is used for the line break only when the
   shorter line is at least half the longer line; otherwise balance at a word boundary.

## Text normalization

Cleaning happens per Cue, after grouping and before line breaking, and every limit above
is measured against the cleaned text. So a Cue that cleaning lengthens (a missing full
stop costs a character) is re-checked and split rather than written oversized.

- Strip bare `♪` and Cues consisting only of music notes — delete the Cue entirely. A word
  that is nothing but notes never reaches a Cue in the first place.
- Keep bracketed non-speech markers (`[Music]`, `[Applause]`) only when the Cue contains
  nothing else; otherwise strip them from mixed speech. A marker-only Cue is shown exactly
  as the engine wrote it: a marker is not a sentence, so it is neither capitalized nor
  punctuated.
- A marker the engine emitted as its own Segment is a Cue of its own and never merges with
  the speech around it, so a `[Music]` at the start of a video survives as `[Music]`.
- Collapse repeated whitespace; remove space before punctuation
  (`,` `.` `;` `:` `?` `!` `…` `%`); trim ends.
- Capitalize the Cue's first letter (stepping over a leading quote), and ensure terminal
  punctuation: a missing stop is added, and a dangling `,` `;` `:` or dash becomes `.`.
  Closing quotes and brackets stay outside the punctuation. A Cue that starts with a digit
  has no letter to capitalize. Leave the engine's remaining casing untouched.
- Keep fillers (`um`, `uh`) — removing them desyncs the meaning of the rest.

## Hallucination guards

Whisper invents fluent text over music, silence, and applause. All three guards are on by
default:

- Silero VAD (`vad_filter=True`) so silence never reaches the decoder.
- `condition_on_previous_text=False` so one bad segment cannot seed the next.
- A small documented blocklist applied only to low-confidence Cues, so genuine speech
  containing those phrases survives.

The blocklist is data, in `src/subie/guard.py`. Changing either the list or the thresholds
is a behaviour change:

- `PHANTOM_PHRASES` — what the engine invents over music: `thanks for watching`,
  `thank you for watching`, `thanks for watching and subscribing`, `please subscribe`,
  `subscribe to my channel`, `like and subscribe`, `see you in the next video`. A phrase
  matches case- and punctuation-insensitively, anywhere in the Cue.
- `LOW_AVG_LOGPROB` = -1.0 — a Segment is low confidence at or below this average
  log-probability.
- `HIGH_NO_SPEECH_PROB` = 0.6 — a Segment is low confidence at or above this no-speech
  probability.

A Cue-sized range is low confidence only when *every* Segment it came from trips one of the
two thresholds; a range the engine reported no confidence for at all counts as trusted,
because deleting real speech is the worse failure. The guard runs on each sentence-sized
range *before* neighbouring sentences are merged into one Cue, so a doubtful invention is
dropped on its own and never takes the confident speech next to it down with it. A range is
dropped when it is low confidence *and* its text matches a phantom phrase.

A Video with no detected speech produces a warning and no Sidecar — never an empty file.

## Output format

UTF-8 without BOM, CRLF line endings, numbering from 1, `hh:mm:ss,mmm` timestamps, one
blank line after each cue, file ends with a single newline.