# PRE_REGISTRATION — EXP-0134-m4-lossless-compression

Frozen before the two official capture runs. Target: DRV-P2-01 (lossless compression)
in `APPLE9_RE_IMPLEMENTATION_GAPS.md`, extending — not redoing — EXP-0017 (A18 codec
first pass) and EXP-M4-07 (M4 tiling/compression coverage, `docs/tiling/README.md`
§4). **Local M4/G16G only. A18 hands-off.**

## What is already established (not retested from scratch)

Per `docs/tiling/README.md` §4 (HW-validated, A18-confirmed): eligibility = no
ShaderWrite/PixelFormatView usage ∧ actual W≥16∧H≥16 texels (bpp/format-family
independent); secondary VA = baseVA + paddedImageBytes, encoded exactly like the
base VA; aux = numTexels/32 = 1 state byte per 8×4-texel block, in Morton-of-blocks
order; observed state bytes 0x03/0x15/0x7f; compression×mipmaps = one contiguous
aux after the full chain. **Still open per that doc's own "Unknowns" section:** the
block codec bitstream (explicitly OUT OF SCOPE here — see Clean-room boundary
below), the exact per-sample MSAA aux ratio, the full state-byte alphabet and what
each means for a driver, CPU access to a compressed resource, and blit/store-action
interaction.

## Clean-room boundary (read before building on this)

We document the compression **state ENCODING** (which discrete values the aux byte
takes and what content pattern correlates with each) and the **geometry** (size,
placement, eligibility). We do **not** attempt to recover the compressed-block
**bitstream** (the bit-exact codec that turns pixels into the ~4-bytes/block-header
main-image stream EXP-0017 partially observed). A CPU-write probe that deliberately
crafts specific *raw compressed bytes* to see which are legal would cross from
"observing hardware output" into "reverse-engineering Apple's codec algorithm" —
this is explicitly the row's forbidden target and this experiment's STOP condition.
For that reason, the CPU-write questions below are scoped to Metal's **public**
CPU-write API (`replaceRegion:`) rather than raw same-process pointer splicing: we
observe what happens to the descriptor/aux state when Apple's own supported
CPU-write path is used, never what byte patterns are individually acceptable as a
raw block encoding.

## Method

Public Metal API (`newLibraryWithSource:` runtime compilation of our own MSL,
`replaceRegion:`/`getBytes:`/blit — all public, documented CPU/GPU-visible calls) +
HW-PROBE (live GPU dispatch/readback, known patterns in) + DATA-TRACE (our own
process's GPU buffer objects, snapshotted by the **read-only, unmodified**
`tools/iotrace` interposer, built into `work/iotrace.dylib`). `harness/cprobe.m`
creates one resource per process and writes any pattern **only via the render
pipeline** (clear or draw) — compute image-store (`access::write`) is deliberately
never used on a compression-candidate texture, because `MTLTextureUsageShaderWrite`
itself disables compression (already established), which would silently defeat
every aux-content probe. `harness/auxdecode.py` locates the 32-byte sampled
descriptor in the dump (generalizing EXP-0017's `twiddle.py` / EXP-M4-07's
`solve3d.py` — our own prior authored technique) and decodes the compression flags
+ secondary VA + measured aux bytes.

**Scope note (every case carries `MTLTextureUsageShaderRead`).** The bind-and-read
descriptor-capture method requires `ShaderRead` usage. A texture used exclusively
as a render target with no `ShaderRead` at all is out of scope for this experiment
(per `docs/descriptors/README.md`, render-target-attachment state may in general
ride a structurally different descriptor than the sampled one; reaching it would
require a new method and is not needed to answer DRV-P2-01's eligibility/geometry/
state/CPU questions, since RenderTarget+ShaderRead is what any driver resource
that is later sampled — the overwhelming common case — will use).

## Hypotheses, variables, falsifiers

### Group ELIG — eligibility (families: elig_usage, elig_storage, elig_type, elig_linear, elig_boundary)

**H-E1 (usage: ShaderWrite and PixelFormatView are each independently
sufficient to disable compression, not only in conjunction).** Every usage combo
containing ShaderWrite OR PixelFormatView shows `compression_flag_word1_b27=0`,
regardless of RenderTarget/ShaderRead also being present; every combo with neither
shows `=1` (at eligible size). *Independent variable:* usage bit combination (6
combos × 2 sizes). *Falsifier:* a combo containing ShaderWrite or PixelFormatView
alone (not both together) still compresses — this would mean
`docs/descriptors/README.md`'s "ShaderWrite AND PixelFormatView disable" wording
denoted a conjunction requirement, not two independently-disabling bits, and the
doc needs correcting.

**H-E2 (storage mode does not gate eligibility, but may gate observability).**
`StorageModePrivate` shows the same compression flag behavior as `StorageModeShared`
for identical usage/size. `StorageModeMemoryless` may reject the standalone
compute-kernel bind step used for descriptor capture (memoryless resources are
tile-pipeline-local); if so this is recorded as a `N/A` (untestable-via-this-method)
result for memoryless, not assumed either way. *Falsifier:* Private shows a
different compression flag than Shared at the same usage/size.

**H-E3 (per-plane eligibility extends to array/cube/3D/MSAA types; the family
already established this on M4 per EXP-M4-07 — this group reconfirms with fresh
captures on the frozen matrix, not a new claim).** *Falsifier:* any type shows
compression at a per-plane size below 16×16, or fails to compress at 32×32.

**H-E4 (linear/buffer-backed textures never compress, at any usage/size).** A
buffer-backed texture at an otherwise-eligible size/usage shows
`compression_flag_word1_b27=0`. *Falsifier:* a linear texture shows the flag set —
this is the direct, simplest answer to the row's own escape-clause question
("can compression stay disabled"), so a falsification here is high-value either way.

**H-E5 (the W≥16∧H≥16 threshold reconfirms cleanly on non-square dims).**
16×16 compresses; 15×15, 16×15, 15×16 do not. *Falsifier:* any asymmetric case
breaks the per-dimension (not per-area) reading of the threshold.

### Group AUX — geometry (families: aux_bpp_size, aux_msaa_ratio, aux_alloc_floor, aux_mip)

**H-A1 (aux = numTexels/32 holds exactly at every tested bpp, for dedicated-BO
sizes).** For each of 7 formats (bpp 1/2/4/8/16, float/unorm/uint families) at two
tile-aligned sizes clearing the ~16KiB dedicated-BO threshold, measured aux bytes
(via `main_bo_size − 0`, since dedicated BOs start exactly at the descriptor's base
VA) equals `W·H/32` exactly. *Falsifier:* any tested (format, size) pair's measured
aux deviates from the formula.

**H-A2 (MSAA aux ratio is exactly `numTexels·N/32`, i.e. per-(pixel,sample), not
per-pixel-regardless-of-N).** For rgba8unorm and r16float at a fixed W×H, aux bytes
at N=2 and N=4 are exactly 2× and 4× the N=1 value. *Falsifier:* aux does not scale
linearly with N (e.g. stays constant, or scales by a non-integer/non-N factor) —
this is the row's specifically-requested "MSAA auxiliary ratio," currently
unresolved in `docs/tiling/README.md` §4.5.

**H-A3 (minimum aux-allocation floor at small dedicated-BO sizes).** *Informed by
pipeline-validation pilot runs (PROGRESS.md M3), stated here for confirmation, not
first discovery:* when `numTexels/32 < ~128` bytes AND the texture still clears the
dedicated-BO threshold (bpp16 only, since bpp≤8 dedicated sizes always predict
≥128B aux at the sizes tested), measured aux is clamped to a floor rather than the
raw formula value. Two adversarial cases (32×32 predicting 32B, 32×64 predicting
64B) both test this; if both measure the same floor value, that supports a hard
floor over a fixed multiplier. *Falsifier:* either case matches its raw formula
value exactly (no floor), or the two cases show different non-formula values
(would refute "hard floor," suggest some other rule).

**H-A4 (small (<16KiB main-image) compression-eligible textures are suballocated
from a shared heap BO with a fixed allocation granule, not given a dedicated BO).**
*Informed by pilot runs (PROGRESS.md M2).* N identical small textures' base VAs
are evenly spaced by `round_up(main_bytes + aux_bytes, granule)` for some constant
granule, reproducible across ≥3 independent (format, size) configurations.
*Falsifier:* base-VA deltas are not uniform across N replicas of the same shape
(would mean the allocator is not simply packing them tightly), or the implied
granule is inconsistent across configurations.

**H-A5 (compression×mipmaps aux extent grows with a larger mip chain, consistent
with EXP-O2G's A18 finding of one contiguous aux over the whole chain).** A 4-level
64×64 chain's measured aux exceeds the 1-level 64×64 case's aux. *Falsifier:* equal
aux size regardless of mip count (would mean only the base level gets aux, or aux
is not measurable this way for mipped textures with this method).

### Group STATE — aux state ↔ data pattern correlation (families: state_pattern, state_format_repeat)

**H-S1 (uniform color, smooth gradient, and high-entropy noise occupy at least
three distinct, mutually exclusive aux state codes).** *Reconfirms EXP-0017's
0x03/0x15/0x7f finding with a fresh capture; not a new claim on its own.*
*Falsifier:* any two of these categories share a code.

**H-S2 (different uniform colors — including the true black/white extremes — share
ONE state code, i.e. the code denotes "constant block," not the specific color).**
*Falsifier:* black, white, mid-gray, and an arbitrary color produce different codes
from each other (would mean the state encodes something about the specific value,
e.g. a fast-clear-specific code for exact 0/1, not merely "constant").

**H-S3 (a single-texel outlier in an otherwise-uniform 8×4 block produces a
FOURTH, distinct state code — evidence of a limited-palette/defect-tolerant
compression mode beyond simple uniform/gradient/raw).** *Informed by a pilot
observation (PROGRESS.md M2: outlier→0x21).* Three outlier configurations (small
color delta, large color delta, corner position) are tested; if all three produce
the same non-{0x03,0x15,0x7f} code, that is strong evidence for a real fourth
state (not sampling noise). *Falsifier:* any outlier case instead reads 0x7f
(falls back to fully-raw) or 0x03/0x15 (treated as noise-in-the-formula, i.e. no
distinct partial-compress state exists) — this is a first-class negative result if
it happens, not a defect.

**H-S4 (the state-code alphabet is format-independent — the same numeric codes
recur for r32uint and rgba16float, not merely a bpp4-specific vocabulary).**
*Falsifier:* the same content pattern (clear/gradient/noise) produces different
numeric codes on a different format family (uint vs. float) at the same bpp class.

### Group CPU/PBE — CPU-visible access and render-target interaction (families: cpu_replace, cpu_getbytes, cpu_blit, cpu_storeaction)

**H-C1 (`replaceRegion:` succeeds on a compression-eligible texture both before
and after it has been GPU-rendered/compressed, and does not fault).** *Falsifier:*
an exception/rejection on either the pre-render or post-render call.

**H-C2 (after `replaceRegion:` touches an already-compressed sub-region, the
descriptor's compression flag and/or the touched block's aux state change —
i.e. Metal's public CPU-write path re-derives compression state rather than
leaving stale aux bytes behind a CPU-overwritten region).** *Falsifier:* the
before/after dump shows byte-identical aux content in the touched region despite
different main-image content (would mean a CPU write can desynchronize aux from
data through the public API — a genuine correctness hazard worth flagging loudly
for the driver either way, not merely a null result).

**H-C3 (`getBytes:` on a compressed texture returns correctly DECODED texel
values, proving Metal transparently decompresses for CPU-visible reads rather
than exposing the raw codec stream).** *Reconfirms a pilot observation
(PROGRESS.md M2: GETBYTES_TEXEL00_MATCH=1).* *Falsifier:* returned bytes do not
match the known pattern formula (would mean getBytes exposes raw/incorrect data on
a compressed texture — a serious finding).

**H-C4 (a blit copy between two same-shaped compression-eligible textures
succeeds and the destination is itself compression-eligible/compressed).**
*Falsifier:* the blit fails, or the destination's compression flag differs from
the source's under identical eligibility conditions.

**H-C5 (MTLStoreActionDontCare on a compression-eligible render target does not
crash or corrupt the command buffer; its aux/descriptor content afterward is not
gated to any specific value since a "don't care" store makes content formally
undefined).** *Falsifier:* the command buffer errors, or the process
crashes/hangs — content divergence from the Store case is expected and is not
itself a falsifier.

## Confounders

- GPU VA allocation is assumed deterministic run-to-run on a fixed pinned revision
  with a fixed harness and fixed inputs (no ASLR-sensitive addressing at the GPU-VA
  level; matches EXP-0009/0011/0017/M4-07 precedent, all of which relied on the
  same assumption for reproducible captures). Confirmed for THIS harness by the
  cross-run gate (`verify.py --captured`) requiring byte-identical `observed`
  across run01/run02.
- The dedicated-BO vs. shared-heap suballocation behavior (H-A4) is a property of
  Apple's own private small-object allocator, observed as a side effect of our
  DATA-TRACE method — not assumed to be a hardware requirement a third-party
  driver must replicate. The *logical* aux-size formula (H-A1) is the portable
  fact; the allocator granule is reported as an OBSERVED curiosity, clearly
  labeled INTERPRETED, not promoted as a UAPI requirement.
- `MTLStoreActionDontCare` (H-C5) makes content formally undefined by the Metal
  spec; any content difference from the Store case is not evidence of anything
  beyond "content differs," and is not used to support or refute any other
  hypothesis in this experiment.
- Memoryless-storage bind failures (H-E2) are recorded as `N/A`, not `FAIL` — an
  untestable-via-this-method result is not evidence that memoryless textures
  never compress, only that this experiment's method cannot observe them.
- All findings are M4/G16G-only; no A18 Pro claim is made anywhere in this
  experiment (target discipline, CLAUDE.md 2026-08-27 directive).

## Pinned environment

- Device: Apple M4 (G16G), Mac16,10, 10 GPU cores, macOS 26.6.2 (25G82), Metal 4.
- Compiler: runtime `newLibraryWithSource:` only (no offline `metal` CLI).
- Repository revision pinned at freeze time in `CAPTURE_CONTRACT.json`
  (authored-blob-hash gated, not gated on live `HEAD` — sibling experiments commit
  continuously to this repo).
- `tools/iotrace/iotrace.c` used **read-only**, built unmodified into
  `work/iotrace.dylib`.

## Method summary (detail in README.md)

One ObjC harness binary (`harness/cprobe.m`, kinds `probe` and `replicate`), each
process invocation running exactly one case (SAFETY: memoryless-resource binds,
tiny shared-heap allocations, and CPU-visible splices can fault a GPU context).
`harness/casematrix.py` freezes the 83-case matrix. `harness/auxdecode.py` decodes
the sampled texture descriptor + aux bytes from an iotrace dump (generalizing our
own EXP-0017/EXP-M4-07 technique). `harness/run.py` drives one subprocess per case
under a hard timeout, invokes `auxdecode` on the resulting dump, and splits each
result into a gated record (`case_id, family, kind, params, status, verdict,
observed` — deterministic, no raw timestamps) and a non-gated sibling (`case_id,
wall_ms, pid, raw_tail, raw_ticks`). `harness/verify.py` implements the five
standing gates.
