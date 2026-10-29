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

When a Sentence cannot fit within 2 × 42 characters, 7 s or 20 CPS, it is halved near its
middle — see *Cue construction* below. The split is never mid-word.

Reading speed is the Cue's characters divided by its on-screen duration (`out - in`), so the
trailing padding and the 1 s minimum count as reading time. It is the one limit that yields
to the 1 s minimum: halving cannot make fast speech slower, so a range is only split for
reading speed when the split leaves two Cues that are each readable *and* each on screen for
a second. Speech that is itself faster than 20 CPS stays whole, because a whole thought at
21 CPS is better than two word-flashes underneath it.

## Sentence thresholds

| Threshold | Value | Why |
|---|---|---|
| Sentence pause | 500 ms | Speech the engine left unpunctuated still breaks where the speaker paused |
| Rescue by text | 15 characters | A Sentence shorter than this cannot be read on its own before it goes |
| Rescue by speech | 1 s | A Sentence with less speech than this flashes past |

A silence ends a Sentence just as terminal punctuation does, but it is the weakest reason to
*split* one: a Sentence end from punctuation outranks clause punctuation, which outranks a
500 ms pause, which outranks any word boundary.

## Cue construction (one Sentence per Cue)

1. Start from word timings (`word_timestamps=True`). A Sentence is a run of words ending
   at `.` `?` `!` (closing quotes and brackets handled as the text rules say) or at an
   inter-word silence of at least 500 ms. A Segment never has any bearing on where a Cue
   starts or ends.
2. One Sentence, one Cue. Two Sentences never share a Cue however much room is left.
3. **Rescue.** A Sentence under 15 characters of text, or spanning under 1 s of speech, may
   absorb exactly one neighbour: the following Sentence when the pair still satisfies every
   limit above, otherwise the preceding Sentence, otherwise it stays alone. A Cue never
   holds three Sentences, and a standalone marker never joins anything.
4. **The flash case.** A Sentence with less than a second between its first word and the
   next word cannot reach the minimum on screen. It absorbs a neighbour even when the pair
   breaks the character and duration limits, and the split in the next step re-cuts the
   combination. A Cue under 1 s survives only when there is nothing to join: a clip whose
   only speech is one short phrase, or a neighbour that cannot be joined.
5. **Split by halving.** A range that breaks the character, duration or reading-speed limit
   is cut at the boundary nearest its character midpoint; any part still over a limit is cut
   again the same way. Candidate boundaries, strongest class first: a Sentence end, clause
   punctuation (`,` `;` `:`), a pause of at least 500 ms, then any word boundary. A weaker
   class is used only when no stronger boundary leaves two halves — the shorter at least
   half the longer. The splitter also cuts a pair a rescue produced, so a rescued Cue may
   legitimately span a Sentence end. Reading speed yields to the 1 s minimum as described
   above: a range is only split for reading speed when both halves would read well, so a
   Cue faster than 20 CPS is always one that could not be improved by splitting.
6. `in` = first word's start; `out` = last word's end + 200 ms. It is clipped to
   `next_in - 100 ms` to reserve the gap. Where that would fall before the last word's end
   (overlapping word timings), `out` is clipped to `next_in` instead, because "out never
   overlaps next cue's in" outranks the padding. The 1 s minimum outranks the gap: when a
   Cue's padding cannot fill a second, `out` advances toward `next_in`, shrinking the gap
   to nothing if it has to, and stops at `next_in`. No speech is ever cut off, so a Cue
   ends up under 1 s only when `next_in` is itself less than a second after its first word.
7. Balance the two lines rather than filling line 1 to 42 characters and leaving line 2
   with one word. A sentence or clause boundary is used for the line break only when the
   shorter line is at least half the longer line; otherwise balance at a word boundary.

There is no packing strategy. A Sentence that is comfortably readable on its own is never
merged, and the reading pace goes up because there are roughly twice as many Cues.

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

A Cue-sized range is low confidence only when even its most generous reading trips a
threshold: the range's highest average log-probability is at or below `LOW_AVG_LOGPROB`, or
its lowest no-speech probability is at or above `HIGH_NO_SPEECH_PROB`. A range the engine
reported no confidence for at all counts as trusted, because deleting real speech is the
worse failure. The guard runs on each sentence-sized range *before* neighbouring sentences
are merged into one Cue, so a doubtful invention is dropped on its own and never takes the
confident speech next to it down with it. A range is dropped when it is low confidence
*and* its text matches a phantom phrase.

A Video with no detected speech produces a warning and no Sidecar — never an empty file.

## Output format

UTF-8 without BOM, CRLF line endings, numbering from 1, `hh:mm:ss,mmm` timestamps, one
blank line after each cue, file ends with a single newline.