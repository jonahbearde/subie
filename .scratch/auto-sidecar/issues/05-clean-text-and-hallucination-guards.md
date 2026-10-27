# 05: Clean text — normalization and hallucination guards

**What to build:** Subtitles that neither look machine-made nor invent dialogue. Music-note-only cues are dropped entirely; a bracketed non-speech marker survives only when it is the only thing in the Cue; whitespace and stray punctuation spacing are normalized; the first character of each Cue is capitalized and the Cue is terminated; the engine's remaining casing is left alone; fillers are preserved. On top of that, phantom phrases such as "Thanks for watching" are filtered only where the engine's own confidence is also low, so real speech containing those words survives. The phrase list and the confidence threshold are data and documented constants, not inline literals.

**Blocked by:** 04.

Status: ready-for-agent

- [ ] A Cue consisting only of music notes does not appear in the Sidecar.
- [ ] A Cue whose only content is a bracketed marker such as `[Music]` is kept.
- [ ] A Cue containing both speech and a bracketed marker has the marker stripped and the speech kept.
- [ ] Doubled spaces and space-before-punctuation are removed; each Cue starts with a capital and ends with terminal punctuation.
- [ ] Fillers such as `um` and `uh` survive into the Sidecar.
- [ ] A low-confidence Cue whose text matches a phantom phrase is dropped; a high-confidence Cue containing the same words is kept.
- [ ] The phrase list is data in one place and documented, and the confidence threshold is a named constant.
- [ ] Golden fixtures cover each rule above, plus a Cue that triggers more than one rule at once.
- [ ] Cue readability limits still hold after normalization: a Cue that normalization lengthens is re-checked, not written oversized.