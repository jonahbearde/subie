# 05: Clean text — normalization and hallucination guards

**What to build:** Subtitles that neither look machine-made nor invent dialogue. Music-note-only cues are dropped entirely; a bracketed non-speech marker survives only when it is the only thing in the Cue; whitespace and stray punctuation spacing are normalized; the first character of each Cue is capitalized and the Cue is terminated; the engine's remaining casing is left alone; fillers are preserved. On top of that, phantom phrases such as "Thanks for watching" are filtered only where the engine's own confidence is also low, so real speech containing those words survives. The phrase list and the confidence threshold are data and documented constants, not inline literals.

**Blocked by:** 04.

Status: done

- [x] A Cue consisting only of music notes does not appear in the Sidecar.
- [x] A Cue whose only content is a bracketed marker such as `[Music]` is kept.
- [x] A Cue containing both speech and a bracketed marker has the marker stripped and the speech kept.
- [x] Doubled spaces and space-before-punctuation are removed; each Cue starts with a capital and ends with terminal punctuation.
- [x] Fillers such as `um` and `uh` survive into the Sidecar.
- [x] A low-confidence Cue whose text matches a phantom phrase is dropped; a high-confidence Cue containing the same words is kept.
- [x] The phrase list is data in one place and documented, and the confidence threshold is a named constant.
- [x] Golden fixtures cover each rule above, plus a Cue that triggers more than one rule at once.
- [x] Cue readability limits still hold after normalization: a Cue that normalization lengthens is re-checked, not written oversized.

## Comments

Implemented as two new pure modules plus a change of measuring stick in the segmenter.

**`src/subie/text.py`** — `normalize(text) -> str | None`: collapse whitespace, pull
punctuation back onto the word before it, strip bracketed markers unless the Cue is nothing
else, capitalize the first letter, and ensure terminal punctuation (a missing stop is added;
a dangling `,` `;` `:` or dash becomes `.`; closing quotes stay outside). It returns `None`
for anything that says nothing: music notes, or markers left with nothing but notes. Marker
entries are exempt from capitalization and punctuation — a marker is not a sentence.
`is_music_only` and `is_bracketed` are the two predicates the segmenter shares.

**`src/subie/guard.py`** — the blocklist as data: `PHANTOM_PHRASES`, `LOW_AVG_LOGPROB`
(-1.0) and `HIGH_NO_SPEECH_PROB` (0.6), plus `is_low_confidence` / `is_phantom`. Matching is
case- and punctuation-insensitive on tokens, so `Thanks, for — watching!` matches.
`Confidence` (new, in `transcript.py`) gives the two numbers a name, and
`Segment.confidence` carries them.

**Segmenter.** Every limit is now measured against the cue's *cleaned* text (`_display`
feeds both the layout check and the reading-speed check), so cleaning that lengthens a Cue
forces a split instead of an oversized Cue; there is no second pass, because the fit check
already sees what will be written. Music-only words are dropped from the word stream, so a
music Cue never forms. Marker-only Segments are flagged `standalone` and are their own Cue:
without that, a `[Music]` next to short speech would be merged and stripped instead of kept
(the ticket's two marker rules otherwise contradict each other). Sentence-ends, clause ends
and `_CLOSERS` moved to `text.py`, which already owned the character sets.

**Guard placement.** The blocklist runs per sentence-sized range *before* sentences merge,
and a range is doubtful only when every Segment it came from was. Both choices are
defensive: a doubtful invention next to confident speech is dropped on its own instead of
taking the speech with it, and a Cue is never deleted on one doubtful word.

**Harness.** `tests/golden.py` grew what the fixtures now need: `S … logprob=… no-speech=…`
and a `T` line for a Segment whose source reported no word timings. Cue-to-word matching is
token-based, so it survives capitalization and punctuation, and it may skip a word only
when that word's Segment was doubtful or the word is a bracketed marker. It also checks that
a doubtful word never silently disappears: the same thresholds are repeated in the harness
(`_CONFIDENCE`) so production is judged against the policy, not against itself.

**Six existing fixtures changed**, each explained only by the two new casing rules — a Cue
ending in `,` now ends in `.`, and a Cue opening mid-sentence now opens capitalized:
`clause-boundary-splits`, `contiguous-clips-to-next-start`, `line-length-and-balance`,
`maximum-duration-splits`, `reading-speed-splits`, `tight-pause-clips-padding`. No timestamp
moved.

Fixtures (`tests/fixtures/text/`): `music-notes-dropped`, `bracketed-marker-kept`,
`marker-stripped-from-speech`, `whitespace-and-punctuation`, `fillers-preserved`,
`phantom-phrase-dropped-unless-confident` (doubtful phrase dropped, confident speech beside
it kept, confident same phrase kept), `mixed-rules-one-cue`, `numeral-start-left-alone`,
`normalization-splits-oversized-cue` (raw text lays out 40/42; the appended stop overflows,
so the Cue splits).

### Evidence

Default suite: 87 passed, 1 deselected. Slow end-to-end test: 1 passed (cached model and the
Windows speech synthesiser). `ruff check`, `ruff format --check` and `mypy` are clean
(32 files). A manual run over synthesized speech gave
`Um, so the quick brown fox jumps over / the lazy dog, and then it runs away.` — filler kept,
lowercase start capitalised, missing stop added, two balanced lines.

Both new behaviour fixtures were mutation-tested: measuring the raw text instead of the
cleaned text makes `normalization-splits-oversized-cue` produce one oversized Cue, and
moving the guard back to after merging makes `phantom-phrase-dropped-unless-confident` keep
the invented phrase. Each fails the fixture it exists for, so neither fixture passes by
construction.

### Review

Ran the two-axis code review. Standards returned a P1 and three P2s; Spec returned two P2s
and four P3s. All addressed:

- P1: this file was stale; status, boxes, evidence and this section are now filled in.
- P2 (both axes): the oversize fixture did not discriminate — the raw text already exceeded
two 42-character lines, so it passed with the re-check removed. One character shorter
(`numbers` → `number`) puts the raw layout at 40/42 so only the appended stop overflows, and
the mutation above confirms it now fails without the re-check.
- P2 (both axes): the guard ran after merging and doubted a Cue on any doubtful word, so a
  doubtful phrase could delete confident speech. It now runs per sentence range, and a range
  is doubtful only when every Segment it came from was; policy and fixture updated.
- P2: the policy said "the Segment it came from" (singular); the cross-Segment rule is now
  stated.
- P2: `_CLOSERS` was duplicated in `segment.py`; the sentence/clause predicates moved to
  `text.py` and are imported.
- P2: the harness re-implemented the text predicates with no stated reason. It now imports
  them, and the comment says why the *thresholds* stay repeated (they are what the harness
  asserts against).
- P3: policy now lists `…` and `%` in the strip-before-punctuation rule, mentions leading
  quotes, and both missing rules (standalone markers, digit starts) are documented.
- P3: `standalone` was computed over unfiltered words, so a `♪ [Music]` Segment lost its
  marker-kept status; it is now computed over the words that survive.

Left as judgement calls: `_display` names the word-range-to-text conversion and costs one
`normalize` per fit check (clarity over a memo); `_Spoken` and the harness's `SpokenWord`
are deliberately separate (production type vs. test model); the spec's pipeline step 7
("Normalize cue text") now happens inside segmentation, because the limits have to be
measured on the cleaned text — recorded here rather than editing the spec.

One deliberate trade-off: the phantom match is a token subsequence *anywhere* in the range,
so a doubtful Cue that says `Thanks for watching the kids tonight.` is dropped too. It only
ever applies where the engine's own confidence is low, and the exact-match alternative
misses `Thanks for watching, everyone.`