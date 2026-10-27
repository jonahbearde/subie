# 09: Install story and docs

**What to build:** The thing a person can actually follow, on both machines. A documented install that works on a Windows machine with no Python and no ffmpeg, a README that leads with the zero-argument case, and an honest list of what the tool will not do well. Someone who has never seen this conversation should be able to install it, subtitle a video, understand what the flags change, and know the limits they should expect.

**Blocked by:** 03, 05, 06, 07, 08.

Status: ready-for-agent

- [ ] The README's first example is the zero-argument case, and every subsequent example matches a behaviour that actually exists.
- [ ] Install instructions cover both machines: the GPU machine with no Python or ffmpeg, and a CPU-only machine.
- [ ] The GPU setup is documented as one command, with what to do when `doctor` reports the GPU path as unavailable.
- [ ] Known limitations are stated plainly: proper nouns and names can be misheard, music and heavy effects can confuse the engine, English only, and there is no translation.
- [ ] The subtitle policy document is linked from the README as the reference for cue limits, and its numbers match the implementation.
- [ ] `--keep-audio` is documented as the way to inspect what the engine actually heard.
- [ ] Exit codes and the skip/force behaviour are documented, with an example script that branches on the exit code.
- [ ] The four architecture decision records are consistent with the shipped behaviour, or amended where reality diverged.