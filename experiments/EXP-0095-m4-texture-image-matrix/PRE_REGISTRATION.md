# PRE_REGISTRATION — EXP-0095 m4-texture-image-matrix

**Closes (addendum Bundle E):** GLTEX-A04, GLTEX-A05, GLTEX-A06, GLTEX-A07, GLIMG-A01, GLIMG-A02
(`APPLE9_RE_OPENGL_TEXTURE_ADDENDUM.md`), deepening `TEX-09`, `TEX-11`, `TEX-13`, `TEX-23`,
`DRV-TEX-01`, `DRV-FMT-01`, `ATOM-*` per `work/ADDENDUM-TRIAGE-20260828.md`'s Bundle E entry.

**Pinned revision:** `b05383c5a40653b1176b0345806af1955bb87659` (working tree dirty with only
untracked sibling-experiment artifacts outside this directory — expected per `SUBAGENT_BRIEF.md`'s
explicit note that concurrent sibling landings are not contamination). Captures are validated
against the **authored blob hashes** recorded here, not against live `HEAD` at capture time.

**Target:** local Apple M4 (G16G), macOS 26.6.2 (25G82), Metal 4, arm64, `Mac16,10`. A18 Pro/G17P
is hands-off (not tested here); every finding is `INFERRED`-by-family for G17P unless independently
validated. Public Metal API only — no `tools/agx-isa` assembler/disassembler, no `tools/agxtest`
splicing anywhere in this experiment.

## Relaunch note (session interruption, not a defect)

This experiment's process was interrupted by a host/terminal problem before any pre-registration or
capture existed; the coordinator confirmed the interruption was environmental. At relaunch the
directory held only pre-freeze scaffolding (`kernels/`, `harness/`, `provenance/pre_freeze/` — none
of it frozen evidence), so no repair-in-place occurred and no evidence was lost. This is the first
and only pre-registration for EXP-0095.

## ISA-decoding caveat (2026-08-28 compiler-engineer cross-check, EXP-0099)

`apple9_isa_explainer.md` and `work/COMPILER-EXPLAINER-INTERACTION-20260828.md` report a confirmed
decoding bug in `tools/agx-isa/db.json`: the top bit of the disassembler's 7-bit `srcA_reg`/
`srcB_reg` fields for the compact float ALU form is actually a source-retention flag, not part of
the register index, so any register number ≥ 64 read from that tooling is suspect (EXP-0099 is
validating this on hardware; not this experiment).

**Applicability to EXP-0095: none of this experiment's frozen claims depend on it.** This experiment
never invokes the ISA assembler/disassembler or `tools/agxtest` splicing; every case is public-Metal
API behavior (compile / pipeline-create / dispatch / CPU-owned-buffer readback). The one place this
experiment's design *touches* ISA-level register semantics is GLTEX-A04's question of whether the
hardware's array-layer "extra coordinate" register is float-typed or a pre-rounded integer at the
instruction level — that question is explicitly left **UNKNOWN**, deferred to an assembler-based
successor, for an independent reason established during pre-freeze exploration: no public-Metal
`texture2d_array`/`texturecube_array` `sample()` overload accepts a float layer parameter at all (the
MSL type signature is `uint`-only), so there is no public-API angle on the raw instruction's operand
type, with or without the register-decoding bug. Case `a04_2darr_conversion`/`a04_cubearr_conversion`
below test the **software** conversion (MSL's own `round()`+`uint()` composition) that a driver must
apply before calling Metal's `uint`-typed entry point, not a raw hardware float-coordinate form.

## Pre-freeze exploration (informs scope; NOT captured evidence)

`provenance/pre_freeze/explore/*.metal` + `analysis/pre_freeze/dump_results_prefreeze.json` record
public-Metal compile/create/dispatch probes run before this contract was frozen, to determine which
matrix cells are even expressible. None of it is claimed as validated evidence — every finding it
surfaced is re-tested as a frozen case below where load-bearing. Findings that shaped scope:

1. `texture1d`/`texture1d_array` expose **only** implicit-LOD `sample(sampler, coord[, array])`,
   `read`, `write`, and size queries at the MSL level — no `bias`/`level`/`gradient`/`offset`/
   `gather` overload exists for 1D, and no `depth1d` type exists at all. (GLTEX-A05)
2. `depth2d_array`/`depthcube`/`depthcube_array` accept `sample_compare`
   (implicit/level/bias/gradient/offset-where-applicable) and `gather_compare`; they reject
   `access::write` (populate via CPU `replaceRegion:`, not a populate kernel). (GLTEX-A06)
3. Native texture atomics (`atomic_fetch_add` etc.) compile for 1D/1D-array/2D/2D-array/3D/
   `texture_buffer` but the AIR backend rejects `texturecube`/`texturecube_array` atomics at
   pipeline-creation time ("unlowered function call") — a real Metal-level negative result.
   Multisample (`texture2d_ms`/`_array`) exposes zero atomic member functions at all. (GLIMG-A01/A02)
4. The direct `[[texture(N)]]` compute argument-table ceiling is exactly **128** (0..127 legal, 128 a
   compile-time "out of bounds" MSL error) — a 17-point sweep from N=31 to N=256. A **separate,
   narrower** ceiling: `access::read_write` textures are capped at exactly **8** per function
   regardless of the 128-entry table (7 OK, 8 OK, 9 fails to compile); `access::write` (write-only)
   is NOT subject to this cap (scales to 128 like plain read). Atomics require `read_write`, so the
   direct-binding atomic capacity kernel is capped at 8, not 128. (GLIMG-A02)
5. A bindless `array<texture2d<float>, 4096>` argument-buffer struct compiles and creates a pipeline
   (feasibility only, not capacity saturation) — far beyond the 128 direct ceiling. (GLIMG-A02)
6. Texel-buffer width ceiling is exactly **2^28 = 268,435,456** elements, uniform across every texel
   byte width tested (1/2/4/8/16 bytes): `MTLTextureDescriptor` validation aborts the **process**
   (SIGABRT, uncatchable by `@try/@catch` — an assertion, not an `NSException`) for width 2^28+1,
   before any GPU submission. `MTLPixelFormatRGB32*` does not exist as a public enum constant at
   all (confirmed by compile-time lookup, not a hardware probe) — no 12-byte texel format exists in
   Metal's format enum. (GLTEX-A07)
7. A same-kernel same-thread `write()` immediately followed by `read()`/atomic of the same texture
   element is **not guaranteed visible without an explicit `t.fence()` call** (a documented public
   MSL member function) — discovered when the very first end-to-end harness draft returned 0 instead
   of the written canary. Cross-*encoder* (separate dispatch) visibility within one command buffer
   needs no such fence (Metal's automatic hazard tracking already handles it; EXP-0079's two-dispatch
   populate/read pattern already relied on exactly this without issue). Every kernel in
   `kernels/matrix.metal` that reads back its own same-invocation write calls `fence()` first.
8. Depth-compare boundary/tie semantics reconfirmed EXP-0034's established convention
   (`compareValue COMPARE storedDepth`, i.e. `ref COMPARISON depth`, not the reverse) against real
   hardware output for the exact tie case (`ref == depth == 0.5`, all 8 `MTLCompareFunction`s).
9. Out-of-range uint image/texel-buffer stores (a value exceeding the destination channel's bit
   width, e.g. writing `0xC0FFEE` to an `r8uint`/`rgba16uint` channel) **clamp to the channel's
   maximum representable value** (`0xFF`/`0xFFFF`), not a low-bits truncation — observed
   independently in both the direct-128 and texel-buffer harness paths.

## Hypotheses and falsifiers (per matrix family; frozen per-case detail in `CAPTURE_CONTRACT.json`)

For every hypothesis below, **rule "a"** cases have an exact predicted value (falsified by any
mismatch — a real defect); **rule "b"** cases are documented/textbook, non-diagnostic controls; **rule
"c"** cases are genuine hypotheses-to-falsify, where a "deviation" from the stated hypothesis is a
first-class finding, not an error.

- **GLTEX-A05 (1D op matrix).** H: the only executable 1D/1D-array operations at the public-Metal
  surface are implicit-LOD sample, fetch, image store, and size query (finding 1 above); read/write
  at the first illegal coordinate is silently absorbed (returns/drops, no fault, no aliasing).
  Refuter: any bias/level/gradient/gather/offset/shadow form that *does* compile for 1D, or any OOB
  access that faults, hangs, or corrupts a neighboring texel.
- **GLTEX-A06 (shadow/cube/cube-array matrix).** H: all six sample_compare/gather_compare forms
  execute correctly (matching the documented `ref COMPARISON depth` convention) across
  `depth2d_array`/`depthcube`/`depthcube_array`; face and array-layer boundaries behave like ordinary
  index boundaries (silent zero at the first illegal layer/face). Refuter: any form rejected by
  Metal, any compare-function disagreement with the documented convention, or non-zero content at an
  illegal face/layer.
- **GLTEX-A04 (array-layer conversion + boundary).** H: MSL exposes no float-layer sample overload
  (finding above); the hardware's uint-index clamping at the resulting integer boundary follows the
  same silent-zero pattern as every other boundary in this matrix. Refuter: a float-layer overload
  existing after all, or non-zero/aliased content at the first illegal integer layer.
- **GLTEX-A07 (texel-buffer boundary).** H: the width ceiling (2^28, finding 6) is uniform across
  texel byte size and independent of `MTLDevice.maxBufferLength`; the first-invalid element read/
  write is silently absorbed; out-of-range stored *values* clamp rather than truncate (finding 9).
  Refuter: a per-format-dependent width ceiling, any fault/hang instead of the documented process
  abort at 2^28+1, or truncation instead of clamping.
- **GLIMG-A01 (image op × dimension matrix).** H: `r32uint` image load/store/size round-trips
  correctly on every non-multisample dimension (1D/1D-array/2D/2D-array/3D/cube/cube-array/buffer);
  multisample image access either compiles-and-runs or is cleanly rejected, never silently wrong;
  unbound-texture reads return zero and unbound-texture writes are silently dropped; same-resource
  read/write aliasing within one dispatch is visible once fenced. Refuter: any dimension's round trip
  producing wrong (not zero, not the written value) content, or an MS case producing plausible-looking
  garbage instead of a clean success/rejection.
- **GLIMG-A02 (image-descriptor capacity census, EXP-0083 tradition).** H: the direct table (128
  entries) and the narrower read_write cap (8 entries) from pre-freeze exploration reproduce exactly
  under the frozen contract; the bindless (argument-buffer) path scales far beyond 128 with
  distinguishable per-entry canaries; holes (never-encoded in-array slots) and out-of-bounds indices
  (beyond the declared array length, including a period-CAP mirroring probe at `2×CAP` in the
  EXP-0083 tradition) read as zero and do **not** alias any legitimate populated entry; out-of-range
  writes/atomics through the bindless path are silently dropped rather than corrupting a real entry.
  Refuter: any ceiling that doesn't reproduce identically across both runs, any OOB read that returns
  a legitimate canary's content (aliasing/mirroring), or any OOB write/atomic that measurably corrupts
  a legitimate canary.

## Independent / controlled variables

Independent: operation (sample/gather/fetch/compare/load/store/atomic/size-query), dimension type,
boundary position (first legal / last legal / first illegal / deep-illegal), texel/channel format,
descriptor width. Controlled per case: single-thread `dispatchThreads(1,1,1)`, frozen CPU-authored
canary content (never GPU-populated for the read-side cases, avoiding circularity between the probe
and its own fixture), a 16-byte prefix/suffix guard region around every output buffer, and the
uniform two-run byte-exact repeat gate.

## Confounders and known limitations (declared up front, not discovered post hoc)

- The **direct-binding** "selector" (GLIMG-A02) is chosen at **MSL compile time**
  (`[[texture(N)]]`), not at runtime — its "first illegal value" is a compile-time ceiling (129 does
  not compile), structurally different from EXP-0083's runtime byte-spliced base-slot selector. The
  **bindless** path's index genuinely is a runtime value (from a buffer) and is the direct analogue
  of EXP-0083's methodology; both paths are tested, and this distinction is called out explicitly in
  `RESULTS.md`, not glossed over.
- `a07_tb_*_write3` and the two `a02_bindless_write_*`/`a02_bindless_atomic_*` non-`first_populated`
  cases write to **all three (or one) boundary indices in a single dispatch** rather than isolating
  one boundary value per process; a corruption confined to *between* the tested indices would not be
  distinguished from a clean result. Declared as a scope limitation, not fixed here (successor work).
- `a02_bindless_atomic_*` cases (other than `first_populated`) reuse the shared `OUT` buffer across
  two dispatches (the atomic op, then a canary readback); the frozen record therefore carries only
  the **canary readback**, not the atomic's own previous-value return, for those cases (declared in
  each case's `rule_note`).
- Mipmapped 1D minification with real derivative-driven (non-implicit-LOD-0) filtering needs a
  fragment-stage draw (compute has no derivatives; already established: implicit LOD always resolves
  to 0 in compute). **NOT exercised** in this all-compute matrix; flagged as a successor item.
- GLTEX-A01's bias-operand item and GLIMG-A02's compare-filtering-footprint sub-question are covered
  by EXP-0034, not repeated here.

## What will NOT be exercised (declared, not silently dropped)

Per Bundle E's own sizing note ("largest bundle by matrix size") and the standing instruction to
freeze a coherent subset rather than silently narrow: this 85-case matrix is a representative,
boundary-focused subset, not an exhaustive op×dimension×format cross product. Explicitly out of
scope here (recommended successor work, listed again in `RESULTS.md`):

- Fragment-stage (real-derivative) LOD/minification behavior for any dimension — everything here is
  compute-stage, implicit LOD pinned to 0.
- The full advertised `MTLPixelFormat` set (96 formats per `docs/descriptors/format-table.md` §2d)
  for image load/store — GLIMG-A01 tests a representative 6-format class sweep on 2D plus a uniform
  `r32uint` probe across every dimension, not every format on every dimension.
- Raw ISA-level descriptor/selector injection (the assembler path) for any capacity boundary —
  everything here stays on the public-Metal behavioral surface per Bundle E's own "no" default.
- Multi-thread / cross-thread contention on the atomic paths (GLIMG-A02's atomics are single-thread
  `dispatchThreads(1,1,1)` correctness probes, not concurrency/throughput tests).
- Bindless capacity beyond `CAP=256` declared array entries (pre-freeze exploration only fed
  feasibility at N=4096, not a captured boundary).
- 2D multisample-array cube/cube-array multisample combinations, sparse/tile residency, and every
  GLIMG-A01 boundary sub-case (offset/partial-write is tested only on 2D and cube, not every dim).

## Environment / timeouts / raw schema (closed)

Per-case timeout ≤ 90s (900s hard ceiling on any `verify.py`/`make_manifest.py` gate subprocess,
matching `--seqtest`'s ~13 no-GPU subprocess spawns). Raw tree: `00_inputs.json`, `01_host_build.json`,
`run_manifest.json`, and one `case_<id>.json` receipt per of the 85 contracted cases — closed key set,
enforced by `verify.py`. Smoke case: `a05_1d_read_first` (a cheap, fast, exact rule-"a" case), run
once per contracted run, never recorded into `raw/`.

## Clean-room provenance

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC (MSL header syntax lookup only, for public API
calling conventions — no hardware/algorithmic fact taken from it)
Inputs inspected: authored MSL (`kernels/matrix.metal`, `kernels/direct128.metal`), authored ObjC
harness (`harness/probe.m`), authored Python runner/verifier/analysis
(`run.py`/`verify.py`/`analysis.py`/`make_manifest.py`), authored case generator
(`kernels/gen_direct128.py`, `provenance/gen_contract.py`)
Apple binary introspection: NONE — no Apple binary, archive, BO, private interface, or ISA
assembler/disassembler was ever touched by this experiment
Reproduction: see README.md's command sequence
Evidence: `raw/m4-20260829-run01`, `raw/m4-20260829-run02`, `analysis.json`, `manifest.json`
