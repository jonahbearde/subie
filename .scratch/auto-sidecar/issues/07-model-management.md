# 07: Model management

**What to build:** Control over the models the tool downloads and uses, so that a machine can be prepared before it goes offline and a stale cache can be reasoned about. `subie models list` shows what is present with sizes, `subie models pull <name>` downloads one ahead of time, and `subie models rm <name>` removes one. The cache lives in a predictable per-machine location that doctor already reports. Asking for a model that cannot be fetched produces a clear message naming the model and the cache path, never a download-library traceback, and `--model` rejects an unknown name before any work starts.

**Blocked by:** 02.

Status: ready-for-agent

- [ ] `subie models list` reports each model present in the cache with its size, and says so plainly when the cache is empty.
- [ ] `subie models pull <name>` downloads the model, reports progress, and the model then appears in `list` and is used by a Run without further network access.
- [ ] `subie models rm <name>` removes it, and a later Run reports the clear missing-model message.
- [ ] Pulling with no network fails with a message naming the model and the cache location, and no stack trace.
- [ ] `--model` with a name that is neither cached nor pullable fails before any decoding starts.
- [ ] The cache location reported by `subie doctor` and the location used by `models` and by a Run are the same one.
- [ ] Tests cover list, pull, remove, and the offline failure through the single agreed seam, with the download step faked so no test needs the network.