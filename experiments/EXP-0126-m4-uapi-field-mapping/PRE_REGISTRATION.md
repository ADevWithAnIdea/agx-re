# PRE_REGISTRATION — EXP-0126-m4-uapi-field-mapping

Frozen before any run under `raw/`. Pinned repository revision, source hashes, matrix,
schema, timeouts, and gates are recorded verbatim in `CAPTURE_CONTRACT.json`; this
document states the question, hypotheses, method, and safety controls.

**Numbering note.** `experiments/EXP-0126-m4-lifecycle-boundary-probe/` also exists under
the EXP-0126 number (observed mid-session; concurrent orchestrator activity). This
experiment keeps the exact path it was dispatched with,
`experiments/EXP-0126-m4-uapi-field-mapping/`; the collision is left for the orchestrator
to resolve at commit/renumber time.

## Question

`docs/P0-P1-CLOSURE.md` row P0.3 / `APPLE9_RE_IMPLEMENTATION_GAPS.md` DRV-UAPI-03 requires,
for every field in `drm_asahi_cmd_render`, `drm_asahi_cmd_compute`, and
`drm_asahi_queue_create` (65 leaves per `EXP-0045-uapi-field-matrix`):

```
userspace derivation -> UAPI value -> kernel/firmware marshaling -> observed Apple9 behavior
```

This experiment has two parts:

1. **Synthesis** (no new hardware run): for all 65 leaves, assemble the chain above from
   (a) the exact `asahi_drm.h` doc comment (file:line), (b) this repository's own prior
   M4/A18 evidence (`EXP-0014`...`EXP-0124` etc., cited per leaf), and (c) the pinned
   Mesa reference driver (`mesa/src/asahi/**`, MIT-licensed, PUBLIC per `CODEX.md` — used
   only to establish the *shape* of the userspace derivation formula for a field whose
   UAPI meaning is generation-invariant, never as a source of Apple9-specific numeric
   values, consistent with `CLAUDE.md`'s "mesa/ is a read-only reference for understanding
   the shape of what a userspace driver must produce"). This part produces the field table
   in `RESULTS.md` and requires no `PRE_REGISTRATION`-gated hardware run.
2. **New M4 hardware probes** (this document's falsifiable part) targeting the two
   highest-value gaps the dispatch explicitly names as unclosed:
   - **H-A (sample positions / `render.ppp_multisamplectl`):** whether the captured
     sample-position BO (`EXP-0021`/RT-4/RT-11/`EXP-M4-03`) reflects a hardware quantization
     grid and rounding rule that (i) is exhaustively confirmed across the full 1/16 grid on
     M4 (prior M4 replication, `EXP-M4-03`, only re-fed already-on-grid values), (ii) has an
     exact, located tie-breaking rule for off-grid inputs (RT-4 showed 4 arbitrary off-grid
     points snap to the nearest 1/16 on A18 only, pre-hands-off; never independently
     confirmed on M4, never bisected to the exact halfway threshold), and (iii) has a
     characterized behavior at and past the documented [0, 0.9375] range.
   - **H-B (`render.samples` valid range):** whether the documented "must be 1, 2, or 4"
     constraint is confirmed on M4 by both the public capability query
     (`supportsTextureSampleCount:`) and actual construction, across the full boundary set
     {0,1,2,3,4,5,6,7,8,16}, with exact negative behavior (not merely "fails").

## Hypotheses

- **H-A1 (grid):** for every `k` in 0..15, requesting `x = k/16` (already on-grid) as a
  custom sample position on M4 yields a captured BO value of exactly `k/16`, for both X and
  Y, at both tested sample counts (2 and 4). *Refuter:* any captured value not exactly
  `k/16` (accounting for exact `float` representation).
- **H-A2 (rounding):** off-grid requests snap to the *nearest* 1/16 grid point (round, not
  floor/ceil/truncate), with ties (`x*16` exactly `n+0.5`) resolved consistently in one
  direction. *Refuter:* a captured value inconsistent with round-to-nearest for any tested
  point, or an inconsistent tie direction across the two tested tie points (1/32, 3/32).
- **H-A3 (upper boundary):** requests inside Metal's documented custom-position range but
  above the grid's nominal maximum (0.9375) either clamp to 0.9375 or produce a value
  consistent with unclamped `round(x*16)/16` (which can reach 1.0 for `x` near 1). *Refuter:*
  a value that fits neither model (e.g., wraparound to a small value, or a NaN/garbage
  capture).
- **H-A4 (API range):** Metal accepts custom positions in `[0.0, 1.0)` and rejects (via a
  process-terminating assertion, not a catchable `NSError`) values `< 0.0` or `>= 1.0`.
  *Refuter:* any accepted negative value, any accepted value `>= 1.0`, or any rejection that
  is instead a silent no-op / catchable exception / GPU fault.
- **H-B1:** `supportsTextureSampleCount:` returns true only for {1,2,4} on this M4, and
  texture/pipeline construction at unsupported counts fails via a process-terminating
  assertion (not a catchable `NSError`) whose text names the offending count. *Refuter:* a
  supported count outside {1,2,4}, or a graceful (non-aborting) rejection.

## Independent / controlled variables

- Independent: requested sample-position `(x,y)` per sample slot (H-A); requested
  `rasterSampleCount`/texture `sampleCount` (H-B).
- Controlled: shader source (fixed, own MSL, inline in the harness), render-target format
  (`BGRA8Unorm`), viewport/target size, non-tested sample slots pinned to a fixed reference
  position distinct from every swept value, one case per fresh process (no cross-case
  state).

## Expected observation vs. falsifier

Stated per-hypothesis above. All are single-bit pass/fail against an exact captured `float`
or exact string/boolean, not a statistical or fuzzy comparison.

## Known confounders

- **Metal API-level validation vs. hardware behavior.** A rejection observed here is a
  Metal-runtime assertion (`libMTL`), not necessarily identical to what a Linux
  `drm_asahi` kernel/firmware path would do with the same raw bit pattern in
  `ppp_multisamplectl` — this experiment characterizes the **input contract as seen through
  the public Metal API**, and the captured BO values as **AGX's own internal float
  representation of the position**, not the packed 4-bit/4-bit Linux UAPI encoding itself
  (that packing, `hk_pack_ppp_multisamplectrl`, is Mesa PUBLIC-source shape, cited
  separately in `RESULTS.md`; it is not independently producible from macOS).
- **Allocator-dependent GPU addresses.** `vtxBuf`/`resBuf` VAs are expected to vary between
  processes/runs; excluded from the cross-run gate (`CAPTURE_CONTRACT.json` schema), proven
  not to mask a real difference (`verify.py --selftest`).
- **Process-terminating aborts are expected, not harness bugs.** Several boundary cases are
  *designed* to hit a Metal API-validation `assert()` (`SIGABRT`); this is captured as a
  first-class case outcome (`status: ABORT_sigN`, with the exact assertion text preserved in
  `raw_stderr`), not treated as an infrastructure failure. No case in the matrix drives a
  live GPU dispatch with an out-of-contract value (the abort happens before submission), so
  there is no GPU-fault/wedge risk from this specific matrix; see Safety below.
- **This is a macOS-only observation.** No Linux kernel exists to submit a real
  `drm_asahi_cmd_render` and observe firmware consumption; "hardware consumption" of the
  captured grid value is inferred from convergence with the independently-derived Mesa
  public packing formula and the RT-4/RT-11/EXP-M4-03 chain, not re-proven here by a new
  splice-and-observe test. `RESULTS.md` states this precisely per field; it does not
  overclaim `HW-VALIDATED` for the register-consumption step.
- **Sample-order / index disambiguation.** Only sample slot 0 is varied; slots 1..N-1 are
  pinned to reference positions distinct from every tested value, so offset `+0x40` (slot 0)
  is unambiguous without needing to identify slots by value.

## Superseded exploratory probe (process history, kept per CODEX §6)

An earlier design (`harness/sampcov.m`) attempted a stronger **HW-VALIDATED** test: render a
sweeping-edge rectangle into a multisample target and read back *raw per-sample* coverage
via a compute kernel (`texture2d_ms::read(coord, sample)`), to prove the rasterizer's
coverage decision — not just the captured BO bytes — tracks the requested sample position.
Diagnosis during pilot testing (not part of any registered run) found the compute kernel's
`dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)` call produces
`thread_position_in_grid == (0,0)` regardless of which output-texture pixel was intended,
so early multi-pixel variants of the diagnostic were reading the wrong pixel; even after
fixing the dispatch, reference "far" samples read as covered far before their requested
edge, an unresolved discrepancy not root-caused within this experiment's time budget. Rather
than land unverified HW-VALIDATED claims from a probe with a known-open discrepancy, this
path was abandoned in favor of the reliable, previously-validated DATA-TRACE method
(`sampos126.m`, extending RT-4/RT-11/`EXP-M4-03`'s own successful technique). `sampcov.m` is
retained as authored source and an honest record of a probe that did not pan out; it is not
invoked by `run.py` and contributes no claim to `RESULTS.md` beyond this note.

## Raw-record schema

One JSON object per case, appended to `raw/<run_id>/records.jsonl` immediately after the
case completes (`f.flush()` + `os.fsync()`), never buffered for a bulk end-of-run write.
Fields and the gated/non-gated split are defined in `CAPTURE_CONTRACT.json`
(`schema.gated_keys` / `schema.nongated_keys`). The one retained raw BO snapshot per
`sampos` case (the pre-classified sample-position BO only — no other BO in the transient
per-case dump directory is opened, scanned, or referenced) is copied to
`raw/<run_id>/hex/<case_id>.hex`.

## Environment / timeouts / safety

- Target: Apple M4 (G16G), Mac16,10, 10 GPU cores, macOS 26.6.2 (25G82), Metal 4 — the sole
  test target per `CLAUDE.md`. A18 Pro not touched.
- Per-case timeout 30 s, smoke-case timeout 20 s, build timeout 120 s (`subprocess` timeout,
  hard-enforced); a timed-out case is recorded with `rc=-9` and the case moves on — no
  cross-case state to corrupt.
- Every case is a single fresh process (`sh()` in `run.py`), matching the established
  one-case-per-process convention for this class of probe (`RT-11`'s `sp11.m`,
  `EXP-M4-03`). No live GPU dispatch runs with a value that Metal's own validation would
  reject — those cases abort at the CPU-side `setSamplePositions:`/
  `newTextureWithDescriptor:` call, before any command buffer reaches the GPU.
- `tools/iotrace/iotrace.c` is used **read-only**: built unmodified from source into
  `work/bin/iotrace.dylib` at the start of every `run.py` invocation; never edited.
- Standing gates (all five) enforced as described in `CAPTURE_CONTRACT.json.gates` and
  verified by `harness/verify.py`.
- Two independently captured runs: `m4_20260828_run01`, `m4_20260828_run02`. No run id is
  ever reused; a defective capture is retained and superseded by a new id, never repaired
  in place.

## Clean-room category

DATA-TRACE (H-A: our own process's committed sample-position BO, captured by the unmodified
`tools/iotrace` interposer) + HW-PROBE (H-B: public Metal capability query and
construction/validation behavior) + OWN-SHADER (inline MSL compiled at runtime, our own
source) for the new hardware probes; PUBLIC (pinned MIT-licensed `asahi_drm.h` and
`mesa/src/asahi/**`) + citation of this repository's own prior experiments for the
synthesis table. No Apple binary is disassembled, decompiled, or otherwise introspected.
