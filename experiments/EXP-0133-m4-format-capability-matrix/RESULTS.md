# EXP-0133 results — M4 full-format capability and conversion matrix

**STATUS: COMPLETE. Both contracted runs captured, byte-exact repeat
verified (modulo a disclosed, corrected analysis-script bug in the
diagnostic itself — see "Gate results"), all five standing gates PASS.**
DRV-FMT-01 (P1.2) capability/conversion/layout/sparse breadth is CLOSED for
the scope defined in `PRE_REGISTRATION.md`, across the full 138-format
target matrix, M4-target only. Third increment of DRV-FMT-01, after EXP-0070
(six formats, fragment-store path) and EXP-0079 (fourteen formats,
compute-store path). This experiment adds the FULL capability breadth
DRV-FMT-01 demands (every exposed `MTLPixelFormat` × eleven capability
axes) plus bounded conversion-rule, layout, and sparse extensions.

Target: **local Apple M4 (G16G), macOS 26.6.2 (25G82), Metal 4, arm64,
device "Apple M4", Mac16,10**, public Metal API only. Nothing here is an
A18/G17P, Linux, native-command-stream, or PBE-descriptor result.

## Capture history: three quarantined attempts, fully disclosed

This experiment's own case grammar hit three real problems before its final
promoted pair. Per `CODEX.md`/`SUBAGENT_BRIEF.md` ("aborts are RESULTS,"
"never repair a quarantined experiment in place," "never reuse a run id"),
each was retained (not deleted, not repaired in place) and the promoted pair
recaptured fresh under corrected tooling:

| attempt | run id | outcome | cause | retained at |
|---|---|---|---|---|
| 1 | `m4-20260828-run01` | STOPped 131/858 | F3: bare `newTextureWithDescriptor:` hard-aborts for a pixel format this device does not support at all (`Depth24Unorm_Stencil8`), discovered mid-run under the original 6-axis-per-process "compute bundle" grammar | `provenance/quarantined_attempt1/` |
| 2 | `m4-20260828-run03` | STOPped 1462/1548 | A harness classification bug: `X32_Stencil8`/`X24_Stencil8` were misclassified `(kind=float, family=depthstencil)` instead of `(kind=uint, family=stencil_view)`, causing a wrong `depthAttachmentPixelFormat` attempt (correctly rejected, wrong reason) and 10 sibling axes run with the wrong MSL binding type | `provenance/quarantined_attempt2/` |
| 3 | `m4-20260828-run05` | Complete, clean, 1548/1548, but unpaired | `run.py`/`verify.py`'s cross-run gate compared `git_revision` (not just `authored_sha256`); two sibling experiments landed commits between this run and the second run's attempted start — the EXP-0082 landmine `SUBAGENT_BRIEF.md` already documents, hit anyway | `provenance/quarantined_attempt3/` |

None of these is a hardware-behavior finding (attempts 2 and 3 are pure
tooling bugs; attempt 1's *content* — `Depth24Unorm_Stencil8`/
`X24_Stencil8` unsupported — corroborates prior EXP-M4-08 evidence and is
carried forward, correctly, into the promoted result below). Full technical
detail in each `NOTE.md` and in `PRE_REGISTRATION.md`'s F1–F4.

The promoted pair is **`m4-20260828-run07`** / **`m4-20260828-run08`**.

## Gate results

| gate | result |
| --- | --- |
| `verify.py --preflight` (PRE_GPU) | **PASS** |
| `verify.py --selftest` | **PASS** (re-run after every fix; final pass includes a regression check that a `git_revision`-only difference does NOT fail `compare_runs`) |
| `verify.py --seqtest` | **PASS** — 4/4/5 real subprocess gate checks across PRE_GPU/RUN01_PRESENT/RUN02_PRESENT fixtures built from `run.py`'s own schema functions |
| non-recorded smoke gate | **PASS** before each of run07/run08 (`cap_sampled_00070_RGBA8Unorm`, real GPU case, written to `work/<run-id>/smoke/`, never to `raw/`) |
| `raw/m4-20260828-run07/` | **CAPTURED** — 1548/1548 cases, no `STOP.json` |
| `verify.py --between-runs` | **PASS** |
| `raw/m4-20260828-run08/` | **CAPTURED** — 1548/1548 cases, no `STOP.json` |
| `verify.py --captured` | **PASS** — cross-run byte-exact repeat on every receipt field except `started_utc` (per-case) and `argv[0]`'s run-id-scoped probe path (which is an intentional, by-design, deterministic difference — see next row) |
| `analysis.py --write` | **PASS** but its own diagnostic is misleading as shipped: it compares full `argv` across runs and reports `repeat_exact=False, mismatch_count=1548` (every case, always on the `argv` field alone), because `argv[0]` is each run's own freshly-compiled `work/<run-id>/probe` path. This is a disclosed bug in a **derived reporting script**, not in evidence: `analysis.py` is part of the frozen `AUTH` set (hash-bound in both runs' `00_inputs.json`), so it cannot be edited post-capture without breaking `verify.py`'s post-capture source-binding check — exactly the protection that check exists to provide. Fixed correctly in a NEW, non-frozen script, `analysis/repeat_check_corrected.py`, which recomputes the same comparison excluding only the run-id-scoped probe path and `started_utc`: **`repeat_exact_corrected: true, mismatch_count: 0`** across all 1548 cases (`analysis/repeat_check_corrected.json`). `analysis.py`/`analysis.json` are left exactly as captured (their field says `repeat_exact: false` — read it with this note, not in isolation). |
| `make_manifest.py --check` | **PASS** (state=CAPTURED) |

**No nondeterministic field appears in any byte-compared record**: every
receipt's `started_utc` is checked for ISO-8601 format only, never for
equality; every other receipt field, and every parsed JSON payload field, is
compared byte-exact across runs (`argv[0]`'s deterministic-but-run-scoped
probe path is the sole, disclosed, by-design exception, corrected for in
`repeat_check_corrected.py`).

## The target matrix: all 138 exposed `MTLPixelFormat` values

`analysis/gen_formats.py` parses the public Metal SDK header
(`MTLPixelFormat.h`) and enumerates every non-sentinel format (excluding
`Invalid`/`Unspecialized`): **138 formats**, spanning `int_norm` (43),
`compressed_astc_ldr` (28), `compressed_bc` (14), `compressed_astc_hdr`
(14), `compressed_etc` (10), `compressed_pvrtc` (8), `float_norm` (8), `xr`
(4), `depthstencil` (2), `yuv422` (2), `stencil_view` (2), `depth` (2),
`stencil` (1).

## Capability matrix: 138 formats × 11 axes = 1518 cells, every cell exercised

Every axis ran as its own process per format (1518 real subprocess
invocations per run, no bundling) — see `PRE_REGISTRATION.md` F1–F3 for why
bundling is unsafe on this API (three independent hard-abort classes, none
catchable via `NSException`, none affected by `MTL_DEBUG_LAYER`). Per-axis
outcome counts (identical both runs, byte-exact):

| axis | ok | not_applicable | hard abort (SIGABRT) |
|---|---|---|---|
| sampled | 136 | 0 | 2 |
| filtered | 136 | 0 | 2 |
| storage_read | 136 | 0 | 2 |
| storage_write | 136 | 0 | 2 |
| atomic | 21 | 116 | 1 |
| linear | 55 | 83 | 0 |
| renderable | 55 | 0 | 83 |
| blendable | 36 | 0 | 102 |
| msaa | 55 | 0 | 83 |
| resolve | 55 | 0 | 83 |
| depth_stencil | 5 | 131 | 2 |

Every non-`ok` cell is fully explained by one of four structural rules
(verified to **zero mismatches** against a full 1518-cell precheck before
capture, `provenance/pre_freeze/precheck/`):

1. **`Depth24Unorm_Stencil8` (id 255) and `X24_Stencil8` (id 262) are not
   valid `MTLPixelFormat` values on this device at all** — bare
   `newTextureWithDescriptor:` aborts ("MTLTextureDescriptor has invalid
   pixelFormat (N)") before any usage-specific check. Corroborates the
   prior EXP-M4-08 finding (`docs/descriptors/format-table.md`:
   "Unsupported on this HW (Metal rejects): depth24unorm_stencil8,
   x24_stencil8"), with a new mechanism-level detail (bare descriptor
   validation, not render-pipeline validation, is where it fires).
2. **83 formats — every compressed family (BC/PVRTC/ETC2/EAC/ASTC-LDR/
   ASTC-sRGB/ASTC-HDR), both YUV 4:2:2 formats, and every depth/stencil/
   depth-stencil/stencil-view format — abort on `renderable`/`msaa`/
   `resolve`** ("is not color renderable").
3. **19 additional integer-kind (`uint`/`int`) formats abort on
   `blendable` only** (still `ok` on `renderable`) — Metal's documented
   "integer formats are not blendable" restriction, now hardware-confirmed
   as an unconditional abort, not a soft capability flag.
4. **`atomic` and `linear` are gated in the harness itself** before
   touching Metal at all (non-integer kind → `atomic` is
   `not_applicable`; family in the empirically-derived
   `family_linear_ineligible` set → `linear` is `not_applicable`), which is
   why the two device-unsupported formats do NOT abort on those two axes
   specifically (21/22 device-touching integer-kind formats succeed on
   `atomic`; only `X24_Stencil8`, which IS integer-kind, aborts).

No format aborts for any reason outside these four rules.

## Divergences from Metal's advertised/assumed capabilities

Per the row's explicit instruction ("Metal's own feature-table claims are
NOT evidence — verify each on hardware and note every divergence"):

1. **Render/blend/MSAA/resolve/depth-stencil-attachment eligibility is
   enforced as an unconditional host-side `abort()`, not a soft runtime
   capability query.** There is no public API to ask "is format X
   renderable" without either already knowing the answer or crashing the
   process. A driver must carry a static allowlist; it cannot safely probe.
2. **`Depth24Unorm_Stencil8`/`X24_Stencil8` are declared in the public
   header with `API_AVAILABLE(macos(10.11)...)`/`API_AVAILABLE(macos(10.12)
   ...)` annotations implying general availability, but are rejected
   outright on this Apple Silicon GPU** — a real divergence between
   "documented as available" and "actually supported," reproducing and
   sharpening the EXP-M4-08 finding.
3. **`X32_Stencil8` needs NO texture view to serve as a direct
   `stencilAttachmentPixelFormat`** — it completes cleanly
   (`command_buffer_status=4`) used directly, once correctly typed as
   `uint`. (An earlier iteration of this contract wrongly predicted it
   would need a view, based on its "view format" framing; the corrected
   precheck refuted that — see `PRE_REGISTRATION.md` F3/F4 and
   `provenance/quarantined_attempt2/NOTE.md`.)
4. **`BGR10_XR`/`BGRA10_XR` (extended-range formats, typically documented
   for camera/display-colorspace use) are fully general-purpose textures
   on this hardware**: `sampled`/`filtered`/`storage_read`/
   `storage_write`/`renderable`/`blendable`/`msaa`/`resolve`/`linear` are
   all `ok` — broader capability than their narrow documented use case
   suggests. (`atomic`/`depth_stencil` are `not_applicable`, correctly,
   since `xr` is a float-kind, non-depth-stencil family.)
5. **Every compressed-family format (all 76 BC/PVRTC/ETC2/EAC/ASTC/YUV422
   formats) accepts `storage_read` AND `storage_write`** — texture
   creation with `MTLTextureUsageShaderRead`/`ShaderWrite` and a
   `texture2d<float, access::read/write>` compute bind both succeed
   (command buffer completes, status 4), for every single one, both runs,
   byte-exact. This is NOT what Metal's public documentation describes
   (compressed formats are documented as sample/gather-only, no direct
   image load/store). **Caveat, explicitly disclosed**: the capability
   sweep does not upload or verify content for compressed formats (no
   pattern upload, no CPU readback attempted — see `axisReadWrite`'s
   compressed-family exclusion in `harness/probe.m`), so this establishes
   *construction and dispatch are accepted*, not that the read/written
   bytes are well-defined, block-encoding-aware, or useful. This is a
   first-class capability-envelope finding (`docs/hypotheses.md`-class)
   that the next increment should follow up with content verification.
6. **`PVRTC_*` (all 8 formats, deprecated in the public header) behave
   identically to every other compressed family** — texture creation,
   sampling, and storage read/write all succeed; only the render-pipeline
   axes reject them (same as every other compressed family). PVRTC is
   *not* rejected outright on this Apple Silicon GPU, contrary to a
   plausible assumption given it originates from PowerVR hardware Apple
   Silicon does not use.
7. **Every non-device-unsupported integer-kind format (21/22: all
   `*Uint`/`*Sint`, `Stencil8`, `X32_Stencil8`) supports `texture2d<uint/
   int, access::read_write>::atomic_fetch_add`**, not merely `R32Uint` —
   broader native texture-atomic support than prior work
   (`EXP-0085`/`EXP-0095`, which established `texture_buffer`/argument-
   buffer atomics) had directly established for `texture2d`.
8. **Integer-format linear filtering is NOT rejected at any stage**
   (`conv_int_filter_r32uint`): sampler creation, pipeline creation, and
   dispatch all succeed for an `R32Uint` texture bound with
   `minFilter=linear`. Metal's documented restriction against filtering
   integer formats is not enforced as a hard error on this path.
   **Caveat**: the probed texture was freshly allocated (zero content), so
   this establishes *no rejection occurs*, not what value the "filtered"
   read actually returns for non-uniform content (nearest-fallback vs.
   fabricated interpolation) — left `UNKNOWN`, named as successor work.
9. **Sparse residency succeeds for every one of the 5 representative
   formats tested**, including a compressed format (`BC1_RGBA`), an ASTC
   format (`ASTC_4x4_LDR`), and a depth format (`Depth32Float`) — sparse
   heap creation and sparse-heap texture creation both complete. `device
   sparseTileSizeInBytes = 16384` uniformly. Full per-format sparse
   semantics (page tables, mip tails, residency management) remain
   DRV-ROBUST-01's (P1.5) scope.

## Extended conversion rules (H1–H6; extends EXP-0079's three rules)

All values below are byte-exact identical across both runs.

**H1 — snorm16 encode scale is symmetric (CONFIRMS the extension of
EXP-0079's snorm8 finding).** `r16snorm_m100` (input −1.0) stores physical
`0x8001` (−32767), NOT the asymmetric `0x8000`; typed read decodes back to
exactly −1.0. `r16snorm_p100` (+1.0) stores `0x7FFF` (32767), the shared
control point. `round(clamp(c,−1,1) × 32767)` holds at 16-bit exactly as at
8-bit.

**H2 — unorm16 tie-breaking is round-half-DOWN, the OPPOSITE convention
from unorm8's round-half-up (EXP-0079). NEW finding, falsifies the
extended-textbook H2 hypothesis registered for this run.**

| case | input | floor parity | registered expectation (round-half-up) | observed | verdict |
|---|---|---|---|---|---|
| `r16unorm_sep_a` | 1.5/65535 | odd | 2 | **1** | deviation |
| `r16unorm_sep_b` | 2.5/65535 | even | 3 | **2** | deviation |
| `r16unorm_nontie` | 5.9/65535 (control, not a tie) | — | 6 | 6 | match |

Both exact-tie probes round DOWN to the lower integer (`1.5→1`, `2.5→2`),
which neither round-half-up nor round-half-even predicts (round-half-even
would also give `2` for the even-floor case but `2` — not `1` — for the
odd-floor case; only round-half-DOWN is consistent with both). The non-tie
control (5.9 → 6, not floor'd to 5) independently refutes simple
truncation. `rgba16unorm_sep` cross-checks both probes inside one 4-channel
store: R channel (2.5/65535, discriminator) → `0x0002`, G channel
(1.5/65535, control) → `0x0001` — identical to the standalone cases,
confirming the rule is not an R8Unorm-vs-R16Unorm-specific artifact of a
single-channel store. **Driver takeaway: normalized-integer encode
tie-breaking is NOT uniform across bit widths on this hardware** — 8-bit
rounds ties up, 16-bit rounds ties down. A driver cannot assume one
tie-break rule generalizes across `Unorm` widths.

**H3 — sRGB storage applies the standard IEC 61966-2-1 encode curve on
compute `access::write`, CONFIRMED bit-exact on encode.**

| case | input (linear) | predicted encoded byte | observed physical byte | decoded (typed read) | reference decode |
|---|---|---|---|---|---|
| `srgb8_low` | 0.0031308 (curve knee) | `0x0a` | `0x0a` | 0.0029304 | 0.0030353 |
| `srgb8_mid` | 0.5 | `0xbc` | `0xbc` | 0.5028083 | 0.5028865 |
| `srgb8_high` | 0.95 | `0xf9` | `0xf9` | 0.9472528 | 0.9473065 |

Encode is bit-exact to the reference `round(srgb_encode(c) × 255)` formula
for all three probes — refutes a "compute writes bypass sRGB encoding"
hypothesis; the encode curve applies even off the fragment/blend path.
Typed-read decode lands close to (within ~0.03–0.1% relative) but not
bit-exact to the reference decode formula — consistent with a
hardware/fixed-function sRGB decode implemented as a polynomial
approximation rather than the exact reference curve. Whether it is an exact
known approximation (and to what error bound generally) is left `UNKNOWN`
— named successor work, not asserted.

**H4 — integer-format linear filtering is accepted, not statically
rejected.** See divergence #8 above; `conv_int_filter_r32uint` completes
(`command_buffer_status=4`) with no pipeline/sampler rejection.

**H5 — BC1 decode of an authored, self-encoded solid-color block round-trips
correctly (own-encoder, public S3TC/DXT1 spec, no Apple artifact copied).**
`bc1_white_opaque` (`color0=0xFFFF`, index=0 everywhere) decodes to exactly
`(1.0,1.0,1.0,1.0)`. `bc1_red565_opaque` (`color0=0xF800`) decodes to
exactly `(1.0,0.0,0.0,1.0)`. Both saturate their 5/6-bit channels fully, so
(as pre-registered) the two candidate 565→8-bit expansion formulas
(bit-replication vs. linear-round) coincide and are **not discriminated by
this probe** — named explicitly unexercised.

**H6 — Depth32Float_Stencil8's depth and stencil aspects are independently
addressable with zero cross-contamination, CONFIRMED.** One draw writes
depth=0.3 (via `depthCompareFunction=less`, clear=0.8) and stencil=0x5A
(via `stencilCompareFunction=always`, `replace`) to the same combined
texture. Direct `depth2d<float>` bind of the combined texture reads back
`0.30000001192092896` (exact fp32 `0.3`, `0x3E99999A`); a texture view with
`pixelFormat=X32_Stencil8` bound as `texture2d<uint>` reads back `0x5A`
exactly. Neither aspect observes the other's value.

## RGB32 and PVRTC (row-mandated questions)

**RGB32: re-confirmed absent.** `analysis/gen_formats.py`'s independent
header parse finds no `MTLPixelFormatRGB32*` constant among the 138
formats (the `R32`/`RG32`/`RGBA32` triplets exist; no `RGB32` gap-filler) —
corroborates EXP-0095's finding (`RGB32 texel buffers have no native
representation`) via a second, independent method (full enum enumeration
vs. EXP-0095's texel-buffer probing).

**PVRTC: present in the enum (8 formats, deprecated), NOT rejected on this
Apple Silicon GPU.** See divergence #6 above — full capability parity with
every other compressed family (creation/sample/storage-read/storage-write
all `ok`; render-pipeline axes rejected identically to BC/ETC2/ASTC). A
clean, positive, hardware-verified answer, not an assumption from the
deprecation notice.

## Layout (public-API-observable alignment/pitch surface)

| format | bpp | `minimumLinearTextureAlignment` | `minimumTextureBufferAlignment` | accepts bytesPerRow at aligned minimum |
|---|---|---|---|---|
| R8Unorm | 1 | 16 | 16 | yes (16) |
| RG8Unorm | 2 | 16 | 16 | yes (32) |
| RGBA8Unorm | 4 | 16 | 16 | yes (64) |
| RGBA16Float | 8 | 16 | 16 | yes (128) |
| RGBA32Float | 16 | 16 | 16 | yes (256) |
| BGR10_XR | 4 | 16 | 16 | yes (64) |
| BC1_RGBA | — | N/A (family excluded pre-call) | N/A | N/A |
| ASTC_4x4_LDR | — | N/A | N/A | N/A |
| Depth32Float | — | N/A | N/A | N/A |
| Stencil8 | — | N/A | N/A | N/A |
| GBGR422 | — | N/A | N/A | N/A |

`minimumLinearTextureAlignment` is a **uniform 16 bytes** across every
tested bpp class (1/2/4/8/16) and XR — the alignment is a fixed granularity
requirement, not bpp-scaled, on this hardware; actual `bytesPerRow` must
still be `>= width*bpp` (rounded up to that 16-byte granularity) — using
the alignment value alone as `bytesPerRow` for a wide format
(`RGBA8Unorm`, needs 64) triggers a hard Metal validation abort ("must be
>= 64 bytes"), confirmed once dedicated (`layout_below_minimum`, expected
abort, observed abort both runs). Compressed/depth/stencil/YUV422 formats
reject `minimumLinearTextureAlignmentForPixelFormat:` itself with a hard
abort (not the catchable exception its own header doc implies) — the
"linear" capability axis and this layout table both correctly treat that
family set as `N/A` without ever calling the API for them.

This is the **public-API-observable** alignment surface only. It does not
re-derive the internal tiled/twiddled layout model (`docs/tiling/README.md`
— bpp1 tile edge 128, already HW-validated via DATA-TRACE by EXP-M4-04..08,
cited not repeated). Mip offsets inside Metal's opaque/tiled storage are
not observable through any public API call (`getBytes` always returns
whatever Metal's internal layout decodes to); this experiment makes no
mip-offset claim.

## Sparse (bounded representative subset — 5/138 formats)

All 5 succeed: heap creation (`MTLHeapTypeSparse`) + sparse-heap texture
creation both complete for `RGBA8Unorm`, `R32Uint`, `BC1_RGBA`,
`ASTC_4x4_LDR`, `Depth32Float`. `sparseTileSizeInBytes = 16384` uniformly.
**133/138 formats explicitly NOT exercised on this axis** — DRV-ROBUST-01
(P1.5) owns full per-format sparse residency semantics (page tables, mip
tails, aliasing, residency return); this experiment only answers "does
sparse participation work at all," for a representative cross-section.

## Explicitly unexercised cells (named up front, not discovered after the fact)

- **Bit-exact conversion verification for compressed formats beyond the two
  BC1 solid-color probes**: no ASTC/ETC2/EAC/BC2-7/BC6H/PVRTC decode oracle
  is constructed; the capability sweep's `sampled`/`storage_read`/
  `storage_write` "ok" results for these 76 formats are construction-and-
  dispatch-only, not content-verified.
- **The two candidate 565→8-bit channel-expansion formulas for BC1** (and
  by extension every other compressed format's exact decode arithmetic)
  remain undiscriminated — H5's probes saturate both channels, which
  coincidentally satisfies both formulas.
- **sRGB decode's exact curve/approximation identity** (H3): observed close
  but not bit-exact to the reference formula; not characterized further.
- **Integer-filtering's actual interpolation behavior for non-uniform
  content** (H4): only "not rejected" is established; whether it behaves as
  nearest or produces fabricated interpolated integers is `UNKNOWN`.
- **Sparse residency for 133/138 formats**, and all sparse semantics beyond
  "creation succeeds" (page tables, mip tails, residency return,
  aliasing) — DRV-ROBUST-01's scope.
- **Native/PBE-descriptor-level layout** — owned by prior EXP-M4-* DATA-
  TRACE work (`docs/tiling/README.md`), cited not repeated; this
  experiment's LAYOUT section is public-API-alignment-only.
- **Mip levels beyond level 0, array layers, cube faces, 1D/3D
  dimensionality** for every axis — this experiment is 2D-level-0-only
  throughout, matching EXP-0070/79/95's established scope. (`EXP-0132`,
  landed during this experiment's run, separately establishes that an
  invalid `slice` silently and destructively zeroes slice 0 while an
  invalid `level` is a silent no-op, and that depth/stencil reuse the color
  MRT k-array at `k=ncolor`/`k=ncolor+1` — cited here as the authoritative
  answer for slice/level/MRT-index questions this experiment does not
  itself probe.)
- **Compression/lossless-encoding interaction.** `EXP-0134`, also landed
  during this experiment's run, establishes that `ShaderWrite` and
  `PixelFormatView` usage flags each INDEPENDENTLY disable lossless
  compression. This experiment's capability sweep uses `ShaderWrite`
  liberally (every `storage_write`/`atomic` cell) and `PixelFormatView` in
  the `split_depth_stencil` conversion case; per EXP-0134, none of the
  textures this experiment created were compression-eligible in the first
  place, so this experiment's results are not confounded by compression
  state — but it also means this experiment says nothing about the
  *compressed* codepath's capability envelope, which remains open.
- **A18/G17P replication** — M4-only, per standing target discipline.
- **Renderable/blendable/depth_stencil/msaa/resolve content verification**
  — every `ok` in those five axes is command-buffer-completion-only; no
  attachment content was read back or checked for any of the 138 formats
  (the render-axis harness intentionally omits readback to keep each
  process minimal and safe against the hard-abort classes).

## What P1.2 (DRV-FMT-01) still needs

Combining EXP-0070 + EXP-0079 + this experiment: the full 138-format
capability breadth is now established (11 axes × 138 formats, this
experiment), and conversion rules are established for 14 formats at the
compute-store path (EXP-0079) + 6 at the fragment-store path (EXP-0070) +
this experiment's extensions (16-bit normalized, sRGB, one compressed
family, split depth/stencil, integer filtering). Still open for full
DRV-FMT-01 closure:

- Bit-exact conversion rules for the 76 compressed-family formats beyond
  BC1's two solid-color probes (a real per-format-family effort: BC2-7,
  ETC2/EAC, ASTC block modes each need their own authored encoder/decoder
  oracle).
- Swizzle and pack/unpack behavior beyond what `docs/descriptors/
  format-table.md` §3 already established (channel-arrangement/numtype
  orthogonality) — not re-probed here.
- Content verification for the render/blend/MSAA/resolve/storage axes
  (this experiment is capability-only for those five axes across the full
  matrix).
- Full sparse-residency semantics (DRV-ROBUST-01, P1.5, a separate row).
- A18/G17P confirmation (deferred, hands-off per standing directive).

## Clean-room provenance

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC (Metal SDK header
`MTLPixelFormat.h`, read only for public enum identifiers, never
disassembled/inspected as a binary; BC1's block layout is a public
S3TC/DXT specification, independently encoded, never copied from any Apple
artifact)
Inputs inspected: authored MSL (`kernels/capability.metal`,
`kernels/conversion.metal`), authored Obj-C harness (`harness/probe.m`),
authored Python orchestration/verification, the public Metal SDK header
(read-only), EXP-0079/EXP-0095/EXP-M4-08's disclosed prior findings (cited
as established facts, never copied as unverified new-experiment evidence)
Apple binary introspection: NONE
Reproduction: `python3 -B verify.py --captured`; `python3 -B
analysis/repeat_check_corrected.py`; full re-capture requires a new
successor experiment number per `CODEX.md` (never repair/rerun in place)
Evidence: `raw/m4-20260828-run07/`, `raw/m4-20260828-run08/` (1548 case
files + 3 top-level files each, append-only), `analysis.json`,
`analysis/repeat_check_corrected.json`, `manifest.json`, `PROGRESS.md`,
three retained quarantined attempts under `provenance/`, and the 138×11
pre-check at `provenance/pre_freeze/precheck/`

Evidence label: **HW-VALIDATED** for every capability-axis support/failure
determination and every conversion-rule byte value (independently
generated MSL/Obj-C, executed on real hardware, byte-exact repeat across
two independently-captured runs, pre-registered hypotheses with named
falsifiers per `CODEX.md`'s evidence ladder) — **STRUCTURAL** for the
capability sweep's informational output content where explicitly disclosed
unverified (compressed-format storage read/write content; render/blend/
MSAA/resolve attachment content).
