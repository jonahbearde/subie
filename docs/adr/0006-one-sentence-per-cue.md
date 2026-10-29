# One Sentence per Cue, not greedy packing

A Cue holds one Sentence. The engine's segments are not the output and neither is a packed
run of sentences: a viewer reading a two-sentence Cue has to find their place inside a
paragraph, and the subtitle sits on screen long after the thought it belongs to has been
spoken.

## Considered Options

- **One Sentence per Cue with a rescue and midpoint halving (chosen).** The Sentence — a run
  of words ending at terminal punctuation or at a 500 ms silence — is the unit. A Sentence
  too slight to stand on screen alone absorbs one neighbour; a Sentence too long for one Cue
  is halved at the boundary nearest its middle, recursively. This is what a subtitler does,
  and it keeps every existing limit meaning what it meant. The cost is roughly twice as many
  Cues and a faster reading pace.
- **Strict one Sentence per Cue, no rescue.** Purer, but it flashes `Right.` and `Begin.` for
  a few tenths of a second. A subtitle the eye cannot land on is worse than a Cue holding two
  short thoughts, so a rescue is part of the decision rather than an exception bolted on.
- **Keep greedy packing, raise the reading speed.** The old behaviour filled each Cue to its
  capacity and only split when a limit was hit. It produces fewer Cues and a calmer pace, but
  it is the thing being removed: a Cue is then a container for as much text as fits, not a
  thought. Raising the reading-speed number would make the paragraphs denser, not shorter.
- **Merge-as-rescue with no halving change.** Keeping the old capacity-driven splitter would
  cut a long Sentence at whatever boundary filled the first Cue, leaving a scrap for the
  second. Halving near the midpoint is what makes a long Sentence read as two halves.

## Consequences

- About twice as many Cues on ordinary speech. Each is on screen for a shorter time and is
  easier to read, but the picture changes more often; if that turns out tiring in practice
  the lever is the reading-speed number, which is one line in `docs/subtitle-policy.md`.
- The 1 s minimum now outranks both the 100 ms gap and the reading-speed trigger. A Cue
  that cannot reach a second from its padding takes the gap instead, and only a Cue with
  nowhere to extend (the next word starts within a second of its first) may be shorter.
- A stretch of speech faster than 20 CPS stays one Cue instead of being halved into
  single-word flashes. Halving cannot slow speech down, so the reading-speed limit is only a
  split trigger when splitting actually leaves two readable Cues; a whole thought at 21 CPS
  beats four words at 0.3 s each underneath it. This is the one place where the spec's
  "20 CPS as a hard split trigger" gives way, because the spec's stronger promise — no Cue
  under a second unless there is nothing to join — cannot hold otherwise. Measured on the
  sample video, this is the difference between 203 sub-second word Cues and none.
- A Sentence the engine left unpunctuated still becomes sentence-sized Cues: a 500 ms pause
  ends a Sentence, so a run-on breaks at the pauses the speaker actually made.
- A Segment never influences Cue boundaries, so the same words always produce the same Cues
  and a re-run is a re-run.
- `docs/subtitle-policy.md` is still the only place the rules and numbers are explained;
  `src/subie/segment.py` carries the values. A regression to packing or to capacity filling
  is checked against the Transcript's words, not against the segmenter's own decisions.