# EXP-0133 pre-registration — M4 full-format capability and conversion matrix

**Frozen state: PRE-GPU.** Target: local Apple M4 (G16G), macOS 26.6.2 (25G82),
Metal 4, arm64, device name "Apple M4", Mac16,10, public Metal API only. This
is the third increment of task-list item **DRV-FMT-01** (P1.2), succeeding
EXP-0070 (batch 1, six formats, fragment-store path) and EXP-0079 (batch 2,
fourteen formats, compute-store path, establishing three conversion rules:
snorm8 symmetric scale, reduced-float truncation, unorm8 round-half-up ties).
EXP-0095 separately establishes RGB32's total absence from `MTLPixelFormat`
and the texel-buffer 2^28 ceiling; both are cited, not re-derived, here.

DRV-FMT-01 demands, for **every exposed format**: sampled, filtered, storage
read/write, atomic, renderable, blendable, depth/stencil, linear, compressed,
MSAA, resolve, row/layer/depth pitch, mip offset, buffer-texture, swizzle,
normalization, rounding, and pack/unpack behaviour, explicitly including
RGB32, packed formats, sRGB storage, integer filtering, split depth/stencil
aspects, YUV, BC/ASTC/ETC/EAC, and PVRTC.

## Target matrix (frozen, full breadth)

`analysis/gen_formats.py` parses the public Metal SDK header
`MTLPixelFormat.h` (a public API interface header shipped with Xcode/CLT —
PUBLIC source, not a compiled Apple binary; reading it to obtain the integer
enum values needed to call the public runtime API is the same category of
action as EXP-M4-08's existing 96-format descriptor table, which already
enumerates the great majority of these formats by name) and derives, for
every non-sentinel `MTLPixelFormat` case (excluding `Invalid`=0 and
`Unspecialized`=263, the only two non-format sentinels in the enum): its
integer id, its MSL binding **kind** (`float`/`uint`/`int` — which template
parameter a kernel must declare to bind it at all; derived mechanically from
Metal's own `Unorm`/`Snorm`/`Float`→float, `Uint`→uint, `Sint`→int naming
convention, not a hardware claim), a **family** tag (`int_norm`,
`float_norm`, `xr`, `yuv422`, `depth`, `stencil`, `depthstencil`,
`stencil_view`, `compressed_bc`, `compressed_pvrtc`, `compressed_etc`,
`compressed_astc_ldr`, `compressed_astc_hdr`), and `bpp` (bytes/texel for
uncompressed families; `null` for compressed/YUV). This yields exactly
**138 formats** (`analysis/formats_generated.json`, frozen verbatim into
`CAPTURE_CONTRACT.json.formats`). This is the full target matrix DRV-FMT-01
asks for — not a subset.

## Hypotheses (pre-registered; some informed by pre-freeze exploration, disclosed below)

Pre-freeze exploration (`provenance/pre_freeze/`, uncommitted-to-evidence
process history, same status as EXP-0075's disclosed exploration in
EXP-0079's own pre-registration) ran a battery of ~30 ad hoc probes across
representative formats from every family to (a) discover harness-breaking
Metal API behavior before freezing the case grammar, and (b) form informed
hypotheses. Its two most important findings, load-bearing for this
contract's *design* (not assumed as this run's *result*):

**F1 — render-pipeline-descriptor validation for a statically non-color-
renderable/non-blendable pixel format is a hard `abort()`, not a catchable
`NSException`, and is unaffected by `MTL_DEBUG_LAYER`/
`METAL_DEVICE_WRAPPER_TYPE`.** Observed for `MTLPixelFormatBC1_RGBA`
("is not color renderable"), `MTLPixelFormatR32Uint` ("is not blendable"),
and every tested compressed/depth/stencil/YUV422 format. This determines the
case grammar below (renderable/blendable/msaa/resolve/depth_stencil axes run
as separate per-(format,axis) processes, not bundled with the other six
axes) and the derived `expect_may_abort` flag (true exactly when
`axis != depth_stencil and format.family in family_render_ineligible`).
**This is itself a normative finding, not merely a harness workaround**: it
means render/blend/MSAA/resolve target eligibility is enforced as an
unconditional host-side precondition on this API, not a soft per-call
capability negotiation — recorded in RESULTS.md as a first-class result.

**F2 — `minimumLinearTextureAlignmentForPixelFormat:` also hard-aborts**
(not "throws" in the catchable sense its own header doc claims) for
depth/stencil/compressed formats, **and additionally for YUV 4:2:2 formats**
(`GBGR422`/`BGRG422`), which the header doesn't mention. `family_linear_
ineligible` in `CAPTURE_CONTRACT.json` is the empirically-derived (not
header-derived) exclusion set the harness checks *before* ever calling this
API. A dedicated single case (`layout_below_minimum_RGBA8Unorm`) exercises
the companion boundary — one byte below the minimum accepted `bytesPerRow` —
as its own process, expected to abort; this is not re-tested per format
(the RGBA8Unorm exemplar plus F1/F2's structural character make a per-format
repeat purely confirmatory, not discovery, and the abort's own message names
the exact numeric boundary each time it fires elsewhere in the sweep).

**F3 (discovered mid-capture; the reason the case grammar below is FULLY
per-axis, not bundled at all) — bare `newTextureWithDescriptor:` itself hard-
aborts for a pixel format this specific device does not support at all**
("MTLTextureDescriptor has invalid pixelFormat (N)"), independent of usage
flags, and independent of F1/F2. The first real capture attempt (retained,
never reused, at `provenance/quarantined_attempt1/m4-20260828-run01/`, see
its `NOTE.md`) used a 6-axis-per-process "compute bundle" believed safe from
F1/F2 exploration; it ran 131/858 cases cleanly and then correctly STOPped
(its own `STOP.json`) on `MTLPixelFormatDepth24Unorm_Stencil8` (id 255),
losing that process's other five (already-successful) axis results along
with it. This corroborates the prior EXP-M4-08 finding
(`docs/descriptors/format-table.md`: "Unsupported on this HW (Metal
rejects): depth24unorm_stencil8, x24_stencil8") with a new mechanism-level
detail — the rejection fires at bare texture-descriptor validation, before
any usage-specific or render-pipeline check. A full systematic re-check
(`provenance/pre_freeze/precheck/`, all 138 formats × 11 axes, 1518 real
subprocess invocations, ~1 minute total) found **exactly these same two
formats** (255, 262 `X24_Stencil8`) abort on every axis that touches texture
creation, and independently confirmed one more structural class: **every integer-kind (`uint`/`int`)
format additionally aborts on `blendable`** (19 formats beyond the 83
already-non-renderable ones — Metal's documented "integer formats are not
blendable" restriction, now hardware-confirmed, not merely a soft capability
flag). `CAPTURE_CONTRACT.json`'s `device_unsupported_format_ids`
(`[255, 262]`) and `blendable_ineligible_kinds` (`["uint","int"]`) encode
exactly this precheck, and `run.py`'s `build_cases()` derives each case's
`expect_may_abort` from them (honoring the harness's own pre-Metal
short-circuits for `atomic`/non-integer-kind and `linear`/ineligible-family,
so a device-unsupported format's `atomic`/`linear` cases — which the harness
never lets reach Metal at all for those combinations — are correctly NOT
marked `expect_may_abort`; verified to exactly zero mismatches against a
full 1518-case precheck, `provenance/pre_freeze/precheck/`). **The case
grammar below abandons axis-bundling entirely** (every one of the 11
capability axes runs as its own process per format, 138×11 = 1518 cases) —
not merely for the two device-unsupported formats, but as a general policy,
since F1/F2/F3 together show no axis can be assumed safe to bundle a priori.

**F3 was itself discovered via a harness classification bug that produced a
SECOND quarantined attempt** (`provenance/quarantined_attempt2/
m4-20260828-run03/`, 1462/1548 cases, STOPped cleanly on
`cap_depth_stencil_00261_X32_Stencil8`): `analysis/gen_formats.py`
originally grouped `X32_Stencil8`/`X24_Stencil8` (view-only stencil-aspect
formats) into the SAME `(kind=float, family=depthstencil)` bucket as the two
real combined depth+stencil formats, causing the harness to attempt
`depthAttachmentPixelFormat = MTLPixelFormatX32_Stencil8` (correctly
rejected — "is not depth renderable" — but for the wrong reason, a
classification bug not new hardware information) and to run every OTHER
X32_Stencil8 axis with the wrong MSL binding type
(`texture2d<float>` instead of `texture2d<uint>`). Fixed: `X32_Stencil8`/
`X24_Stencil8` are now `kind=uint, family=stencil_view`, matching
`docs/descriptors/format-table.md`'s existing `x32_stencil8` descriptor code
(identical to plain `stencil8`'s). **Correcting this also REFUTED the
original assumption that X32_Stencil8 needs a texture view** to serve as a
direct `stencilAttachmentPixelFormat`: with the correct `uint` binding, the
precheck shows `depth_stencil` for `X32_Stencil8` completes cleanly
(command-buffer status 4) when used directly, no view required — so
`depth_stencil_direct_attach_ineligible_families` is empty in the final
contract, not `["stencil_view"]` as first assumed. This refutation is itself
recorded as a result (a Metal-format capability is BROADER than its "view
format" framing in Apple's naming/documentation suggested), not hidden.

**H1 (extends EXP-0079's H1 to 16-bit) — snorm16 encode scale is symmetric**
(`round(clamp(c,-1,1) × 32767)`, so −1.0 → `0x8001`), matching the snorm8
finding. Falsifier: the asymmetric `[-1,1]→[-32768,32767]` convention would
give `0x8000`. Cases: `r16snorm_m100` (−1.0, discriminates), `r16snorm_p100`
(+1.0, control — both conventions give `0x7FFF`).

**H2 (new, 16-bit unorm tie-breaking) — registered textbook expectation:
unorm16 encode ties round half-up**, extending EXP-0079's unorm8 round-half-
up finding (`r8unorm_sep_b`: 2.5/255 → `0x03`) to 16 bits by the same
reasoning. Falsifier disclosed from pre-freeze exploration (not assumed as
this run's result): the *same* two probes it used there — a tie at an
**odd**-floor value (`1.5/65535`, both round-half-up and round-half-even
predict `2`) and a tie at an **even**-floor value (`2.5/65535`, round-half-
up predicts `3`, round-half-even predicts `2`) — instead landed on `1` and
`2` respectively, i.e. **both ties rounded DOWN**, which neither
round-half-up nor round-half-even predicts. A third, non-tie control
(`5.9/65535`, unambiguous nearest-integer target `6`) landed on `6`,
refuting simple truncation/floor as the general rule (5.9 is not floor'd to
5). The three points together are most consistent with a **round-half-down**
tie-break (ties always round toward the lower integer; non-tie values round
to nearest as usual) — the opposite convention from unorm8. This
registration keeps the round-half-up value as the *frozen expectation* for
`r16unorm_sep_a`/`r16unorm_sep_b` (rule **c**, hypothesis-to-falsify per
EXP-0079's convention) and records round-half-down as the named falsifying
alternative; `r16unorm_nontie` is rule **a** (unambiguous nearest-integer,
not diagnostic between the two tie rules, but it does rule out plain
truncation). `rgba16unorm_sep` repeats the R-channel discriminator
(2.5/65535) alongside a non-discriminating G-channel control (1.5/65535) in
one 4-channel store, as an independent multi-channel cross-check.

**H3 (new) — sRGB storage applies the standard IEC 61966-2-1 encode curve on
compute `access::write`,** not a bypass-to-linear store. Textbook prediction
per format documentation: `srgb_encode(c) = 12.92c` for `c ≤ 0.0031308`,
else `1.055·c^(1/2.4) − 0.055`; encoded byte = `round(srgb_encode(c)×255)`.
Registered expected bytes (independently computed, `analysis/gen_contract.py`
does not compute these — see the plain Python one-liner in RESULTS.md):
`srgb8_low` (c=0.0031308) → `0x0a`; `srgb8_mid` (c=0.5) → `0xbc`; `srgb8_high`
(c=0.95) → `0xf9`. Falsifier: a bypass-to-linear store would instead give
`round(c×255)` = `0x01`/`0x80`/`0xf2`. The typed compute read of the same
texel is expected to apply the inverse (decode) curve, landing close to but
not necessarily bit-exact with the original linear input (fixed-function
sRGB hardware units commonly use a polynomial approximation, not the exact
reference curve); this experiment records the observed decoded value without
asserting bit-exactness to the reference decode formula, and explicitly
leaves "is the on-hardware curve the exact IEC reference curve, or a
polynomial approximation, and to what error bound" as `UNKNOWN`/successor
work.

**H4 — Metal's documented restriction that integer pixel formats cannot be
linearly filtered is enforced on real hardware,** not merely rejected by the
CPU-side API layer. `int_filter_r32uint` attempts a `minFilter=linear`
sampler bound to an `R32Uint` texture and dispatches a real sample; the
falsifiable question is whether this (a) is rejected at sampler/pipeline
creation, (b) executes but silently behaves as nearest (no interpolation
possible on integer data, consistent with any documented behavior), or (c)
executes and produces a fabricated interpolated integer result. No specific
outcome is assumed here; the tested value is recorded and interpreted in
RESULTS.md.

**H5 — BC1 decode of an authored, self-encoded solid-color block round-trips
correctly.** `bc1_white_opaque` (`color0=0xFFFF`, `color1=0x0000`, all-zero
2-bit indices) and `bc1_red565_opaque` (`color0=0xF800`) are constructed from
the public, well-known S3TC/DXT1 block layout (two little-endian RGB565
16-bit endpoints + 32 bits of 2-bit-per-texel indices; index `0` always
selects `color0` regardless of the 4-color/3-color mode bit, so these two
cases do not depend on resolving the mode-selection question at all) — an
**own-encoder** construction from a public compression-format specification,
not copied from any Apple artifact. Both chosen endpoint values are exactly
representable at their channel's full 5/6-bit precision, so the two
candidate 565→8-bit channel-expansion formulas (bit-replication vs.
linear-round) coincide for these two probes; discriminating them is
out of scope here (**explicitly unexercised**, named in RESULTS.md).
Expected decode: white → `(1.0,1.0,1.0,1.0)`; red → `(1.0,0.0,0.0,1.0)`.

**H6 — Depth32Float_Stencil8's depth and stencil aspects are independently
addressable and mutually non-corrupting.** `split_depth_stencil` renders one
draw writing depth=0.3 (via `depthCompareFunction=less`,
`depthWriteEnabled=YES`, clear=0.8) and stencil=0x5A (via
`stencilCompareFunction=always`, `depthStencilPassOperation=replace`,
reference=0x5A) to the SAME combined-format texture in one pass, then reads
the depth aspect directly (`depth2d<float>` bind of the combined texture —
the documented direct-bind path) and the stencil aspect via a texture view
created with `pixelFormat=X32_Stencil8` bound as `texture2d<uint>` (the
documented stencil-view path). Expected: depth read ≈ `0.3` (fp32 exact,
`0x3E99999A`), stencil read == `0x5A`, with **no cross-contamination** in
either direction.

**H7 (RGB32/PVRTC negative confirmations, not new hypotheses — re-citing
prior evidence).** `analysis/gen_formats.py`'s header parse independently
confirms EXP-0095's finding: no `MTLPixelFormatRGB32*` constant exists in
the 138-entry enumeration (`R32`/`RG32`/`RGBA32` triplets exist; no `RGB32`
gap-filler). The eight PVRTC formats (ids 160–167) ARE present as enum
constants (deprecated, `API_DEPRECATED("Usage of ASTC/ETC2/BC formats is
recommended instead", macos(11.0,15.0)...)`) and are part of the full
capability sweep like every other format; this pre-registration does not
assume their outcome — the sweep's `sampled`/`storage_read`/etc. results for
`family=compressed_pvrtc` are the answer, reported as a clean result
(positive or negative) in RESULTS.md rather than assumed here.

## Capability sweep case grammar (1548 cases total)

- **`cap_<axis>_<id>_<name>`** (138 × 11 = 1518 cases, one process per
  (format,axis) pair — every axis, not just the render-pipeline ones, per
  F3): `sampled`, `filtered`, `storage_read`, `storage_write`, `atomic`,
  `linear` (compute-path axes; content is NOT verified against a host oracle
  in this sweep — that is the conversion-rule section's job for a bounded
  subset — each records support and, for `ok`, the raw output words for
  informational value), `renderable`, `blendable`, `msaa` (sampleCount=4),
  `resolve` (MSAA-with-resolve), `depth_stencil` (attach as a depth and/or
  stencil target per the format's family; `not_applicable` without touching
  Metal for the 131 formats outside the depth/stencil/stencil_view
  families). `expect_may_abort` is derived per (format,axis) from F3's four
  rules (device-unsupported id, render-ineligible family, blendable-
  ineligible kind, depth_stencil-direct-attach-ineligible family) —
  `run.py`'s `build_cases()` is the single source of truth for this
  derivation, shared by the runner and verifier so they cannot drift.
- **`conv_<case>`** (13 cases): H1–H6 above.
- **`layout_<id>_<name>`** (11 cases) + **`layout_below_minimum_<name>`**
  (1 case): `minimumLinearTextureAlignmentForPixelFormat`/
  `minimumTextureBufferAlignmentForPixelFormat` per representative format
  (one per bpp class 1/2/4/8/16, one BC, one ASTC, one depth, one stencil,
  one YUV422, one XR) plus the boundary-violation case. This is the
  **public-API-observable** alignment/pitch surface; it does not re-derive
  the internal tiled/twiddled layout model (`docs/tiling/README.md`,
  bpp1 tile edge 128, already HW-validated by EXP-M4-04..08 via DATA-TRACE —
  cited, not repeated). Mip offsets within Metal's opaque/tiled storage mode
  are not observable through the public API at all (`getBytes` always
  returns whatever Metal's internal layout decodes to, never raw tiled
  bytes); this experiment does not claim otherwise.
- **`sparse_<id>_<name>`** (5 cases): a bounded representative subset
  (RGBA8Unorm, R32Uint, BC1_RGBA, ASTC_4x4_LDR, Depth32Float) querying
  `sparseTileSizeInBytes`/`heapTextureSizeAndAlignWithDescriptor:` and
  attempting one sparse-heap texture creation per format. Full per-format
  sparse residency semantics belong to DRV-ROBUST-01 (P1.5); this axis here
  only answers "does this format participate in sparse residency at all."
  **135 of 138 formats are explicitly NOT exercised on this axis** — named
  here, not silently narrowed.

**Explicitly unexercised cells (named up front, not discovered after the
fact):** bit-exact conversion verification for every compressed format
other than the two BC1 solid-color probes (no ASTC/ETC2/EAC/BC2-7/BC6H/
PVRTC decode oracle is constructed); bit-exact verification of the
capability-sweep's `storage_write`/`atomic`/render-pipeline axes' *content*
(only success/failure/informational readback, not a checked oracle, for all
138 formats — the conversion section is the bit-exact layer, deliberately
narrow); sparse residency for 135/138 formats; native/PBE-descriptor-level
layout (owned by prior EXP-M4-* work, cited not repeated); A18/G17P
replication (M4-only, per standing target discipline); mip-level pitch
beyond level 0 for any format; array/cube/3D texture dimensionality for any
axis (2D only throughout, matching EXP-0070/79/95's established scope).

## Environment, timeouts, gates

Same target as EXP-0079 (see header). Case timeout 60s (generous; observed
per-case wall time in exploration was well under 1s including a fresh
`MTLCreateSystemDefaultDevice()` and one small library compile). Host build
timeout 180s. `verify.py`/`run.py` implement the five standing gates:
`--selftest` (schema self-test against `run.py`'s own pure builders,
state-agnostic), `--seqtest` (PRE_GPU/RUN01_PRESENT/RUN02_PRESENT gate-
sequence state machine over synthetic fixtures built from `run.py`'s real
schema functions — never hand-typed), the non-recorded pre-capture smoke
gate (`run.py`'s `smoke_gate()`, one real GPU case — `cap_sampled_00070_
RGBA8Unorm` — run to `work/<run-id>/smoke/` before `raw/` is created),
byte-exact repeat excluding only `started_utc` (the sole nondeterministic
field any record carries — no pid/address/duration field exists anywhere in
this schema), and fixtures built from `run.py`'s real functions
(`build_fixture()` in `verify.py` calls `mod.build_cases`/`build_argv`/
`case_argv`, never a parallel hand-maintained case list).

**Design deviation from EXP-0079, disclosed:** EXP-0079's `run.py` stopped
the entire run on ANY case's nonzero exit (appropriate there: a uniform
34-case store+read replay where any harness-level failure meant a bug).
This experiment's capability sweep is pre-registered (F1/F2/F3 above) to
*legitimately* abort for a derived, named subset of its 1518 (format,axis)
cases (2 device-unsupported formats × 11 axes, 83 render-ineligible formats
× {renderable,msaa,resolve}, 19 additional integer-kind formats ×
{blendable}, 1 format × {depth_stencil}); per `CODEX.md`/`SUBAGENT_BRIEF.md`
("aborts are RESULTS," "keep failures... they bound the hardware"), `run.py`
here continues past a case whose contract entry carries
`expect_may_abort=true`, and only stops (writing `STOP.json`, same
append-only-and-terminal semantics) on an *unexpected* nonzero exit — i.e. a
case not marked `expect_may_abort` failing anyway, which would be a genuine
harness fault or new hardware behavior, either way requiring a fresh capture
under a new run id per the standing "never repair in place" rule. **This
happened once already** (F3, `provenance/quarantined_attempt1/`): the
pre-fix grammar's `expect_may_abort` derivation didn't yet know about the
device-unsupported-format class, so `run.py` correctly stopped at
case 131/858 rather than silently discarding or guessing past the surprise.

Pinned revision at pre-registration time: git HEAD `cf544b4dd1fb37047c7cfee6a70a0d1a87628666`
(clean tree for this experiment's own files at that point; F3's discovery
and the resulting harness/contract fix are later commits on top of it, still
pre-GPU-capture for the run ids actually promoted below). Captures compare
authored blob hashes across runs, not live `HEAD` (sibling experiments may
land commits between the two promoted runs -- confirmed to happen in
practice: see the F4 note below). **Run ids `m4-20260828-run01` through
`m4-20260828-run06` are retired** (`run01`, `run03`, and `run05` are three
retained, not-reused quarantined attempts, see below; `run02`/`run04`/
`run06` were never created). The two runs this registration actually
promotes are `m4-20260828-run07` and `m4-20260828-run08`.

**F4 (third quarantine; a gate bug, not a hardware finding) —
`m4-20260828-run05`** (`provenance/quarantined_attempt3/`) **is a complete,
clean, 1548/1548-case capture retained but not promoted**, because the bug
it exposed was in the tooling, not the hardware: `run.py`'s cross-run
preflight gate and `verify.py`'s `compare_runs()` both compared
`git_revision` (in addition to `authored_sha256`) between the two runs of a
pair. Two sibling experiments landed commits on `master` between run05's
capture and the second run's attempted start (this repository's active
multi-experiment workflow), moving `git_revision` with zero change to any
file this experiment owns -- exactly the EXP-0082 landmine
`SUBAGENT_BRIEF.md` already documents ("Pin the revision at pre-registration;
do not gate on live HEAD... repo HEAD moving because a sibling experiment
landed is not contamination"), now hit by this experiment's own gate despite
that documented precedent. Fixed in both files: the cross-run gate now
compares `authored_sha256` only; `git_revision`/`git_dirty` are still
recorded per run (for audit) but never gated on. Because the fix changes
`run.py`'s/`verify.py`'s own byte content, run05 (captured under the pre-fix
tooling) cannot be validly paired with a run captured under the post-fix
tooling, so both runs of the final promoted pair are recaptured fresh.

## Clean-room provenance

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC (Metal SDK header
`MTLPixelFormat.h`, read only for its public enum identifiers, never
disassembled/inspected as a binary; BC1's block layout is a public S3TC/DXT
specification, independently encoded by this harness, never copied from any
Apple artifact)
Inputs inspected: authored MSL (`kernels/capability.metal`,
`kernels/conversion.metal`), authored Obj-C harness (`harness/probe.m`),
authored Python orchestration/verification, the public Metal SDK header
(read-only, for enum identifiers), EXP-0079/EXP-0095's disclosed prior
findings (cited as established facts or read as hypotheses to test, never
copied as unverified new-experiment evidence)
Apple binary introspection: NONE
Reproduction: `python3 -B verify.py --captured` after both runs;
`python3 -B run.py --run-id <id> --execute` to (re)capture under a NEW run id
Evidence: `raw/m4-20260828-run07/`, `raw/m4-20260828-run08/` (1548 case
files + 3 top-level files each, append-only), `analysis.json`,
`manifest.json`, `PROGRESS.md`, plus the three retained quarantined attempts
at `provenance/quarantined_attempt1/m4-20260828-run01/` (131/858 cases +
STOP, pre-F3-fix grammar), `provenance/quarantined_attempt2/
m4-20260828-run03/` (1462/1548 cases + STOP, pre-classification-fix), and
`provenance/quarantined_attempt3/m4-20260828-run05/` (1548/1548 cases,
clean but unpaired, pre-F4-fix cross-run gate) — none promoted as
evidence — and the 138×11 pre-check at `provenance/pre_freeze/precheck/`
