# Spec: one Sentence per Cue

Status: ready-for-agent
Feature: one-sentence-per-cue

## Problem Statement

I read the Sidecar this tool wrote for a video, and I am not keeping the result. The
transcription is fine — the words are right. The segmentation is what's wrong: my Sidecar
is a set of half-minute slabs of text where each Cue holds several sentences at once, so
subtitles sit on screen for thirty seconds, covering half the picture, and my eye has to
hunt for where it currently is inside a paragraph.

I want subtitles shaped the way subtitlers shape them: **one sentence on screen at a
time**. "What does it look like for a story to be stripped right back?" is a Cue. When a
sentence is too long to read in one go, I want it cut roughly in half at a place that makes
sense — "What if there are no sprawling landscapes" / "no long adventures, no big set pieces
or huge battles" — not filled greedily to the character limit and not cut mid-phrase.

I also don't want the opposite failure. Subtitles that flash a single word for a tenth of a
second are worse than a slab, and a Cue that sits on screen for a moment less than it should
because the next one is crowding it reads as a glitch. Whatever replaces the slabs has to be
comfortable to watch, not just short.

## Solution

The segmenter stops packing sentences together and starts treating the sentence as the unit
of a Cue.

What I see, watching the Sidecar:

- One sentence, one Cue. Two sentences never share a Cue unless one of them is too slight to
  stand on screen alone ("Right.", "Begin.") — then it joins a neighbour instead of
  flashing past by itself.
- A sentence too long for one Cue is halved near its character midpoint, at the nearest
  sentence end, clause punctuation, or long silence — recursively, if a half is still too
  long. Halves read as halves, not as a full Cue and a scrap.
- Speech the engine couldn't punctuate at all ("what do you think you're going to accomplish
  you're not going to change anybody's mind") still breaks into sentence-sized Cues, because
  a long enough silence counts as the end of a sentence when no punctuation does.
- A Cue is on screen for at least one second. If the only way to give it that second is a
  shorter gap to the next Cue, the gap gives way — never the other way around, and never an
  overlap.
- Everything else about the Sidecar is unchanged: two lines of 42 characters, at most seven
  seconds, 20 CPS, 100 ms gaps, trailing padding, capitalization, terminal punctuation,
  music and non-speech markers, and the SRT bytes themselves.

## User Stories

### What I watch

1. As a viewer, I want one sentence on screen at a time, so that I never have to find my
   place inside a paragraph of subtitle text.
2. As a viewer, I want a Cue to hold a single complete thought, so that what disappears from
   the screen matches what I just finished reading.
3. As a viewer, I want a long sentence presented as two readable halves, so that I can
   follow it without the second half arriving before I have read the first.
4. As a viewer, I want the halves of a long sentence to be roughly equal, so that the second
   half isn't one trailing word.
5. As a viewer, I want a long sentence to be cut at a clause boundary where one exists, so
   that each half reads as a phrase rather than a fragment.
6. As a viewer, I want a sentence that arrives without any punctuation to still be cut into
   sentence-sized Cues at the pauses the speaker actually made, so that the run-on doesn't
   become a wall of text.
7. As a viewer, I want no Cue to sit on screen long enough to feel stuck, so that subtitles
   keep pace with the video.
8. As a viewer, I want no Cue to be too dense to read at the speed it is shown, so that I am
   never still reading when the text changes.
9. As a viewer, I want a Cue to appear the moment its first word is spoken, so that the
   subtitle and the audio stay together.

### What I don't want to see

10. As a viewer, I want a one-word Cue never to flash past in a tenth of a second, so that my
    eye can land on it at all.
11. As a viewer, I want a trivially short utterance ("Right.", "Yes.", "Begin.") joined to a
    neighbouring sentence when that can be done within the limits, so that the video isn't
    punctuated by single words blinking.
12. As a viewer, I want a rescued short utterance to never turn into a paragraph, so that the
    rescue is an exception rather than a return to slabs.
13. As a viewer, I want adjacent Cues never to overlap in time, so that the picture isn't
    disturbed by two subtitles fighting for the same frame.
14. As a viewer, I want a Cue that gains its one-second minimum to take it from the gap before
    the next Cue rather than from the next Cue's words, so that no speech is ever cut off.
15. As a viewer, I want the gap between Cues preserved whenever there is room for it, so that
    adjacent Cues read as two events rather than one flickering block.
16. As a viewer, I want a Cue to linger a moment past its last word, so that the end of a
    sentence doesn't vanish on the same frame as the syllable.

### Layout and text

17. As a viewer, I want a Cue to use at most two lines of 42 characters, so that it never
    covers half the screen.
18. As a viewer, I want a two-line Cue to wrap at a clause boundary when it can and to be
    balanced when it can't, so that a line never ends with a lone word.
19. As a viewer, I want the first letter of a Cue capitalized and the Cue to end in terminal
    punctuation, so that each Cue reads as a sentence even when the split created it.
20. As a viewer, I want music symbols and non-speech markers handled exactly as they are
    today, so that this change doesn't resurrect `♪♪♪` as a subtitle.

### When the input is awkward

21. As a viewer, I want a video whose speech the engine left unpunctuated to still get
    sentence-sized Cues, so that a quiet or mumbly recording doesn't produce slabs.
22. As a viewer, I want a Cue made of nothing but a non-speech marker to stay a Cue of its
    own, so that `[Music]` doesn't get glued to the first line of dialogue.
23. As a viewer, I want a single-sentence video — or a video whose only speech is one short
    phrase — to still produce a Sidecar, even if that Cue cannot be shown for a full second,
    so that a short clip isn't dropped for being short.
24. As a person whose transcript omitted word timings, I want the tool to keep degrading to
    segment-shaped text rather than producing an empty or crashed Sidecar, so that an
    unusual Transcript never loses a file.

### Trust and repeatability

25. As the person running the tool twice, I want the same Transcript to produce the same
    Cue list, so that a re-run is a re-run and not a new result to evaluate.
26. As the person running the tool on a folder, I want the change to affect only Cue
    construction, so that Jobs, Skips, Runs, counts and exit codes behave exactly as they do
    today.
27. As the person running the tool, I want the summary line's Cue count to reflect the new
    segmentation honestly, so that I can see the density change in the number.

### As the maintainer and as an agent

28. As a maintainer, I want every number this feature introduces to live in the subtitle
    policy document beside the existing limits, so that there is one place to change them.
29. As a maintainer, I want the policy document's cue-construction section to describe one
    Sentence per Cue with an explicit rescue and an explicit halving rule, so that the
    document and the code cannot drift apart silently.
30. As a maintainer, I want the reason for abandoning greedy merging recorded in a decision
    record, so that a future reader doesn't "fix" it back to packing.
31. As a maintainer, I want the glossary to define Sentence and Segment, so that "segment"
    stops being used for both the engine's chunk and the thing on screen.
32. As an agent working in this repo, I want a fixture per behaviour, with exact expected
    Sidecar bytes, so that a regression shows up as a named failing Cue rather than a diff I
    have to interpret.
33. As an agent working in this repo, I want the test harness to check the policy's limits
    independently of the segmenter, so that a limit regression is caught even if the
    expectations were regenerated from the same mistake.

## Implementation Decisions

**The unit.** A **Sentence** is the unit a Cue is built from: a run of words ending at `.`,
`?` or `!` (existing handling of closing quotes and brackets applies), **or** at an
inter-word silence of at least `SENTENCE_PAUSE_S` = 500 ms. Pause-derived boundaries are
equal in strength to punctuation-derived ones for the purpose of ending a Sentence, but
weaker as a *split* boundary (see precedence below). A **Segment** is the engine's own chunk
of Transcript and never has any bearing on Cue boundaries; the word stream is still flattened
across Segments exactly as today, including the "Segment without word timings becomes one
word-shaped piece" degradation.

**Grouping.** One Sentence per Cue. Merging survives only as a **rescue**: a Sentence whose
text is under `RESCUE_MIN_CHARS` = 15 characters, or whose words span less than
`RESCUE_MIN_SPEECH_S` = 1 s of speech, may absorb exactly one adjacent Sentence — forward
neighbour first when the pair still satisfies every limit, otherwise the preceding
neighbour, otherwise it stays alone. Never three Sentences in one Cue. There is no
packing strategy: a Sentence that is comfortably readable on its own is never merged, however
much room is left in the Cue.

**Splitting.** A range that breaks the character, duration or reading-speed limit is split by
**recursive halving**: cut at the boundary nearest the character midpoint, then repeat on any
part still over a limit. Candidate boundaries, in precedence order: a Sentence end, clause
punctuation (`,` `;` `:`), a pause of at least `SENTENCE_PAUSE_S`, then a balanced word
boundary. Never mid-word. Greedy capacity filling is removed; the halving splitter is the
only splitter, and it also cuts a Sentence that a rescue merge produced, which means a
rescued Cue may legitimately span a Sentence end.

**The flash case.** A Sentence may have too little on-screen room to reach 1 s — the next
Sentence starts almost immediately after it. That Sentence is merged into its neighbour
*even when the pair breaks the character and duration limits*, because the halving splitter
will re-cut the combination with the fragment absorbed into a large enough half. A sub-1 s
Cue survives only when there is nothing to merge with (a video whose only speech is one short
phrase, or a Sentence whose neighbour also cannot be joined).

**Timing precedence.** `out` = last word's end + trailing padding, clipped to
`next_in − gap`. If the result is less than the 1 s minimum, `out` advances toward `next_in`
— the gap shrinks, possibly to zero — and only stops there. The 1 s minimum now outranks the
gap rule instead of losing to it, and `out` still never passes `next_in`. This is a
behaviour change to the existing timing rule and is implemented as its own commit, ahead of
the grouping change, with its own fixtures.

**What does not change.** The 42-character line limit, the two-line ceiling, line balancing,
20 CPS as a hard split trigger measured over displayed duration, the trailing padding and gap
amounts, the 7 s maximum Cue duration, capitalization and terminal punctuation, music-note
removal, non-speech marker handling (standalone markers never merge), the phantom-phrase
guard and its thresholds, the SRT byte format, and every Job/Run/Skip behaviour.

**Interfaces.** The segmenter's public interface is unchanged in shape: one pure function
from a Transcript to an ordered Cue list, no I/O, no model, no clock, deterministic. New
constants for the three new numbers are module-level and exported the way the existing limits
are, so the documentation test can assert that the policy document states the same values.
The new numbers and the rewritten construction rules are documented in the subtitle policy
document, which remains the only place they are explained; the module carries the values, not
another explanation.

**Records.** A new decision record — decision records run to 0006; this is the next one —
records why packing was abandoned for one-Sentence-per-Cue, the alternatives considered
(strict with no rescue; keep packing; merge-as-rescue), and the trade-off accepted (more
Cues, more churn, faster reading pace, in exchange for far less text on screen and one
thought per Cue). The glossary gains **Sentence** and **Segment**, in the existing
single-context glossary, with no implementation detail.

## Testing Decisions

**The seam.** There is exactly one, and it already exists: the tool's CLI entry point, driven
with the project's existing fakes for the device probe, the media probe and the transcriber
factory. A fixture is a Transcript in a compact text format on one side and the exact expected
Sidecar bytes on the other; the test writes a dummy video, runs the real CLI, and compares
bytes. No new seam is introduced, and the segmenter's internals are never called directly.
This is also the seam the existing segmentation, Job and parallel-run tests already use.

**What makes a good test here.** Tests assert what a viewer sees: the bytes of the Sidecar and
the policy's external limits. They do not assert the shape of intermediate groupings, do not
import private functions, and do not restate the algorithm. A failure must name the offending
Cue — number, expected text, actual text — not a byte offset; the harness already does this and
keeps doing it.

**Harness extensions.** The independent limit checker gains two rules, because the new policy
has two edges the old one did not: a Cue's duration may fall below the 1 s minimum only when
it has nowhere to extend to (the next Cue starts within a second of this one's first word), and
a Cue may contain more than one Sentence only when the earlier Sentence is under the rescue
thresholds. Both are expressed against the Transcript's words, not against the segmenter's
decisions.

**Fixtures.** Each behaviour gets one, and the ones that assert the old behaviour are
rewritten rather than deleted: the merging fixtures become a rescue fixture (short utterance
joined forward) and a refusal fixture (a comfortably readable sentence left alone despite
room); a fixture for punctuation-free speech split at a 500 ms pause and one for a 300 ms
pause that does *not* split; a fixture for midpoint halving that would come out lopsided under
greedy filling; a fixture for a rescued Cue that spans a sentence end; a fixture for the
unavoidable sub-1 s Cue; and the existing duration, padding, gap, clipping, line-balance,
reading-speed and clause-split fixtures kept with their expectations updated where the new
grouping changes them.

**Docs tests.** The existing documentation test that pins the policy's numbers to the
segmenter's constants is extended to cover the new pause threshold, so the policy table and the
code cannot diverge. The decision record is linked from the README the way the other records
are, because the docs test checks every record is reachable.

**End to end.** The slow, model-backed end-to-end test is unchanged and stays out of the
default run; nothing about speech recognition, decoding or model choice is touched.

## Out of Scope

- Restoring punctuation the engine didn't produce, or any additional model for casing,
  punctuation or sentence splitting.
- Changing the line limit, line count, reading speed, maximum duration, padding or gap values.
- Anything upstream of the Cue list: the engine call, VAD, word timestamps, the model cache,
  `--keep-audio`, or any flag on the CLI.
- Job, Skip, Run, parallel execution, folder walking, summary output and exit codes.
- Re-running recognition to improve the transcript, and any change to what the words say.
- Investigating where the stale thirty-second Sidecar that prompted this came from; the tool as
  it stands cannot produce it, and this spec is about the Cues the tool should produce from now
  on.
- Re-encoding or otherwise modifying the Video.

## Further Notes

**The reported symptom and the real defect.** The Sidecar that provoked this was produced by a
build whose Cues were the engine's own Segments. The current segmenter cannot emit a 30 s Cue:
it caps at 7 s, and word timings survive even the GPU-only batched engine path (verified — 68
words for the first Segment of the offending video). Re-running the current build on that video
yields 385 Cues of a few seconds each. So this feature is not a bug fix for slabs; it is the
change that makes the output match what was expected — plus a fix for the two real defects
found while checking: sentences still being packed into one Cue, and sub-second Cues caused by
the gap rule beating the 1 s minimum.

**Expect roughly double the Cue count** on ordinary speech, and a noticeably faster reading
pace. That is the intended trade: less text on screen at any moment, more frequent changes.
If it turns out tiring in practice, the lever is the reading-speed number, which is one line in
the policy document.

**Manual check after implementation.** Regenerate the sample video's Sidecar and read it,
rather than only reading the diff of the fixtures: the point of this feature is how it feels to
watch, and no assertion covers that.
## Comments

### Implementation notes

- **Reading speed yields to the one-second minimum.** Taken literally, "20 CPS as a hard
  split trigger" halved dense speech all the way down to single-word Cues of 0.2–0.3 s — the
  exact flash failure this spec exists to prevent. Measured on the sample video, 203 of the
  previous build's 385 Cues were those sub-second shards. A range is now split for reading
  speed only when the split leaves two Cues that are each readable and each on screen for a
  second; otherwise it stays whole. Recorded in `docs/adr/0006-one-sentence-per-cue.md` and
  `docs/subtitle-policy.md`.
- **The slight Sentence in a rescued Cue may be the later one.** The harness rule is checked
  as "either Sentence is under the rescue thresholds", not "the earlier one is", because a
  backward rescue (a slight last Sentence absorbing the comfortable one before it) is what
  "otherwise the preceding neighbour" produces. See `rescue-short-utterance-joins-backward`.
- **Cue counts.** The sample video produces 199 Cues, not roughly double the old 385: the old
  count included the 203 sub-second shards above. Compare like with like — about 182 whole
  Cues before, 199 now — rather than against the shard-inflated number.
