# One line per Cue, and Fragments that read as Fragments

A Cue is one line of up to 90 characters. The two-line wrap at 42 characters is gone: it
broke single thoughts in half for no reason a viewer could see, and the break landed wherever
a broadcast number put it rather than where the thought ended. A Sentence too long for one
Cue is cut into **Fragments**, and a Fragment looks unfinished exactly where it is
unfinished.

This decision supersedes the layout and text rules of
`0006-one-sentence-per-cue.md` while keeping its central decision: the Sentence is still the
unit a Cue is built from, with a rescue for one too slight to stand alone and recursive
halving for one too long.

## Considered Options

- **One line of up to 90 characters (chosen).** An ordinary thought arrives whole: the
  reported 61-character sentence sits on one line, and the median Cue in the sample video
  (52 characters) never comes close to the limit. Only a rambling Sentence is cut, and the
  cut now looks like one.
- **Keep two lines of 42 characters.** Broadcast-safe and legible, but it is the thing being
  removed: it splits thoughts mid-phrase and makes a 42-character number the shape of every
  Cue.
- **One line capped near 60 characters.** Close to broadcast's total two-line budget and
  still wide, but it would cut the 61-character sentence that prompted this feature — the
  exact thought the feature exists to keep whole.
- **No character cap at all.** Every Sentence would be one line however long, which lets a
  fast unpunctuated run-on become an unreadable stripe across the frame. The 90-character
  cap keeps a Cue from growing without bound while rarely binding.

## Consequences

- A 90-character line is roughly twice broadcast's 42-character safe width. On a full-screen
  player the text is wider than the frame's safe area, and some players will shrink it or
  hard-wrap it themselves. That is the cost being paid, deliberately, in exchange for never
  breaking a thought across lines. It is the number most likely to need revisiting after
  watching a few videos; it is one row in `docs/subtitle-policy.md` and one constant
  (`MAX_LINE_CHARS`) in `src/subie/segment.py`.
- A Cue that holds part of a Sentence keeps no capital it did not earn and no terminal stop
  where the Sentence carries on. This deliberately reverses ADR 0006's promise that "the
  first letter of a Cue is capitalized and the Cue ends in terminal punctuation, so that each
  Cue reads as a sentence even when the split created it". A Fragment must not be dressed as
  a whole sentence: a future reader who treats the Fragment rules as a bug against 0006
  should read this record first.
- The rescue threshold rises from 15 to 40 characters, so a 40-character scrap such as
  `Told within tight narrative constraints.` joins its neighbour instead of standing alone.
  A joined pair is still two Sentences: its internal full stop stays. Removing it would mean
  deciding that a participle fragment is not a sentence while `Right. Begin.` is two real
  short sentences — a comprehension judgement this tool does not make.
- A small closed list of words that cannot end a Sentence repairs the engine's provably
  spurious stops before any grouping or cutting. It is a certainty test, not a model and not
  a threshold, and it lives beside the phantom-phrase blocklist in `src/subie/guard.py`.
- One line also removes the line-balance rule and `MIN_LINE_BALANCE`: a single line has
  nothing to balance. Balance survives only as a guard on cuts that are not at a Sentence
  end, which keeps badly lopsided Fragments out of the remaining cuts.
- Everything else ADR 0006 decided still holds: one Sentence per Cue, the rescue, the flash
  case, recursive halving, the 1 s minimum outranking the gap and the reading-speed trigger,
  and a pure deterministic segmenter whose output depends only on the Transcript.
- `docs/subtitle-policy.md` remains the only place the rules and numbers are explained. The
  independent limit checker in `tests/golden.py` judges a Sidecar against the policy, not
  against the segmenter: it now rejects any Cue with a line break, any Cue over 90
  characters, and any Cue that begins lowercase or ends without a stop where the Transcript
  does not show its Sentence continuing.