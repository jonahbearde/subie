# 04: Readability segmentation

**What to build:** Cues that a viewer can actually read, instead of the engine's own segment boundaries. Words are packed into a Cue until a limit would be broken; breaks are preferred at a sentence end, then at clause punctuation, then at the longest pause; two sentences share a Cue only when both fit; lines are balanced and broken at clause boundaries rather than mid-phrase; Cues never overlap and carry the specified trailing padding. A Cue whose true duration would exceed the reading-speed limit is split into more Cues rather than stretched. The limits and their precedence are the ones recorded in the subtitle policy document, which stays the single place those numbers live.

**Blocked by:** 02.

Status: ready-for-agent

- [ ] No Cue ever exceeds the character and line limits, the reading-speed limit, or the maximum duration; every Cue meets the minimum duration and the inter-Cue gap.
- [ ] A sentence longer than one Cue is split at clause punctuation rather than mid-phrase.
- [ ] Two short sentences that fit within the limits share one Cue; two that do not are never merged.
- [ ] Cue start is the first word's start; Cue end is the last word's end plus the padding, clipped so that no Cue overlaps its successor.
- [ ] Two-line Cues are balanced rather than filling the first line to the limit.
- [ ] Segmentation is a pure function of a Transcript: no I/O, no model, no clock, and identical input yields identical output.
- [ ] A golden-file test harness exists: a fixture Transcript on one side, the exact expected Sidecar bytes on the other, asserted through the single agreed seam.
- [ ] At least one fixture exists for each behaviour above, and failures report the differing Cue rather than an opaque byte offset.