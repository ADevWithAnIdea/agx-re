# EXP-0120: M4 tiler parameter-buffer (TVB) overflow mechanism

- **Date:** 2026-08-28
- **Clean-room category:** DATA-TRACE + HW-PROBE (+ bounded PUBLIC reference to `mesa/`,
  read-only, never treated as Apple9 hardware evidence)
- **Target:** local Apple M4 (G16G), this host only. A18 Pro not touched (hands-off per
  `CLAUDE.md`). M5 out of scope.
- **Phase / question:** when the tiler's parameter buffer / tile-vertex buffer (TVB)
  overflows mid-render on Apple9, what is the mechanism, and what does userspace supply
  versus what firmware/kernel owns? This is the P0.4/`DRV-UAPI-04`-relevant follow-up to
  EXP-0108 (which established *no* new userspace-visible record for load/store/format/MRT/
  depth/stencil, and a *bounded, inconclusive* partial-render probe up to ~600,000
  *distributed* triangles) and reuses EXP-0118's project-authored, already-validated
  partial-render trigger/oracle workload (tile-*concentrated* geometry, additive-blend
  accumulation into 8 R32F attachments) without modifying it.

## Hypotheses

See `PRE_REGISTRATION.md` for the full falsifiable statement of each. In short:

- **H1** — does a partial render actually engage, and at what triangle-count threshold
  (independent of the oracle's own correctness check)?
- **H2** — which mechanism: (a) TVB grows via a new/resized userspace BO, (b) a genuine
  multi-kick partial render with extra userspace-visible submission traffic, (c) a
  transparent segment-chain inside an already-reserved region, or (d) something else?
- **H3** — at the overflow boundary, what does userspace supply versus firmware/kernel own
  (does any new userspace-authored program/descriptor ever appear)?
- **H4** — what is the TVB's finite-resource envelope: capacity, growth granularity, and
  failure mode at exhaustion?

## Method

Two independent OWN-source pieces of read-only tooling are combined via environment
variables only — **neither is modified**:

1. `experiments/EXP-0118-a18-pro-partial-render-workload/build/partial_render` — the
   already-built, already-validated trigger/oracle binary (project-authored MSL + ObjC).
2. `tools/iotrace/iotrace.c` — the existing DYLD IOKit interposer, compiled read-only into
   `harness/build/iotrace.dylib`, used via `DYLD_INSERT_LIBRARIES` + its documented env vars
   (`IOTRACE_LOG`, `IOTRACE_DUMP_DIR`, `IOTRACE_MAX_MAP`) plus EXP-0118's own pre-existing
   `G17P_DUMP_BEFORE_COMMIT` hook (raises `SIGUSR1`, which iotrace's `usr1_thread` answers by
   snapshotting every sel-9-registered BO).

A frozen four-sweep matrix (`CAPTURE_CONTRACT.json`, derived from `harness/casematrix.py`,
never hand-duplicated):

- **Sweep A** — slope-corrected wall-clock timing vs. triangle count (H1), 1 to 20,000,000
  triangles, `accumulate` mode, 128x128, 8xR32F.
- **Sweep B** — mechanism/inventory trace vs. triangle count (H1/H2/H3), 6 points spanning
  the same range.
- **Sweep C** — mechanism/inventory trace vs. render-target dimension (H2 orthogonal axis),
  32x32 to 1024x1024, fixed N=1, to separate "more geometry" from "more tile state."
  independent axis.
- **Sweep D** — exploratory, single-shot, deliberately extreme-N limits probe (H4), using
  EXP-0118's `overflow` mode (avoids `accumulate` mode's float32-precision confound at
  extreme N) plus a post-case sanity re-check every time.

Every case is its own OS process (never batched, never reused), captured **twice**
(`raw/m4_20260828_run01/`, `raw/m4_20260828_run02/`) for a byte-exact reproducibility gate
over Sweep B/C's (size-multiset, selector-histogram) payload — GPU VA/CPU addresses are
recorded but excluded from that gate, per the standing "no nondeterministic field in
byte-compared records" rule (mirrors EXP-0108's proven address-independent method).

## Procedure

```sh
cd experiments/EXP-0120-m4-tvb-overflow-mechanism
harness/build_iotrace.sh                       # compiles tools/iotrace/iotrace.c read-only
python3 harness/casematrix.py                  # sanity-checks the frozen matrix + pins
python3 harness/run_sweep.py --smoke           # NON-RECORDED dry run -> work/smoke/
python3 harness/run_sweep.py --run-id <new-id> # official capture -> raw/<id>/ (57 cases)
python3 analysis/analyze.py <run-id>           # -> analysis/<run-id>.json + _report.txt
python3 analysis/verify.py --selftest
python3 analysis/verify.py --seqtest  --run01 m4_20260828_run01 --run02 m4_20260828_run02
python3 analysis/verify.py --captured --run01 m4_20260828_run01 --run02 m4_20260828_run02
```

The two run ids already used (`m4_20260828_run01`, `m4_20260828_run02`) must never be
reused; a follow-up capture takes a new id.

## Results

See `RESULTS.md` for the full observed-vs-interpreted writeup, gate results, and the
P0.4/`DRV-UAPI-04` implications. Headline: no independent signal (timing or BO-inventory)
shows partial-render engagement anywhere from 1 to 20,000,000 tile-concentrated triangles on
M4 for this configuration; the userspace-visible sel-9 BO inventory and IOKit selector-CALL
histogram are byte-identical across the entire tested range, in both officially gated runs;
cross-referencing the real, currently-shipping Asahi kernel UAPI (`mesa/include/drm-uapi/
asahi_drm.h`, read-only PUBLIC reference) shows there is no TVB/tiler-heap field in the
render/compute submit structs at all (kernel-managed by construction), while `bg`/`eot`/
`partial_bg`/`partial_eot` program records *are* required on every render, unconditionally —
which is consistent with, and mechanistically explains, EXP-0108's finding that the shader
code window never changes size. A genuine, non-deterministic hardware-level fault
(`kIOGPUCommandBufferCallbackErrorInnocentVictim`, cleanly recovered every time) was found
above ~10,000,000-100,000,000 triangles, with an unreproducible exact threshold.

## Established facts -> docs (for the orchestrator; this experiment does not edit `docs/`)

- Candidate correction to `docs/pipeline/README.md`'s tiler-parameter-buffer note: the
  region at `0x10000140000` ("sparse-tiler-param-header", EXP-0108) is **475136 bytes**
  (`0x74000`), not the `0x1000` EXP-0108 assumed; a second, previously-unnamed 786432-byte
  (`0xc0000`) region exists at a fixed relative position. Both are invariant across an
  20,000,000x triangle-count range and a 1024x pixel-count range (gate-proven, both runs).
- `docs/pipeline/README.md`'s existing "overflow -> partial-render trigger is firmware-
  managed — no userspace knob" claim is now supported by a genuinely tile-concentrated-
  geometry probe (not just EXP-0108's distributed-geometry one) up to 20,000,000 triangles,
  plus an independent UAPI-structural explanation (see `RESULTS.md` §6).
- A new, real finding for the finite-resource/limits documentation: non-deterministic
  `kIOGPUCommandBufferCallbackErrorInnocentVictim` GPU-recovery faults beyond ~10⁷
  tile-concentrated triangles (128x128, 8xR32F), cleanly recovered every time, no host risk
  observed.

## Clean-room statement

DATA-TRACE (our own process's IOKit boundary traffic, via the unmodified `tools/iotrace`
interposer) + HW-PROBE (black-box wall-clock timing and `MTLCommandBufferStatus`/error-string
observation of our own process, via EXP-0118's own already-public-API-only instrumentation).
A bounded amount of PUBLIC open-source reference material (`mesa/src/asahi/`,
`mesa/include/drm-uapi/asahi_drm.h`) was read, per `CLAUDE.md`'s explicit sanction of `mesa/`
as read-only reference, and is cited by exact file/line; it is never treated as Apple9/M4/A18
hardware evidence, and `mesa/` is not edited. No Apple binary was disassembled, decompiled, or
introspected. `tools/iotrace/` and `experiments/EXP-0118-.../` are used exactly as they were
written/built, read-only (pinned SHA-256 hashes in `CAPTURE_CONTRACT.json`).
