# English-only: no translation, no language detection

Inputs are assumed to be English. The recognition task is always `transcribe`; the
`translate` task and language detection are absent from the pipeline entirely.

This is surprising to anyone who knows Whisper can translate any language into English,
and it was raised in design: the requirement was originally "foreign videos should be
translated to English". It was dropped by the author's decision — the video library is
English, so translation is a feature that would be written, untested against real
material, and never exercised.

The consequences are all favourable, which is why this is worth recording rather than
looking like an oversight:

- Whisper's `translate` is its weakest mode: one decoder pass listening and writing
  English simultaneously, prone to dropping content and to fluent invented text over
  music. It also has no identity path, so an English video sent through `translate` gets
  paraphrased for nothing.
- Word-level timestamps, which cue segmentation wants and which are documented as
  unreliable under `translate`, are always available.
- The English-only `.en` models and `distil-large-v3` become usable; the former are
  strictly better per unit of compute and cannot translate, so the two decisions are
  linked.

A Video in another language is unsupported misuse, not a degraded case. Adding translation
later means re-introducing language detection and a second code path in segmentation.