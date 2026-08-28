# EXP-0109 Results — M4 VS/FS/CS stage ABI (DRV-ABI-01 / P0.8)

**Target: Apple M4/G16G, local host only.** macOS 26.6.2 (25G82), Metal 4 (Apple9),
Apple clang 21.0.0, `xcrun` 72, Python 3.14.6. **A18 Pro: no data collected here**
(hands-off per `CLAUDE.md`); every A18 fact cited below is prior art
(EXP-0031/EXP-0029/EXP-0035, all pre-dating the M4-only directive), explicitly labeled
as such, never silently promoted. M5: not touched.

**Two official captures**, `raw/m4-20260828-run01/` and `raw/m4-20260828-run02/`, 57
cases each (56 `OK` + 1 deliberate negative-control `FAIL`), each a fully separate
`run.py` process invocation. `python3 verify.py --crossrun raw/m4-20260828-run01
raw/m4-20260828-run02` → **57/57 byte-identical, 0 mismatches.** Zero faults, zero
`CMDBUF_ERROR`, zero hangs, zero host instability anywhere in this experiment.

---

## Standing-gate results

| Gate | Result |
|---|---|
| `--selftest` | **9/9 PASS** (runs with zero `raw/` captures present; also re-run and still passing after both official captures) |
| `--seqtest` | **3/3 PASS** — `PRE_GPU → RUN01_PRESENT → RUN02_PRESENT` all correctly detected; `crossrun` correctly unrunnable in `PRE_GPU`, correctly runnable and PASS-capable in `RUN02_PRESENT` |
| Non-recorded smoke gate | `run.py --smoke-only` (writes to `work/`, never `raw/`) — one real structural case + one real HW-PROBE case, both `OK`, run **before** either official capture (`work/smoke_pre1/`) |
| No-nondeterministic-field | `run.py`'s `check_no_nondet()` statically forbids `{duration_ms, pid, timestamp, started_utc, address, elapsed}` inside any case's `gated` record (recursively); all timing/process metadata lives in the separate, uncompared `meta` field. Enforced at capture time, not just post hoc. |
| Fixtures from recorded reality | `harness/fixtures/recorded_reality.json` — 6 records built from real M4 GPU/compiler calls during harness development (`run.py`'s own `BACKEND_FN` dispatch), used by `--selftest` |
| Cross-run byte-exact gate | **57/57 PASS**, 0 mismatches |

Other CODEX/SUBAGENT_BRIEF discipline actually followed: append+`fsync` after every
case record (`run.py`); `PROGRESS.md` per milestone; a full 57-case dry run into
`work/dryrun1/` (never `raw/`) before spending either official run id; one process per
case (each backend invocation is its own `subprocess.run`); hard 30s per-case / 60s
per-build timeouts; one authored source file per family, one CLI-driven parameter
varied per case; `raw/` run-directory creation refuses to overwrite/reuse an existing
dir; `CAPTURE_CONTRACT.json` pins authored-file sha256 hashes (not live `HEAD`) at
state `PRE_GPU`, then is updated to `RUN02_PRESENT` after capture — `git_revision_at_registration`
(`0f1af7f...`) differs from `PRE_REGISTRATION.md`'s freeze-time revision
(`75eb840a...`) purely because the orchestrator committed sibling experiments in
between, per the pinned-revision rule (SUBAGENT_BRIEF, post-EXP-0082) — not a gate
failure.

---

## TL;DR — what a compiler backend must emit, per stage

1. **VS fetch**: still in-shader software fetch on M4 (extends EXP-0031's A18 finding).
   Every tested format category (float/half/int/uint/normalized/packed) produces
   distinct compiled bytes from the same attribute slot; stride/offset/step/divisor
   each independently move the compiled bytes. **Out-of-range fetch reads back exactly
   zero** — HW-VALIDATED, extends EXP-0076's generic buffer-robustness model to the
   VS's own generated `device_load`.
2. **FS input**: all 7 interpolation-qualifier spellings compile to 7 byte-distinct
   fragment programs on M4 (extends EXP-0029 A18→M4); pull-model calls compile
   **byte-identically** to the matching qualifier (exact match, 3/3 tested pairs).
   Barycentric coordinates are a real, device-gated capability
   (`supportsShaderBarycentricCoordinates=true` on this M4) and compile cleanly.
   `primitive_id` compiles to the shortest fragment program tested (82 bytes).
   `front_facing` correctly reports CCW=front/CW=back on M4 in a real render
   (HW-VALIDATED).
3. **FS output**: MRT scales cleanly to 4 targets with independently-addressable,
   correctly-computed per-target values (HW-VALIDATED, exact arithmetic match).
   Dual-source blending is real and HW-VALIDATED, but the correct mental model is the
   standard one — `index(1)` is consumed **as a blend factor multiplying `index(0)`'s
   color**, not as an alternative source color; see §3.2 for the corrected derivation.
   Explicit depth output (`any`/`less`/`greater`) genuinely overrides the built-in
   rasterizer depth (HW-VALIDATED, 4/4 cases exact). **Fragment stencil output
   (`[[stencil]]`) is a real MSL attribute** — contrary to this experiment's own
   pre-registered working hypothesis — and a shader-supplied stencil value genuinely
   overrides the fixed-function `stencilReferenceValue` in a real stencil attachment
   (HW-VALIDATED, clean paired positive/negative control).
4. **CS**: dynamic threadgroup-memory capacity (`setThreadgroupMemoryLength:atIndex:`)
   is a genuine dispatch-time parameter against ONE compiled pipeline — correct
   wraparound at every tested size 1..64, no recompilation (HW-VALIDATED). The
   preamble (`_agc.main.constant_program`) is present regardless of whether the kernel
   binds a `constant`-address-space argument (extends EXP-0020 A18→M4).
5. **Linkage**: Metal's own compiler never produces a third, separately-addressed code
   segment for attribute fetch, interpolation setup, or any fragment-output family
   tested — every render/compute pipeline structurally reports exactly
   `["_agc.main.constant_program", "_agc.main"]`, confirmed across 10 spot-checked
   cases spanning both stages. The CALL/RETURN opcode family (`byte0` low-nibble
   `0xf`) EXP-0035 documented on A18 is present in M4-compiled code for a `noinline`
   function call (structural cross-check, not a full byte-level re-decode).

---

## §1 VS fetch ABI

### 1.1 Format matrix (structural, `vfetch_extract`, OWN-SHADER-DIFF)

7 formats tested at a single attribute slot (`offset=0, stride=32, stepFunction=perVertex`),
each paired with the MSL field-type category the format requires (public
`MTLVertexFormat` enum values, read from the public Metal SDK header, not any binary):

| format | MSL field type | compiled VS length (bytes) | byte-identical to Float4 baseline? |
|---|---|---:|---|
| Float4 (31) | `float4` | 234 | — (baseline) |
| Half4 (27) | `half4` | 230 | No |
| UChar4Normalized (9) | `float4` | 250 | No |
| Short4Normalized (24) | `float4` | 250 | No |
| Int4 (35) | `int4` | 232 | No |
| UInt4 (39) | `uint4` | 232 | No |
| Int1010102Normalized (40) | `float4` | 378 | No |

**OBSERVED.** All 7 formats produce mutually distinct compiled VS bytes from the same
`[[stage_in]]` slot; UChar4Normalized/Short4Normalized (both need an integer-load +
normalize-to-float sequence) land at the same length (250) but are not necessarily
identical byte-for-byte (not separately diffed — both are "normalized 4-component small
integer," a plausible shared-length coincidence, flagged as unconfirmed-identical, not
asserted so). The packed Int1010102Normalized format is substantially longer (378 vs.
234 baseline) — consistent with needing three independent bitfield extractions (10/10/10
bits) plus a 2-bit alpha extraction and four separate normalize operations, each firing
from a single packed 32-bit load.

**INTERPRETED.** H1 holds for all 7 tested format categories on M4: attribute fetch
remains in-shader software (Metal lowers the `MTLVertexDescriptor` into per-format
load-and-convert code baked into the VS), extending EXP-0031's A18-only finding.
**Driver consequence**: a compiler backend must synthesize format-specific fetch code
per attribute (as Asahi Mesa already does for M1/M2), not rely on a fixed-function
fetch unit; the exact per-format load-width/shift/normalize sequence is not re-decoded
bit-for-bit here (that is DRV-ISA-01/opcode-census territory) — this experiment
establishes *that* the code differs and *how much* it differs (length), not the
bit-level encoding of every format's convert sequence.

### 1.2 Layout (stride/offset/step/divisor) — structural, all pairs byte-DIFFERENT

| pair | lengths | byte-identical? |
|---|---|---|
| stride 32 vs 64 | 234 / 234 | **No** (same length, different bytes — consistent with an immediate-only change, e.g. EXP-0031's A18 `imad` stride immediate) |
| offset 0 vs 16 | 234 / 234 | **No** (same length, different bytes) |
| step vertex vs instance | 234 / 230 | **No** (also a length change — the index-source SR selector differs) |
| instance stepRate 1 vs 2 | 230 / 256 | **No** (rate=2 is 26 bytes LONGER — consistent with an added divide-by-rate operation) |

**INTERPRETED.** H2 holds: every layout knob independently and measurably changes the
compiled VS. The step-rate (instance-divisor) delta (+26 bytes) is new information
beyond EXP-0031 (which tested only rate=1 perInstance); it is consistent with a real
compiled division, i.e. **a nonzero step rate is not free — it costs extra ALU in the
fetch prologue**, a fact a compiler's cost model should account for.

### 1.3 Value delivery + out-of-range fetch — HW-PROBE, HW-VALIDATED

Method: `rasterizationEnabled = NO` vertex-only pipeline (`v_fetch_probe`,
`kernels/mrt_interp.metal`), one atomic-indexed SSBO record per invocation (mirrors
EXP-0092's `agxvdraw.m` order-independent-append pattern), `MTLVertexFormat
UChar4Normalized` at a tightly-packed 4-byte stride, real `drawIndexedPrimitives:`.

| case | setup | observed |
|---|---|---|
| `vsfetch_hw_inrange` | 6 in-range indices, `nvert=6` | every `attr` == `(i/255, i/255, i/255, 1.0)` **exactly** for `i=0..5` |
| `vsfetch_hw_oob` | 6 in-range + 1 index = `nvert+50` (56, buffer holds 6 elements) | in-range records exact as above; the OOB record reads `attr=(0,0,0,0)`, `vid=56` |
| `vsfetch_hw_instancing_base` | `nvert=4, ninst=3, baseVertex=2, baseInstance=10`, indices `0..3` | `vid = index+baseVertex` (2..5), `iid = ordinal+baseInstance` (10,11,12); `vid∈{2,3}` (in range) read exact values; `vid∈{4,5}` (base-shifted OUT of the 4-element buffer) read `(0,0,0,0)` — **the fetch address is computed from `vertex_id` (already base-inclusive), not the raw index** |
| `vsfetch_hw_oob_large_base` | `nvert=4, baseVertex=1000000`, one OOB index | all 5 records (`vid` 1000000..1000003, 1000054) read `(0,0,0,0)` — a huge base offset does not fault, crash, or wrap; it simply puts every fetch address far outside the 16-byte buffer, and every one reads zero |

**OBSERVED, exactly, both runs byte-identical:** in-range fetches are exact; every
out-of-range fetch (small OOB, base-shifted OOB, huge-base OOB) reads back precisely
zero, with zero faults across all 4 cases. **INTERPRETED**: H3 holds — this generalizes
EXP-0076's owned-buffer robustness model (independent naturally-aligned units, per-unit
align-down addressing, OOB reads zero / stores discarded) to the VS's own
compiler-generated attribute-fetch `device_load`, which was not previously
independently confirmed (EXP-0076 tested SSBO/storage-buffer access broadly, not
specifically the VS fetch prologue). This is `HW-VALIDATED`, not merely inferred by
analogy — the exact mechanism (compute-then-load, not clamp-then-load) also falls out
of the `vsfetch_hw_instancing_base` case: the base offset is folded into `vertex_id`
*before* the address computation, and the OOB read policy applies uniformly regardless
of whether the OOB-ness comes from the raw index or from `baseVertex`.
**Driver consequence**: no additional bounds-checking is required in generated VS
fetch code for an out-of-range vertex/instance index under the current UAPI's buffer
model — the hardware/driver memory model already returns zero, matching what a
robustness-buffer-class API (e.g. `VK_EXT_robustness2`'s "return zero") would want.

---

## §2 FS input ABI

### 2.1 Interpolation qualifiers — structural + M4 confirmation of EXP-0029 (A18)

| qualifier | compiled length (bytes) |
|---|---:|
| `flat` | 98 |
| default no-perspective (`center_no_perspective`) | 114 |
| `centroid_no_perspective` | 130 |
| `sample_no_perspective` | 132 |
| default perspective (implicit) | 166 |
| `centroid_perspective` | 182 |
| `sample_perspective` | 184 |

**OBSERVED.** All 7 spellings compile cleanly on M4; all 7 are byte-distinct (7/7
distinct, confirmed via `analysis/decode.py`); `flat` is shortest (matches EXP-0029's
A18 finding that `flat` is a distinct, shorter `iter_flat` op with no barycentric
setup); no-perspective variants are shorter than their perspective counterparts (matches
EXP-0029's "perspective adds a W-denominator `iter` + reciprocal + multiply" finding);
centroid/sample variants are longer than the corresponding center/default variant
(matches EXP-0029's "centroid/sample add an `iter_at` setup op" finding).
**INTERPRETED**: EXP-0029's A18 interpolation-lowering model reproduces structurally on
M4 for all 7 qualifier forms (this experiment's own M4-native confirmation, not a
byte-identical A18↔M4 claim — the exact byte contents were not cross-compared against
an A18 capture, only the shape/ordering of the length relationships, which is
consistent with `docs/m4-deltas.md`'s "shader ISA IDENTICAL" finding).

### 2.2 Pull-model interpolation — exact byte match to the qualifier form (M4, new)

`interpolate_at_center()`/`_centroid()`/`_sample()` on an `interpolant<float4,
interpolation::perspective>` `[[stage_in]]` member compile **byte-for-byte identical**
to the corresponding `[[*_perspective]]`-qualified plain member, for all 3 tested pairs
(center/centroid/sample). `interpolate_at_offset()` is a distinct, much longer lowering
(478 bytes vs. 166–184 for the others) — a custom-offset barycentric computation, not a
fixed qualifier form. **This exactly reproduces EXP-0029's A18 claim on M4**, now with
an actual byte-exact diff (not just "no diff reported") backing it.

### 2.3 Barycentric coordinates — capability confirmed present

`MTLDevice.supportsShaderBarycentricCoordinates` (public property) reads `true` on this
M4; a fragment function declaring `float3 b [[barycentric_coord]]` alongside an
ordinary `[[stage_in]]` struct compiles cleanly (224 bytes). **Not HW-PROBE-validated**
(no pixel-level readback of the barycentric values themselves was performed — flagged
as an open item). **Driver consequence**: `SPV_KHR_fragment_shader_barycentric`-class
functionality has a native MSL/hardware path available on Apple9; no software emulation
via manual position-based interpolation is required at the ABI-presence level (semantic
correctness of the returned weights is unverified here).

### 2.4 `primitive_id` — structural presence, shortest fragment program tested

`fragment float4 f_primid(VOut in [[stage_in]], uint pid [[primitive_id]])` compiles to
82 bytes — the shortest of any fragment program in this matrix, consistent with
EXP-0029's A18 characterization of `primitive_id` as a flat tiler-output load rather
than an interpolation-datapath read. **Per-fragment value correctness was not
HW-PROBE-tested here** (flagged open item — the earlier plan to add an SSBO-append
per-fragment readback was dropped for time; structural presence + plausible length is
the evidence this experiment delivers).

### 2.5 `front_facing` — HW-VALIDATED on M4

Real render, two disjoint triangles (CCW at instance 0, CW at instance 1, identical
non-culling pipeline), readback of `front_facing`-encoded color: CCW triangle reads
`255` (front, red channel), CW triangle reads `0` (back). **Exact, both runs
byte-identical.** This is the same CCW=front convention EXP-0031 established on A18 via
`get_sr 0xc5`; this experiment confirms the *behavior* on M4 at the public-API level
(does not re-confirm the exact SR number on M4 — that remains an A18-only fact per
EXP-0031, `INFERRED`-by-family for M4 per `docs/m4-deltas.md`'s ISA-identity finding,
not independently re-spliced here).

---

## §3 FS output ABI

### 3.1 Multiple render targets — HW-VALIDATED, exact arithmetic

Real renders with `f_mrt1`/`f_mrt2`/`f_mrt4` (1/2/4 `RGBA16Float` attachments),
half-float readback decoded in `analysis/decode.py`:

- `MRT1` attachment 0 == `MRT4` attachment 0, exactly (both runs, both encodings).
- `MRT2` attachments {0,1} == `MRT4` attachments {0,1}, exactly.
- `MRT4` attachment 2 == attachment 0 × 0.5, attachment 3 == attachment 1 × 0.5, exactly
  (both within float16 rounding, checked to <0.01 absolute tolerance — the shader
  computes `c2 = c0*0.5`, `c3 = c1*0.5`).

**INTERPRETED**: MRT scales cleanly from 1 to 4 targets with independently-addressed,
independently-correct per-target values, and adding more targets does not perturb the
values already being written to lower-indexed targets — a clean, load-bearing
confirmation (not merely "it compiles," but "the values that land in each attachment
are exactly the values the shader computed for that attachment").

### 3.2 Dual-source blend — HW-VALIDATED, but the naive model is WRONG (corrected)

**Pre-registered hypothesis (H7)** was that, with `sourceRGBBlendFactor =
Source1Color, destinationRGBBlendFactor = Zero`, the rendered pixel would equal the
shader's `index(1)` output directly. **The official capture's raw observation refutes
that literal claim**: `dualsource_hw`'s readback (decoded: `[0.202, 0.161, 0.072,
0.5]`) does **not** equal `c1` (`index(1)`'s value, `[0.281, 0.797, 0.921, 0.5]`) at
the same screen position (cross-checked against the `mrt_hw_4` case's `c0`/`c1`, same
vertex shader `v_common`, same geometry, same sampled pixel).

**Root-cause investigation** (one supplementary, single-run, **non-frozen** ad hoc
probe, `work/supplementary/render_probe_src0test.m` — a one-line blend-factor edit of
the frozen `render_probe.m`, run once, explicitly outside the two-run gate, mirroring
EXP-0091's `d_helper_relay` precedent for a post-hoc gap-closing single probe): with
`sourceRGBBlendFactor = SourceColor` (i.e. `index(0)` referencing itself as the blend
*factor*), the readback decodes to `[0.517, 0.041, 0.0062, 1.0]`. Checking this against
`c0 * c0` (component-wise square) matches to 3 decimal places; checking the official
`dualsource_hw` reading against `c0 * c1` (component-wise product) also matches to 3
decimal places (`0.719×0.281=0.202`, `0.202×0.797=0.161`, `0.079×0.921=0.073`,
`1.0×0.5=0.5`).

**CORRECTED INTERPRETATION.** Apple9's dual-source blend, like the standard
Vulkan/D3D/GL model, always multiplies `index(0)`'s color by the *selected blend
factor* — `Src1Color`/`Src1Alpha` are factor *choices* that pull in `index(1)`'s value
as a coefficient, they do not replace `index(0)` as the multiplicand. So the correct
blend-unit equation, confirmed exactly: `result = src0 * factor(src1) + dst *
dstFactor`. This experiment's own pre-registered falsifier text was based on an
incorrect mental model of the blending equation (disclosed here, not silently
corrected); the *substantive* ABI question — does `index(1)`'s shader-computed value
genuinely reach and participate correctly in the hardware/API blend unit — is answered
**YES, HW-VALIDATED**: swapping the blend-factor selection from a self-referencing
`SourceColor` to `Source1Color` changes the observed output from `c0²` to `c0×c1`
exactly, which is only possible if the value the hardware pulls in for the "Source1"
factor genuinely is `c1` (the shader's `index(1)` output), not a repeat of `index(0)`
or a constant. **Driver consequence**: dual-source outputs need no software emulation
on Apple9 — the standard dual-source blend equation is natively supported and its
`index(1)` operand is exactly the shader's second declared color output.

### 3.3 Depth output — HW-VALIDATED, all 3 qualifiers

Real renders, `Depth32Float` private-storage attachment, `MTLCompareFunctionAlways` +
`depthWriteEnabled=YES` (removes any interaction with the depth *test*, isolating the
*write*), blit-readback to a shared buffer. The probe geometry's rasterizer-interpolated
`position.z` is held at a constant `0.0` for every vertex, so any depth-buffer value
other than `0.0` is unambiguous evidence the explicit shader output — not the built-in
interpolated `z` — is what lands in the attachment.

| case | qualifier | requested | observed (center) | observed (corner) |
|---|---|---:|---:|---:|
| `depth_hw_any_250` | `depth(any)` | 0.25 | 0.25 | 0.25 |
| `depth_hw_any_750` | `depth(any)` | 0.75 | 0.75 | 0.75 |
| `depth_hw_less_250` | `depth(less)` | 0.25 | 0.25 | 0.25 |
| `depth_hw_greater_250` | `depth(greater)` | 0.25 | 0.25 | 0.25 |

**Exact match in all 4 cases, both runs.** (Center and corner agree because the probe
triangle deliberately over-covers the whole viewport — a "fullscreen triangle" — so
there is no genuinely-uncovered control pixel in this geometry; the meaningful control
is the constant built-in `z=0.0`, which every case's readback contradicts.)
**INTERPRETED**: explicit fragment depth output is real and functionally correct on
M4 for all three MSL qualifier spellings under a compare function that cannot mask the
write; the `any`/`less`/`greater` distinction affects only the compiler/hardware's
early-Z eligibility contract (not independently probed here — flagged open item), not
correctness of the written value itself.

### 3.4 Fragment stencil output — HW-VALIDATED positive result (corrects the pre-registered H9)

**This experiment's own pre-registered working hypothesis (H9) was that MSL has no
fragment stencil-output attribute**, by analogy with EXP-0097's cull-distance absence.
**That hypothesis is refuted.** `[[stencil]]` is a real, recognized MSL fragment-output
attribute: `struct StencilOut { float4 c0 [[color(0)]]; uint s [[stencil]]; }` compiles
cleanly (216 bytes vs. 166 for the color-only baseline — genuinely more code, not a
silently-dropped attribute) and, under a real `MTLPixelFormatStencil8` attachment with
`MTLStencilOperationReplace` + `MTLCompareFunctionAlways`, the shader's value is what
lands in the buffer:

| case | shader `[[stencil]]` value | encode-time `stencilReferenceValue` | observed stencil (center=corner) |
|---|---:|---:|---:|
| `stencil_hw_sval5` (`f_stencil_out`) | 5 | 200 | **5** |
| `stencil_hw_sval9` (`f_stencil_out`) | 9 | 200 | **9** |
| `stencil_hw_control_mrt1` (`f_mrt1`, no `[[stencil]]` output) | n/a | 200 | **200** |

**Clean, paired positive/negative control, exact in both runs.** With no shader
stencil output, `MTLStencilOperationReplace` writes the fixed-function encode-time
constant (200) — the expected baseline. With a shader `[[stencil]]` output, the buffer
instead gets the *shader's* value (5 or 9), overriding the encode-time constant
entirely. **This is a genuinely new characterization** (not previously attempted in
this repository) and directly closes a named DRV-ABI-01 sub-item ("FS outputs: ...
depth, stencil, ..."). **Driver consequence**: a compiler backend can lower a
Vulkan/GL `gl_FragStencilRefARB`-class fragment stencil-export extension natively via
`[[stencil]]`; no software emulation (e.g., a second discard-based pass) is required on
Apple9.

**Negative-detection control** (proves the harness genuinely distinguishes "compiles"
from "silently rejected," so the `[[stencil]]` positive result is not a harness
artifact): a deliberately-invalid attribute name
(`[[not_a_real_attribute_xyz123]]`) produces `warning: unknown attribute ... ignored`
followed by `error: invalid return type 'BogusOut' for fragment function` —
byte-for-byte the same two-stage rejection shape EXP-0097 documented for
`cull_distance`. Exact, both runs.

### 3.5 Output ordering constraints — not established (open item, stated honestly)

This experiment did not test ordering/interaction constraints between simultaneous
color+depth+stencil+sample-mask outputs from a single fragment invocation (e.g., write
visibility order, whether a depth-fail can suppress an already-computed stencil write).
`UNKNOWN` — flagged for a follow-up experiment, not asserted from the individually-
tested cases above.

---

## §4 CS ABI

### 4.1 Dynamic threadgroup memory — HW-VALIDATED, genuine dispatch-time parameter

ONE compiled pipeline (`cs_tgmem_probe`: `buf[lid] = f(lid); barrier; out[gid] =
buf[(lid+1) mod threads_per_threadgroup.x]`, where the modulus is the RUNTIME
`threads_per_threadgroup` builtin, never a compile-time constant), dispatched 7 times
with `setThreadgroupMemoryLength:atIndex:0` and `threadsPerThreadgroup` both varying
together (`N ∈ {1,2,4,8,16,32,64}`, i.e. `N×4` bytes of `[[threadgroup(0)]]` capacity
each time):

**OBSERVED, exact, both runs byte-identical, all 7 sizes**: every `out[i] ==
(i+1) mod N × 10 + 1` (the expected wraparound value), including the `N=1` degenerate
case (`out[0]==1`, i.e. wraps to itself) and every `out[N-1] == buf[0] == 1` (confirms
the wrap, not just monotonic indexing). Zero faults across the full 1–64 size range,
64× dynamic range, with the SAME compiled bytecode throughout.

**INTERPRETED**: H10 holds. The `[[threadgroup(n)]]` region's base address is a
compiled/fixed offset (works identically regardless of requested size), and its total
CAPACITY is a genuine host-supplied, per-dispatch runtime parameter with no compiled
dependency — a driver can freely vary `setThreadgroupMemoryLength`-equivalent state per
dispatch against a single compiled compute pipeline, exactly the flexibility a Vulkan/GL
`VkComputePipeline` + dynamic shared-memory-size model needs.

### 4.2 Preamble presence — extends EXP-0020 (A18) to M4

Both `cs_with_constant` (binds a `constant Params&` argument) and `cs_no_constant` (only
a plain `device` output buffer, no bound `constant` argument at all) produce an archive
whose vertex/compute stage structurally reports exactly `["_agc.main.constant_program",
"_agc.main"]` — the preamble section is present in BOTH cases. **INTERPRETED**: H11
holds — thread-invariant state (at minimum, the output buffer's own base pointer) lives
in the compiled preamble regardless of whether the kernel binds an explicit `constant`
argument, matching EXP-0020's A18 model, now independently confirmed present on M4 for
both the with- and without-argument cases.

---

## §5 Prolog/main/epilog linkage

### 5.1 No separate linked segment for attribute-fetch/interpolation/output code

Every structural report collected in this experiment (10 spot-checked cases: 3
`vsfetch_format` render pipelines, `fsin_interp_persp`, `fsout_stencil_struct`,
`fsout_depth_any`, `fsout_mrt_4`, `fsout_dualsource_struct`, `cs_preamble_with_constant`,
`cs_preamble_no_constant`) reports **exactly two** regions per compiled stage:
`_agc.main.constant_program` (the preamble) and `_agc.main` (everything else,
including VS attribute fetch, FS interpolation setup, and every FS output family
tested). **No third region ever appears.** **INTERPRETED**: H13 holds — Metal's own
compiler never produces a separately-addressed "prolog" object for attribute fetch or
an "epilog" object for fragment output; both are inlined into the single `_agc.main`
blob per stage. This is a genuine hardware/ABI-relevant negative result, not merely "we
didn't look": **there is no fixed-function or separately-loaded attribute-fetch/blend
unit for the compiler to hand a prolog/epilog to** — a Mesa-style prolog/epilog
key-based shader-variant split (as Asahi already does for M1/M2) is a *software*
organization choice for reducing shader-variant explosion, not something the Apple9
hardware ABI structurally requires or exposes. If a future compiler backend wants a
genuine separately-compiled prolog/epilog pair (e.g. to avoid recompiling a whole VS
per vertex-buffer layout), the mechanism available to implement that split is the
ordinary CALL/RETURN ABI (§5.2, EXP-0035) — arguments in `r10,r11,r12,...`, return value
in `r10`, non-leaf frames spilling to per-thread scratch — not a distinct hardware
"prolog slot."

### 5.2 CALL/RETURN ABI — structural cross-check, M4 reproduces EXP-0035's A18 shape

A `noinline`-attributed helper function called twice from a compute kernel
(`cs_call_probe`) produces compiled bytes containing the pattern `0f 05 54 1a 8f 00 54
...` **twice** (once per call site) — the same CALL-family opcode group (`byte0`
low-nibble `0xf`) EXP-0035 documented on A18. **This is a structural presence
cross-check, not a full byte-level re-decode**: EXP-0035's A18 record shows `byte+6 ==
0x56` at the corresponding position where this M4 capture shows `0x54` — a
one-byte discrepancy that this experiment does **not** resolve (it may be the same
`0x54↔0x56` field `docs/isa/README.md`'s EXP-0038 entry already downgraded to
`UNKNOWN`/context-dependent for an unrelated float-ALU family, or it may be a
distance/offset-dependent field of the CALL encoding itself — not established here).
**Flagged as an open item for DRV-ISA-01**, not silently smoothed over. The
higher-level ABI fact this experiment does establish — that a `noinline` call compiles
to a genuine CALL-family instruction pair on M4, not full inlining — stands
independently of that byte-level question.

---

## Finite-resource rows

| Namespace/resource | Scope | Encoding | Exact usable range/count (tested) | Observed failure mode outside range | Evidence |
|---|---|---|---|---|---|
| VS `[[stage_in]]` attribute fetch address | per-vertex, per attribute | `device_load` computed from `vertex_id`/`instance_id` (base-inclusive) × stride + offset | in-range: exact value; out-of-range (small, base-shifted, or huge-base): reads **zero**, no fault | none observed (zero-fill, not reject/fault) across small OOB, base-shifted OOB, and `baseVertex=1,000,000` OOB | `vsfetch_hw_*` (4/4 cases, both runs) |
| Threadgroup-memory dynamic capacity (`[[threadgroup(0)]]`) | per-dispatch, one compiled pipeline reused | `setThreadgroupMemoryLength:atIndex:` × `threadsPerThreadgroup` (runtime, not compiled) | exact correct wraparound at `N=1,2,4,8,16,32,64` (a 64× range) | not tested past 64 (no failure observed in tested range) | `cstgmem_hw_sweep` (7/7 sizes, both runs) |
| User-varying / stage_in interpolation qualifier space | per fragment-input member | 7 distinct MSL spellings | all 7 compile, all 7 byte-distinct | none — no rejected spelling in the tested set | `fsin_interp_*` (7/7, both runs) |
| MRT attachment count | per render pipeline | `[[color(n)]]`, n=0..3 tested | 1, 2, 4 all compile and render correctly, independently addressed | not pushed past 4 in this experiment (Apple9's documented MRT ceiling is out of this experiment's scope — not re-tested here) | `mrt_hw_{1,2,4}` (3/3, both runs) |
| Fragment stencil-output value | per fragment | `uint`/equivalent via `[[stencil]]`, feeds `MTLStencilOperationReplace` | tested values 5, 9 (both exact); no boundary/overflow (e.g. value >255 into an 8-bit stencil format) tested | not tested — open item | `stencil_hw_{sval5,sval9,control_mrt1}` (3/3, both runs) |
| Dual-source blend factor selection | per color attachment | `MTLBlendFactorSource1Color`/`Source1Alpha` as FACTOR choices (not alternative sources) | confirmed: factor genuinely reads `index(1)`'s value; standard `src0 × factor(src1)` equation, not `src0` replaced by `src1` | n/a (this is a semantic/API-shape finding, not a range boundary) | `dualsource_hw` (official) + supplementary single-run `src0test` (informal, disclosed) |

---

## What P0.8 / DRV-ABI-01 still needs (explicit, not implied)

This experiment closes several named DRV-ABI-01 sub-items on M4 (VS fetch format/
layout/OOB; FS interpolation qualifiers + pull-model + barycentric presence +
primitive_id presence; FS color/MRT/dual-source/depth/stencil outputs; CS dynamic
shared-memory + preamble; the "does a separate prolog/epilog object exist" linkage
question) but the row remains **OPEN**, not `CLOSED`, per `docs/P0-P1-CLOSURE.md`'s six
closure rules. Explicitly still required, not silently dropped:

1. **Programmable-blend-epilog synthesis specification.** This experiment
   characterizes the ingredients (tilebuffer `tile_read`/EXP-0029, dual-source blend
   equation/§3.2, MRT/§3.1) but does not specify the exact consume/produce contract a
   future epilog *generator* must implement across every advertised blend factor/op/
   format combination — DRV-ABI-01 explicitly scopes that as "specify what a future
   epilog generator must emit; do not implement that generator," and the full blend
   factor/operation matrix is a separate, large sub-task not attempted here.
2. **CS system values beyond dynamic shared memory** — `dispatch_threads`,
   `grid_origin`, and the full direct/indirect dispatch sysval table are covered by
   EXP-0092 (M4, already `HW-VALIDATED`), not re-tested here; this experiment adds only
   the dynamic-threadgroup-memory and preamble-presence facts.
3. **FS output ordering constraints** between simultaneous color/depth/stencil/
   sample-mask writes from one invocation (§3.5) — `UNKNOWN`.
4. **Barycentric-coordinate VALUE correctness** (only presence/compile confirmed, §2.3)
   and **`primitive_id` VALUE correctness** (only presence/compile confirmed, §2.4) —
   both need an HW-PROBE readback follow-up.
5. **MSAA-dependent centroid/sample pixel-level differentiation** — not attempted (the
   probe geometry gives full coverage everywhere, so centroid/sample/center are
   indistinguishable at the pixel-value level, matching EXP-0029's same limitation on
   A18).
6. **Full CALL-ABI byte-level re-decode on M4**, resolving the `0x54`/`0x56` byte+6
   discrepancy against EXP-0035's A18 record (§5.2) — flagged for DRV-ISA-01.
7. **Stencil-output value range/overflow behavior** (values beyond an 8-bit stencil
   format's range) — not tested.
8. **Register-level live-value-crossing mechanics** for a hypothetical genuinely-split
   prolog/epilog pair (if a compiler ever chooses to build one via the CALL ABI rather
   than inlining) — this experiment establishes that the CALL ABI *exists* and *could*
   serve this role (§5.1/§5.2) but does not construct or validate an actual split
   prolog/epilog pair end-to-end.
9. **A18/G17P confirmation** of every M4 fact in this document — all `INFERRED`-by-family
   per `docs/m4-deltas.md`'s ISA-identity finding, not independently validated (A18 is
   hands-off).

---

## Clean-room provenance

```text
Clean-room provenance: OWN-SHADER (structural: harness/vfetch_extract.m,
  harness/mrt_extract.m, and the unmodified tools/shdump/shdump.m, rebuilt fresh from
  committed source) + OWN-SHADER + HW-PROBE (harness/render_probe.m,
  harness/compute_probe.m: real draws/dispatches, no splicing) + PUBLIC (MTLVertexFormat/
  MTLPixelFormat/MTLBlendFactor enum values and supportsShaderBarycentricCoordinates,
  read from the public Metal.framework SDK headers — public developer-facing API
  declarations, not compiled binaries; and the public Metal Shading Language compiler's
  own diagnostic text, returned for OUR OWN source via the public
  newLibraryWithSource: API).
Inputs inspected: kernels/vfetch.metal, kernels/mrt_interp.metal, kernels/cs_probe.metal
  (all authored by us); public Metal SDK headers (MTLVertexDescriptor.h,
  MTLPixelFormat.h, MTLRenderPipeline.h, MTLDevice.h); NSError diagnostic strings the
  public compiler returns for our own source.
Apple binary introspection: NONE. No disassembler, decompiler, or binary-inspection
  tool was run on any Apple framework, dylib, kext, firmware, or compiler binary.
  tools/agx-isa/ and tools/agxtest/ were not touched; tools/shdump/shdump.m was used
  unmodified (rebuilt from its committed source into this experiment's own work/bin/).
Reproduction: python3 run.py --run <id> --out raw/<id> (×2); python3 verify.py
  --crossrun raw/m4-20260828-run01 raw/m4-20260828-run02; python3 analysis/decode.py;
  python3 verify.py --selftest; python3 verify.py --seqtest.
Evidence: raw/m4-20260828-run01/, raw/m4-20260828-run02/ (00_inputs.json, 01_cases.json,
  04_results.jsonl, 05_run_manifest.json each), analysis/summary.json,
  harness/fixtures/recorded_reality.json, CAPTURE_CONTRACT.json (authored sha256 set).
```

## Files

- `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json`, `PROGRESS.md` — frozen contract and
  milestone log.
- `casematrix.py` — the 57-case frozen matrix (single source of truth for `run.py` and
  `verify.py`).
- `kernels/vfetch.metal`, `kernels/mrt_interp.metal`, `kernels/cs_probe.metal` —
  authored MSL.
- `harness/vfetch_extract.m`, `harness/mrt_extract.m` — structural (compile+extract)
  probes, adapted from EXP-0031's `attrdump.m` pattern.
- `harness/render_probe.m`, `harness/compute_probe.m` — HW-PROBE (real draw/dispatch +
  readback) probes.
- `run.py`, `verify.py` — capture driver + standing-gate verifier.
- `raw/m4-20260828-run01/`, `raw/m4-20260828-run02/` — the two official captures.
- `analysis/decode.py`, `analysis/summary.json` — post-capture arithmetic (half-float
  decode, byte-length diffing), no new GPU calls.
- `harness/fixtures/recorded_reality.json` — real-GPU-call-derived selftest fixture.

## STOPs

No BLOCKED state was entered; no host wedge, reboot, or `macvdmtool` use occurred. Two
honestly-disclosed course corrections were internal to this experiment's own
pre-registration (H9's working hypothesis about `[[stencil]]`, and H7's blend-equation
mental model) — both are documented above with the falsifying evidence and the
corrected interpretation, not silently smoothed over.

One operational-compliance correction, disclosed for the record: during development,
the supplementary dual-source probe (§3.2) was first written and run from `/tmp/`
(outside `/Users/user/asahi_re/public/agx-re`), before being copied verbatim into
`work/supplementary/render_probe_src0test.m` and re-run from inside the repo — the
result cited in RESULTS.md is the in-repo re-run's output (identical to the original,
confirming no discrepancy was introduced). The `/tmp/` copies were deleted. No Apple
binary or file outside this repository was read, searched, or otherwise operated on at
any point — the excursion was limited to writing/compiling/running our own authored
`.m` source in `/tmp` — but it should not have happened per `CLAUDE.md`'s "never leave
this directory" rule, and is recorded here rather than omitted.
