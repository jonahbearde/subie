# Spec: one line per Cue

Status: ready-for-agent
Feature: one-line-cues

## Problem Statement

I read the Sidecar this tool wrote for a video and the words are right, but the shape is
not. Almost every Cue is broken across two lines at 42 characters, so a single short thought
arrives as a stack:

```
1
00:00:00,880 --> 00:00:04,640
What does it look like for a
story to be stripped right back?
```

"What does it look like for a story to be stripped right back?" is 61 characters. It is one
thought, spoken in one breath, and it should be one line. The break lands mid-phrase for no
reason the viewer can see — nothing about that sentence needed two lines except a number I
picked out of a broadcast standard.

Two other things bother me in the same file:

- The engine punctuates mid-thought, so one idea becomes two Cues: `A contained story is
  essentially any narrative.` / `Told within tight narrative constraints.` The second of
  those is 40 characters — it is a scrap, not a thought, and it should have joined the first.
  Under the current rescue threshold of 15 characters it does not.
- When a Cue really is cut (because the thought runs long), the pieces are dressed up as
  whole sentences: the first gets a full stop it did not earn, the second gets a capital it
  did not earn. `Most commonly, this involves the story taking place in one primary
  location.` / `Over a short span of time and with a limited cast of characters.` reads as
  two sentences, and it is one.

I want the two-Cue cut to stay — that thought is 9.4 seconds long and one Cue cannot hold it
— but I want the pieces to look like pieces: the first with no full stop, the second
starting lowercase.

## Solution

A Cue is one line, always. The two-line wrap is gone, and with it the 42-character line
limit; a Cue may run to 90 characters before it has to be cut.

What I see, watching the Sidecar:

- One sentence, one line, one Cue — however wide that line is. `What does it look like for a
  story to be stripped right back?` sits on a single line at 61 characters.
- A Sentence too slight to stand alone absorbs a neighbour at 40 characters instead of 15, so
  `A contained story is essentially any narrative. Told within tight narrative constraints.`
  becomes one 87-character Cue instead of two.
- A Sentence that genuinely cannot fit one Cue is cut into **Fragments**, and a Fragment reads
  as unfinished exactly where it is unfinished: no terminal stop where the Sentence carries
  on, no capital where it did not begin. `Most commonly, this involves the story taking place
  in one primary location` / `over a short span of time and with a limited cast of
  characters.`
- A comma or dash at a cut is dropped rather than kept or turned into a full stop.
- A Sentence the engine plainly mis-punctuated — one ending on `the`, `a`, `of`, `and` and the
  like, which no sentence can end with — is not trusted: the stop disappears, the word after
  it loses its capital, and the joined thought is laid out again from scratch. `…the story
  forces the. Audience into a sort of narrative claustrophobia.` becomes two readable Cues
  instead of a nonsense break.
- A proper noun keeps its capital after a cut, because the Transcript itself shows the engine
  capitalizing that word mid-sentence.
- Nothing else about the Sidecar changes: one second minimum, seven second maximum, 20 CPS,
  100 ms gaps, 200 ms trailing padding, music and non-speech markers, the SRT bytes, and how
  Jobs, Skips and Runs behave.

The trade is deliberate and it is the whole point: a 90-character line is roughly twice
broadcast's 42-character safe width, so on a full-screen player the text is wider than the
frame's safe area and some players will hard-wrap it themselves. I would rather read one line
in a player that shrinks or wraps it than read my own thoughts cut in half on every cue.

## User Stories

### One line, one Cue

1. As a viewer, I want a Cue to occupy a single line, so that I am never reading a stack of
   text when one line would do.
2. As a viewer, I want a one-sentence Cue of 61 characters to stay on one line, so that a
   short thought arrives whole.
3. As a viewer, I want the two-line wrap removed entirely, so that no Cue anywhere in the file
   has a line break I did not ask for.
4. As a viewer, I want a Cue to be allowed up to 90 characters on its one line, so that the
   width limit is generous enough that ordinary speech does not get cut.
5. As a viewer, I want a Cue over 90 characters to still be cut, so that a rambling Sentence
   does not become an unreadable stripe across the frame.
6. As a viewer, I want the cut to land near the middle rather than at the first opportunity, so
   that the two halves read as halves and not as a whole plus a scrap.
7. As a viewer, I want the cut to prefer a Sentence end, then clause punctuation, then a real
   pause, then a word boundary, so that the break lands where the speaker actually broke.

### Fragments read as fragments

8. As a viewer, I want the first Fragment of a cut Sentence to carry no terminal stop, so that
   I can see the thought is not finished.
9. As a viewer, I want the second Fragment to start lowercase, so that I can see it continues
   the sentence above rather than starting a new one.
10. As a viewer, I want a comma or dash at the cut point dropped, so that the line does not end
    in punctuation that reads as a mistake.
11. As a viewer, I want a Fragment that starts mid-Sentence to be lowercased rather than left
    capitalized, so that the engine's capitalization after its own full stop does not leak into
    the middle of my sentence.
12. As a viewer, I want a proper noun to keep its capital in a Fragment, so that names are not
    mangled by the lowercase rule.
13. As a viewer, I want the first-person pronoun to keep its capital, so that `…and then I
    left.` never becomes `…and then i left.`
14. As a viewer, I want a Cue that begins and ends whole Sentences to keep full capitalization
    and punctuation even when it was produced by cutting a rescued pair, so that a Cue that is
    not a Fragment is not dressed as one.
15. As a viewer, I want a Cue that ends a Sentence but does not begin one — the second half of
    a cut — to keep its terminal stop, so that the sentence still closes properly.
16. As a viewer, I want the missing-full-stop repair to keep working at real Sentence ends, so
    that a Cue that ends a thought always terminates.

### The rescue threshold

17. As a viewer, I want a 40-character scrap of a Sentence to join its neighbour instead of
    standing alone, so that `Told within tight narrative constraints.` is not a Cue.
18. As a viewer, I want a joined pair to still be one line and within every other limit, so
    that the rescue cannot grow into a paragraph.
19. As a viewer, I want a rescued pair to be joined forward when that fits and backward
    otherwise, so that the short thought attaches to whichever neighbour reads with it.
20. As a viewer, I want three Sentences never to share a Cue, so that a rescue stays an
    exception.
21. As a viewer, I want a Sentence that is comfortably readable on its own to never be merged,
    so that one thought on screen at a time remains the rule.

### Sentences the engine got wrong

22. As a viewer, I want a Sentence that ends on `the`, `a`, `of`, `to`, `and`, `by`, `with` and
    the like to be treated as not a Sentence end, so that a break the engine invented does not
    become a break I see.
23. As a viewer, I want the stop after such a word removed and the following word lowercased,
    so that the repaired Cue reads as the sentence that was spoken.
24. As a viewer, I want the list of words that cannot end a sentence to be data I can inspect,
    so that the repair is a documented rule rather than a hidden heuristic.
25. As a viewer, I want the repaired range to be re-split under the normal rules, so that
    repairing the punctuation cannot itself produce an oversized Cue.

### Comfort

26. As a viewer, I want a Cue to be on screen for at least one second, so that my eye can land
    on it.
27. As a viewer, I want a Cue never to sit for more than seven seconds, so that it does not feel
    stuck.
28. As a viewer, I want no Cue to read faster than 20 characters per second, so that I am never
    still reading when the text changes.
29. As a viewer, I want the one-second minimum to take the gap before the next Cue rather than
    the next Cue's words, so that no speech is ever cut off and no Cues overlap.
30. As a viewer, I want a Cue to linger 200 ms past its last word, so that the end of a thought
    does not vanish on the same frame as the syllable.
31. As a viewer, I want speech that is genuinely too fast to stay whole, so that a dense run-on
    is not chopped into single-word flashes.
32. As a viewer, I want the seven-second maximum to still put a 9.4-second thought on two Cues,
    so that the cuts that remain are the ones that had to happen.

### Nothing else moves

33. As a viewer, I want music notes removed and non-speech markers handled exactly as today, so
    that this change does not resurrect `♪♪♪` as a subtitle.
34. As a viewer, I want a marker the engine emitted on its own to stay a Cue of its own, so that
    `[Music]` is not glued to the first line of dialogue.
35. As a viewer, I want the words, the timings, the numbering and the file bytes unchanged in
    every other respect, so that this is a layout and punctuation change and nothing more.
36. As the person running the tool twice, I want the same Transcript to produce the same Cue
    list, so that a re-run is a re-run.
37. As the person running the tool on a folder, I want Jobs, Skips, Runs, counts and exit codes
    to behave exactly as they do today, so that only the Sidecar's shape changes.
38. As a person whose transcript omitted word timings, I want the tool to keep degrading to
    segment-shaped Cues rather than producing nothing, so that an unusual Transcript never
    loses a file.

### As the maintainer and as an agent

39. As a maintainer, I want every number this feature introduces or changes to live in the
    subtitle policy document beside the existing limits, so that there is one place to change
    them.
40. As a maintainer, I want the policy document's construction and text-normalization sections
    rewritten for one line and for Fragments, so that the document and the code cannot drift.
41. As a maintainer, I want the decision to accept a 90-character line, with its legibility
    cost, recorded in a decision record, so that a future reader does not "fix" it back to 42.
42. As a maintainer, I want the glossary to define **Fragment** and to stop describing a Cue as
    up to two lines, so that the vocabulary matches what the tool produces.
43. As an agent working in this repo, I want a fixture per behaviour with exact expected
    Sidecar bytes, so that a regression is a named failing Cue rather than a diff to interpret.
44. As an agent working in this repo, I want the harness to check the new rules independently
    of the segmenter, so that a regression is caught even if the expectations were regenerated
    from the same mistake.

## Implementation Decisions

**Layout.** A Cue is one line. The line limit becomes the Cue's text budget:
`MAX_LINE_CHARS` = 90, a hard split trigger measured against the Cue's cleaned text, and
`MAX_LINES_PER_CUE` = 1. The two-line wrapping pass and the line-balance rule it needed are
deleted, along with `MIN_LINE_BALANCE`; a single line has nothing to balance. The character
limit stays a hard trigger that does not yield — unlike reading speed, which continues to yield
to the one-second minimum exactly as documented today. Every other limit is unchanged: 20 CPS,
1 s minimum, 7 s maximum, 100 ms gap, 200 ms trailing padding, 500 ms sentence pause, rescue by
speech at 1 s.

**The unit stays a Sentence.** One Sentence per Cue, with the rescue and the recursive halving
recorded in ADR 0006 and the subtitle policy. What this feature changes is the layout, the
rescue threshold, and what a cut looks like — not the decision to make the Sentence the unit.

**Rescue threshold.** `RESCUE_MIN_CHARS` moves from 15 to 40. The rescue keeps its existing
shape: a Sentence under the character threshold or under the speech-duration threshold may
absorb exactly one neighbour — forward when the pair satisfies every limit, otherwise backward,
otherwise it stays alone; never three Sentences in one Cue; a standalone marker never joins
anything. A pair that a raise in the threshold now merges must still fit one line of 90
characters and every other limit, so the rescue cannot grow into a paragraph.

**Fragment.** A Fragment is a Cue holding part of a Sentence. Whether a Cue is a Fragment, and
at which end, is decided from the word ranges the segmenter chose — never guessed from the text
alone. Two text rules follow, and they are the only place a Cue's text depends on its position:

- A Cue that does not begin its Sentence gets no capital added, and its first letter is
  lowercased unless the token is one the Transcript itself capitalizes away from a Sentence
  start. That whitelist is derived per Transcript from the words the engine capitalized
  mid-sentence, which are its confident proper nouns and the pronoun `I`; `I` and its
  contractions are always members. Tokens that begin with a digit, or that are entirely
  uppercase, are left alone. Known limitation: a proper noun that appears in the Transcript
  only at Sentence starts is lowercased.
- A Cue that does not end its Sentence gets no terminal stop added, and a trailing `,` `;` `:`
  or dash is stripped rather than converted to `.`. A Cue that does end its Sentence keeps
  today's repair: a missing stop is added and a dangling `,` `;` `:` or dash becomes `.`.

**Sentences the engine mis-punctuated.** A new small documented list of words that cannot end a
sentence — articles, prepositions, coordinating and subordinating conjunctions — marks a
Sentence end as provably spurious when it falls on one of them. Such a range is repaired before
grouping: the stop is removed, the following word loses its capital under the same whitelist
rule as a Fragment, and the joined range is then laid out by the normal rules. This is data,
kept beside the phantom-phrase blocklist, not a model. It is a certainty test, not a threshold:
a sentence may end on a noun and look like `A contained story is essentially any narrative.`,
which is why the previous pair is fixed by the rescue threshold instead.

**Joining a pair keeps both Sentences' text.** A rescued pair is one Cue, but it is still two
Sentences: the internal full stop and the capital that follows it stay. The one-line layout is a
layout change, not a licence to rewrite what the engine punctuated where the punctuation is not
provably wrong. Consequence to be seen and judged: cue 6 of the sample becomes `A contained story
is essentially any narrative. Told within tight narrative constraints.` on one 87-character line.

**Splitting.** A range over the character, duration or reading-speed limit is cut at the boundary
nearest its character midpoint and re-cut recursively, as documented today. One change of
precedence: a Sentence end inside the range always wins as a cut point, even when the two halves
are badly unbalanced. The balance guard now applies only to word boundaries inside a single
Sentence, which keeps Fragments out of the cases where they would be most jarring. Boundary
classes otherwise stay: Sentence end, then clause punctuation, then a pause of at least 500 ms,
then a balanced word boundary; never mid-word. A provably spurious stop is not a cut candidate.

**Interfaces.** The segmenter's public shape does not change: one pure function from a Transcript
to an ordered Cue list, no I/O, no model, no clock, deterministic. Cue text is one line, so the
SRT renderer needs no change beyond never having a second line to emit. The text-rules module
gains the Fragment context — whether a Cue opens and closes its Sentence — and the whitelist it
needs; both are internal. The word list of sentence-final impossibilities lives as module data
beside the phantom-phrase blocklist, so the two honesty guards are discovered in the same place.
New and changed constants are exported the way the existing limits are, so the documentation test
can pin them.

**Documents.** The subtitle policy is the only place the rules are explained: the readability
table gains 90 characters and one line and loses the balancing row, the sentence-threshold table
gains the 40-character rescue, and the construction and text-normalization sections are rewritten
for Fragments, the comma strip, the whitelist and the provably-spurious stop. A new decision
record — 0007, superseding the layout and text rules of 0006 while keeping its sentence-unit
decision — records the trade accepted (a line twice broadcast's safe width in exchange for never
breaking a thought across lines), the alternatives (keep two lines of 42; one line capped near
60, which would cut the 61-character example; no character cap at all, which would let a fast
unpunctuated run-on reach the frame), and the consequence for players that hard-wrap wide lines.
The glossary gains **Fragment** and stops describing a Cue as at most two lines.

## Testing Decisions

**The seam.** There is exactly one, and it already exists: the tool's CLI entry point, driven
with the existing fakes for the device probe, the media probe and the transcriber factory. A
fixture is a Transcript in the compact text format on one side and the exact expected Sidecar
bytes on the other; the test writes a dummy video, runs the real CLI and compares bytes. No new
seam is introduced, the segmenter's internals are never called directly, and the existing
segmentation, Job and parallel-run tests keep using this same seam. The second, non-seam check is
the documentation test that pins the policy document's numbers to the segmenter's constants; it
gains the changed values and keeps the property that the policy table and the code cannot diverge
silently.

**What makes a good test here.** Tests assert what a viewer sees: the bytes of the Sidecar and the
policy's external limits. They do not assert intermediate groupings, do not import private
functions, and do not restate the algorithm. A failure must name the offending Cue — number,
expected text, actual text — not a byte offset. Expectations are regenerated only after reading
the new file, never to make a red test green.

**Harness extensions.** The independent limit checker judges production against the policy rather
than against the segmenter's own decisions, and gains three rules for this feature: a Cue's text
contains no line break; a Cue may run to at most 90 characters; and a Cue may begin lowercase or
end without a terminal stop only when the Transcript's words show its Sentence continuing on
either side — matched back to the Cue's words, with the whitelist applied to the lowercase case.
The two-line limit and the line-balance rule are removed from the checker with the code.

**Fixtures.** Each behaviour gets one, and the fixtures that assert the old layout are rewritten
rather than deleted:

- `one-line-cue-at-sixty-one-characters` — the reported sentence, one line.
- `one-line-cues-never-wrap` — a range of lengths, none containing a line break.
- `ninety-character-cue-fits-one-line` and `over-ninety-splits-into-two-cues` — the new cap from
  both sides.
- `seven-seconds-still-makes-two-cues` — the 9.4-second thought, two one-line Fragments.
- `fragment-drops-its-comma` and `fragment-keeps-no-stop` — the cut's text rules.
- `fragment-second-cue-starts-lowercase`, `proper-noun-keeps-its-capital`,
  `pronoun-keeps-its-capital` — the whitelist and its edges.
- `sentence-edge-of-a-fragment-keeps-its-stop` — the second half of a cut that ends a Sentence,
  and a rescued pair cut at a Sentence end.
- `article-final-stop-is-not-a-sentence-end` — the provably spurious stop, repaired and re-split.
- `forty-character-scrap-joins-forward` and `comfortable-sentence-stays-alone` — the new rescue
  threshold from both sides.
- `lopsided-pair-cuts-at-the-sentence-end` — the precedence change, replacing the fixture that
  asserted balance at a mid-sentence cut.
- The duration, padding, gap, clipping, reading-speed, dense-speech, recursive-halving,
  pause-derivation and marker fixtures are kept with expectations regenerated where the layout
  changes them.

**End to end.** The slow, model-backed end-to-end test is unchanged and stays out of the default
run; nothing about recognition, decoding or model choice is touched.

**Manual check after implementation.** Regenerate the sample video's Sidecar and read it, then
watch it in a player at full screen. The point of this feature is how the line feels and how wide
it gets, and no assertion covers either. Specifically confirm the four reported cues, and confirm
that a Fragment's lowercase start does not read as a typo.

## Out of Scope

- Any language model, POS tagger or punctuation-restoration model. The provably-spurious stop is a
  closed word list; everything else the engine punctuated wrongly stays as it is.
- Rewriting the internal punctuation of a rescued pair — the `…any narrative. Told within…` full
  stop stays (see Further Notes).
- Changing the reading speed, the one-second minimum, the seven-second maximum, the gap, the
  padding or the sentence pause.
- Anything upstream of the Cue list: the engine call, VAD, word timestamps, the model cache,
  `--keep-audio`, or any command-line flag.
- Job, Skip, Run, parallel execution, folder walking, summary output and exit codes.
- The SRT byte format, numbering and timestamp formatting.
- Player-side presentation: font size, safe-area compliance, and whether a given player hard-wraps
  an over-wide line.
- Re-encoding or otherwise modifying the Video.
- Choosing per-video or per-aspect-ratio widths; the 90-character line is one number for all
  Videos.

## Further Notes

**Measurements from the sample.** The Sidecar for the sample Video holds 199 Cues; 155 of them
(78%) currently contain a line break, so this is a whole-file change, not an edge case. Cue text
runs 42–85 characters, median 52, p90 73 — under a 90-character line the median Cue becomes a
single 52-character line. Cue duration runs 1.0–6.2 s, median 3.1 s. The four cues in the report
measure 61, 87, 75 and 64 characters. A rescue threshold of 40 merges 19 of the 198 adjacent pairs
in the sample (about 10%, so roughly 180 Cues afterwards); a threshold of 45 would merge 28 and
starts swallowing comfortable declaratives, which is why 40 was chosen rather than the smallest
number that fixes the reported Cue. Cue 8/9 in the report is 9.4 seconds end to end: it is the
seven-second maximum that puts it on two Cues, not the character limit, so that split survives
this change and each half simply becomes one line.

**The full stop that stays.** Joining a scrap to its neighbour makes one Cue but does not merge
two Sentences into one. Removing the internal stop would mean knowing that `Told within tight
narrative constraints.` is a participle fragment and `Right. Begin.` is two real short sentences —
a comprehension judgement this tool does not make, and one that a wrong guess would turn into
`Right begin.` The reported Cue therefore reads `A contained story is essentially any narrative.
Told within tight narrative constraints.` on one line. If that still reads wrong when watched, the
lever is a sentence-start word list in the same data module as the sentence-final one, and it
should be recorded as its own decision rather than folded in here.

**Reversal of an earlier promise.** The previous feature promised that "the first letter of a Cue
is capitalized and the Cue ends in terminal punctuation, so that each Cue reads as a sentence even
when the split created it". This feature reverses that for Fragments, deliberately: a Cue that
holds part of a thought now looks like part of a thought. ADR 0007 must say so plainly, or a future
reader will treat the Fragment rules as a bug against 0006.

**Legibility is the cost being paid.** 42 characters per line is not arbitrary — it is the width at
which subtitle text stays inside the safe area at a legible size. A 90-character line is
approximately twice that, so it will be shrunk or hard-wrapped by the player. That is accepted here
in exchange for never splitting a thought across lines, and it is the one number most likely to
need revisiting after watching a few videos; it is a single value in the policy table and a single
constant in the segmenter.
## Comments

### Implementation notes

- **A spurious end also covers a pause.** Story 22 says a Sentence ending on `the` is not a
  Sentence end; the engine can make that mistake with a pause as well as a stop, so the
  repair joins pause-derived endings too. `pause-on-an-impossible-word-is-not-a-sentence-end`
  covers it; the punctuation case is `article-final-stop-is-not-a-sentence-end`.
- **Balance still gates clause and pause cuts.** A Sentence end always wins a cut. Clause
  punctuation, pauses and word boundaries still require two halves of comparable size, or
  the 140-character `Most commonly, …` sentence would cut at its first comma and leave a
  13-character Fragment. The sample keeps its `location` / `over` cut, and
  `lopsided-pair-cuts-at-the-sentence-end` pins the sentence-end exception.
- **The sample after this change.** Regenerated: 183 Cues, none wrapped, longest exactly 90
  characters, median 57. The four reported Cues read as the Solution describes, including
  `the story forces the` / `audience into a sort of narrative claustrophobia.`
