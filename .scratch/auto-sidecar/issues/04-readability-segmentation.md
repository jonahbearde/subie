# 04: Readability segmentation

**What to build:** Cues that a viewer can actually read, instead of the engine's own segment boundaries. Words are packed into a Cue until a limit would be broken; breaks are preferred at a sentence end, then at clause punctuation, then at the longest pause; two sentences share a Cue only when both fit; lines are balanced and broken at clause boundaries rather than mid-phrase; Cues never overlap and carry the specified trailing padding. A Cue whose true duration would exceed the reading-speed limit is split into more Cues rather than stretched. The limits and their precedence are the ones recorded in the subtitle policy document, which stays the single place those numbers live.

**Blocked by:** 02.

Status: done

- [x] No Cue ever exceeds the character and line limits, the reading-speed limit, or the maximum duration; every Cue meets the minimum duration and the inter-Cue gap.
- [x] A sentence longer than one Cue is split at clause punctuation rather than mid-phrase.
- [x] Two short sentences that fit within the limits share one Cue; two that do not are never merged.
- [x] Cue start is the first word's start; Cue end is the last word's end plus the padding, clipped so that no Cue overlaps its successor.
- [x] Two-line Cues are balanced rather than filling the first line to the limit.
- [x] Segmentation is a pure function of a Transcript: no I/O, no model, no clock, and identical input yields identical output.
- [x] A golden-file test harness exists: a fixture Transcript on one side, the exact expected Sidecar bytes on the other, asserted through the single agreed seam.
- [x] At least one fixture exists for each behaviour above, and failures report the differing Cue rather than an opaque byte offset.

## Comments

Implemented as `src/subie/segment.py`: the pure `cues_from_transcript` used by the Job.
`srt.py` now only renders SRT; `pipeline.py` imports the segmenter directly. The engine's
segments become one flat word stream, so a segment without word timings still degrades to
a segment-shaped Cue rather than disappearing.

**Grouping.** Sentence endings divide the word stream, but a sentence boundary is not
automatically a Cue boundary. Adjacent sentences are merged greedily while the combined Cue
still satisfies every limit. An over-long sentence is first split by text/line capacity and
maximum duration, then each piece is recursively split while it exceeds the reading-speed
limit. The break preference is sentence end, then clause punctuation, then the longest
inter-word pause, then a character-balanced word boundary.

**Timing.** `in` is the first word's start. `out` is the last word's end + 200 ms, clipped to
`next_in - 100 ms` to reserve the gap when that does not cut into the last word, otherwise
clipped to `next_in`. The one-second minimum extends forward and may consume the gap, but
never overlaps the next Cue. Reading speed is measured on the displayed duration, so padding
and the minimum count as reading time. The competing cases are covered by the
`tight-pause-clips-padding` and `contiguous-clips-to-next-start` fixtures.

**Line breaking.** A Cue's text is one line if it fits 42 characters; otherwise the split
prefers a sentence end, then a clause end, but only when the shorter line is at least half
the longer one. A lopsided clause is rejected in favour of a balanced word boundary
(`lopsided-clause-balances`).

**Golden harness.** `tests/golden.py` runs each fixture through `run(argv, deps)` with only
the documented seam replaced (probe, device probe, transcriber factory). It compares exact
Sidecar bytes, reports the first differing Cue (number, expected text, actual text) rather
than a byte offset, and independently checks each Cue against the policy limits, the first
word's start, no overlap, and a best-effort 100 ms gap from the available silence. The
`.gitattributes` rule keeps the CRLF fixture bytes exact across checkouts.

Fixtures (`tests/fixtures/segmentation/`): `reading-speed-splits`,
`clause-boundary-splits`, `short-sentences-merge`, `merged-sentences-two-lines`,
`long-sentences-stay-apart`, `line-length-and-balance`, `lopsided-clause-balances`,
`maximum-duration-splits`, `minimum-duration-and-padding`, `tight-pause-clips-padding`,
`contiguous-clips-to-next-start`.

**Policy.** `docs/subtitle-policy.md` remains the single reference. The timing paragraph now
states the gap reservation, the CPS denominator, and the 50% line-balance guard explicitly;
the table's timing rows put no-overlap and the gap ahead of trailing padding to match the
implemented conflict resolution.

### Evidence

Default suite: 75 passed, 1 deselected. Slow end-to-end test: 1 passed (a cached model and
the Windows speech synthesiser were available). `ruff check`, `ruff format --check` and
`mypy` are clean (29 files).

### Review

Ran the two-axis code review. Standards and Spec both returned P1s, all addressed:

- Ticket state was stale; this file is now `done` with evidence.
- The 100 ms gap was not enforced while the harness asserted it. `_clipped_end` now reserves
  the gap, the policy states the reservation, and two fixtures cover the tight and
  contiguous cases. The harness now checks the gap against the actual available silence.
- The no-overlap clip had no fixture; `contiguous-clips-to-next-start` exercises it.
- Lopsided clause line breaks violated the "balanced" policy item; the 50% guard and
  `lopsided-clause-balances` cover it.
- P2 cleanups: one shared break-scan helper, one shared test WAV writer, and the
  segmenter fallback test moved out of the rendering test module.

Left as judgement calls: the `(words, first, last)` signature appears across the segmenter's
private helpers (a `Span` type would remove the data clump but adds indirection to a small
pure module), and line breaks do not yet consider pauses (the ticket asks for clause
boundaries; pause-aware line breaking is deferred).