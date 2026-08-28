# RESULTS — EXP-0136 M4 Metal-unreachable descriptor/opcode encodings (DRV-P2-05)

**Target: Apple M4 (G16G), local host only, macOS 26.6.2, Metal 4. No A18 Pro claim
anywhere (A18 hands-off per CLAUDE.md).** Two official capture runs
(`raw/m4_20260828_run01/`, `raw/m4_20260828_run02/`), **97/97 cases each, 97 PASS / 0
FAIL / 0 TIMEOUT both runs.** `verify.py --captured m4_20260828_run01 m4_20260828_run02`
→ `cross_run_gate_pass: true, issues_total: 0`. `--selftest` 14/14, `--seqtest` 3/3. Zero
GPU hangs that were not fault-contained; zero host wedges across ~200 total case
executions (97×2 official + 9 smoke + the non-recorded spike).

```
Clean-room provenance: HW-PROBE + DATA-TRACE + OWN-SHADER
Inputs inspected: our own MSL (harness/descpatch.m, harness/gfxprobe.m string templates,
  harness/kernels/add.metal), the public Metal API (MTLSamplerDescriptor,
  MTLTextureDescriptor, MTLRenderPipelineDescriptor, MTLRenderCommandEncoder,
  MTLBuffer.gpuAddress/.contents), tools/iotrace (read-only, unmodified, hash-checked --
  see CAPTURE_CONTRACT.json) used strictly as a DATA source (never as a write path to
  Apple code), and tools/agxtest (read-only, unmodified, hash-checked) for the opcode
  splice family.
Apple binary introspection: NONE. No Apple binary was disassembled, decompiled, or
  otherwise introspected anywhere in this experiment. Descriptor bytes, command-stream
  bytes, and OS fault-classification strings are DATA (call parameters / buffer contents /
  public NSError text), not code, per the Asahi clean-room policy already relied on
  throughout this repo (tools/iotrace/README.md, EXP-0015).
Reproduction: harness/run.py --run <id> --out raw/<id> (x2), then
  harness/verify.py --captured <run_a> <run_b>. See README.md "Commands" for the full
  sequence including the standing gates.
Evidence: raw/m4_20260828_run01/, raw/m4_20260828_run02/ (00_inputs.json,
  02_gated.jsonl, 03_nongated.jsonl, 04_manifest.json each); work/spike/ (non-recorded
  method-validation spike -- method only, no promoted fact drawn from it);
  work/smoke/ (non-recorded smoke gate, 9 cases).
```

## 0. Technique note (a load-bearing negative finding in its own right)

The direct-descriptor-patch technique (`harness/descpatch.m`) required a redesign after
the first attempt **failed silently**: patching a Metal-internal sampler/texture
descriptor's bytes *between two separate dispatches* that both reference the same
`MTLSamplerState` object does not work — Metal's own `-setSamplerState:atIndex:` on the
**second** encoder rewrites the descriptor pool entry back to the object's creation-time
canonical bytes before the second dispatch ever runs, silently reverting the patch with no
error of any kind. This is itself a real hardware/driver-boundary fact: **the descriptor
pool entry is not stable, externally-patchable memory across re-encodes of the same
object** — Metal re-materializes it on every bind, not just once at creation. The working,
validated design instead patches the bytes *within* the single command buffer whose
execution is being observed (between `-endEncoding` and `-commit`, never followed by
another `-setSamplerState:`/`-setTexture:` call), with a separate process run (empty patch
list) as the paired control. See `PRE_REGISTRATION.md` §0/§1/§2 for the full method and
its bit-exact positive-control validation.

## 1. OBSERVED — Sampler anisotropy beyond Metal's 16× cap (H1)

**OBSERVED** (family `aniso`, 16/16 cases, `raw/m4_20260828_run{01,02}/`, byte-identical):
sampled-pixel red channel (`observed.pixel[0]`) of a hand-authored mip chain (rows
alternate 0/255 at mip0; every mip≥1 is uniformly ≈127 by box-filter construction) under an
explicit `gradient2d` derivative producing a controlled anisotropy ratio:

| ratio (dPdx:dPdy texels) | real aniso1 | real aniso2 | real aniso4 | real aniso8 | real aniso16 | patched aniso32 | patched aniso64 | patched aniso128 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 16  | 0.498 | 0.498 | 0.498 | 0.498 | **1.000** | 1.000 | 1.000 | 1.000 |
| 64  | — | — | — | — | 0.498 | 0.498 | **1.000** | 1.000 |
| 128 | — | — | — | — | 0.498 | 0.498 | 0.498 | **1.000** |

(0.498 ≈ 127/255 = the fully-blurred/mip-averaged value; 1.000 = the fully-resolved,
correct row value.)

**INTERPRETED.** At ratio=16 (exactly Metal's advertised cap), real aniso values below 16
under-resolve (blur) and real aniso=16 exactly resolves — a clean, monotonic sanity curve
confirming the mip-chain/gradient design correctly measures anisotropic resolving power.
At ratio=64 and ratio=128, **real aniso=16 always blurs** (Metal's own maximum is
insufficient once the ratio exceeds it, as expected) — but a **directly patched**
`maxAnisotropy` encoding of 32/64/128 (values Metal's public API can never produce; the
sampler byte2 bits[4:6] 3-bit log2 field, values 5/6/7) **crisply resolves exactly when the
patched value is ≥ the ratio**, with the identical blur/crisp threshold pattern a genuine,
unclamped anisotropic filter would produce. **This is not "doesn't fault" — it is a
measured, monotonic, threshold-exact quality effect**, the strongest form of evidence this
experiment collects for any claim. **HW-VALIDATED.**

**Verdict: AGX9 sampler hardware natively supports anisotropic filtering up to at least
128× (the full range of the 3-bit log2 field). Metal's 16× cap is a pure software/API
ceiling with zero hardware backing.** Tested range: aniso codes 0–7 (1×..128×); ratios
16/64/128; only tested at ratios that are exact powers of the aniso codes' boundaries —
finer-grained ratio sweeps (e.g. 20:1, 48:1) were not run and would refine the exact
crossover shape but cannot change the headline finding (128× definitively works; 16× cap
is definitively artificial).

## 2. OBSERVED — Sampler address-mode codes 4, 6, 7 (H2)

**OBSERVED** (family `addrmode`, 32/32 cases, byte-identical both runs): 4-point pixel
signature per code (u = 1.2, 1.7, 2.6, −0.4; v fixed 0.5; `address_t=clampToEdge`
throughout; `address_s` is the field under test):

| code | signature (4 points) | classification |
|---:|---|---|
| 0 (clampToEdge, documented) | edge,edge,edge,(0.5333,.,0,.) | reference |
| 1 (repeat, documented) | wraps each point independently | reference |
| 2 (mirrorRepeat, documented) | mirrors each point independently | reference |
| 3 (clampToBorder/Zero, documented) | (0,0,0,0) at all 4 points | reference |
| 4 (**unreachable**) | **byte-identical to code 0 at all 4 points** | **exact alias → clampToEdge** |
| 5 (mirrorClampToEdge, documented) | matches code0 at 3/4 points, diverges at u=−0.4 | genuinely distinct mode (not an alias) |
| 6 (**unreachable**) | **byte-identical to code 3 at all 4 points** | **exact alias → clampToBorder** |
| 7 (**unreachable**) | **byte-identical to code 3 at all 4 points** | **exact alias → clampToBorder** |

**INTERPRETED.** Codes 4/6/7 are not garbage, not faults, and not novel addressing modes —
they are **exact, deterministic hardware aliases**: code 4 behaves identically to code 0
(clampToEdge) and codes 6/7 both behave identically to code 3 (clampToBorder) across every
tested point, resolving EXP-0015's open "codes 4,6,7 untested" note. **HW-VALIDATED**
(4-point signature match, not a single coincidental sample — code 5 in the same test
correctly shows itself as *genuinely distinct*, proving the signature method has the power
to detect a real difference when one exists). **No native address mode exists beyond the 5
Metal already exposes** (0/1/2/3/5); the address-mode field's nominal 3-bit/8-value space
is hardware-limited to exactly 5 distinct behaviors, two of the remaining three collapsing
onto "clamp to border" and one onto "clamp to edge". Tested range: 8 codes × 4 UV points,
all out-of-[0,1] (1.2, 1.7, 2.6, −0.4); u values inside [0,1] and 3D `address_r` were not
tested.

## 3. OBSERVED — Sampler border-color code 3 (H3)

**OBSERVED** (family `border`, 12/12 cases, byte-identical both runs): code under test
patched into a sampler *created* with each of the 3 real border presets:

| created with → | code0 patched | code1 patched | code2 patched | code3 patched (**unreachable**) |
|---|---|---|---|---|
| transparentBlack | (0,0,0,0) | (0,0,0,1) | (1,1,1,1) | **(0,0,0,0)** |
| opaqueBlack | (0,0,0,0) | (0,0,0,1) | (1,1,1,1) | **(0,0,0,0)** |
| opaqueWhite | (0,0,0,0) | (0,0,0,1) | (1,1,1,1) | **(0,0,0,0)** |

**INTERPRETED.** Codes 0/1/2 exactly match their expected preset regardless of which
preset the sampler was actually *created* with — confirms the patch, not the creation-time
value, genuinely controls the field (a required internal falsifier: if the patch were
silently ignored, code0-patched-onto-an-opaqueWhite-sampler would read (1,1,1,1), not
(0,0,0,0); it never does). **Code 3 reads transparent-black (preset 0) in all three
creation conditions** — true hardware aliasing to preset 0, independent of creation
context, not "ignores the patch." **HW-VALIDATED, adversarially cross-checked (3 different
creation contexts).** Confirms and strengthens EXP-0015's original finding (2-bit field,
only 3 presets exist in hardware — no 4th preset, and definitely no room for an arbitrary
RGBA border color as Vulkan's `VK_EXT_custom_border_color` wants).

## 4. OBSERVED — Texture-descriptor swizzle codes 6, 7 (H4)

**OBSERVED** (family `swizzle`, 11/11 cases, byte-identical both runs; component0/R-dst
byte2 bits[0:2], component1/G-dst byte2 bits[3:5]):

| code | comp0 (R-dst) result | comp1 (G-dst) result |
|---:|---|---|
| 0 (R) | r=0.6667 (= source R) | g=0.6667 (= source R) |
| 1 (G) | r=0.7843 (= source G) | — |
| 2 (B) | r=0.1569 (= source B) | — |
| 3 (A) | r=1.0 (= source A) | — |
| 4 (One) | r=1.0 | g=1.0 |
| 5 (Zero) | r=0.0 | — |
| 6 (**unreachable**) | **`CMDBUF_ERROR`** (GPU-hang-class fault) | **`CMDBUF_ERROR`** |
| 7 (**unreachable**) | **`CMDBUF_ERROR`** | not tested |

**INTERPRETED.** Codes 0–5 exactly reproduce the predicted channel-routing value (R, G, B,
A, constant-1, constant-0) — the full documented 6-value swizzle codespace is confirmed
correct and now **HW-VALIDATED by direct construction** (previously DATA-TRACE-only per
EXP-0015). **Codes 6 and 7 hard-fault the command buffer** on both components tested — this
is the one family in this experiment where "unreachable" means the hardware actively
rejects the encoding rather than aliasing it. The fault is **fault-contained** (per-command-
buffer, no host wedge, consistent with CLAUDE.md's expectation) but is a genuine **GPU-hang
class** fault, not a graceful validation error — see §6 for the fault-classification detail
and its confirmed cross-run nondeterminism.

## 5. OBSERVED — Primitive restart is a fixed all-ones sentinel (H5)

**OBSERVED** (family `restart`, 6/6 cases, byte-identical both runs): indexed triangle-strip
draw over two disjoint vertex-position groups joined by one sentinel index:

| index type | sentinel value | connector band lit? | classification |
|---|---:|---:|---|
| u16 | `0xFFFF` (all-ones) | **0 (cut — restart honored)** | matches docs/cmdstream's DATA-TRACE-only prediction |
| u16 | `0xFFFE` | 1 (literal index used, strip connected) | not restart |
| u16 | `8` (small OOB, only 8 real vertices) | 1 (literal index used, strip connected) | not restart, and no fault |
| u32 | `0xFFFFFFFF` (all-ones) | **0 (cut — restart honored)** | matches |
| u32 | `0xFFFFFFFE` | 1 | not restart |
| u32 | `8` (small OOB) | 1 | not restart, and no fault |

**INTERPRETED.** Restart triggers **exactly and only** at the all-ones sentinel for both
index widths; adjacent values (`0xFFFE`) and small out-of-bounds literals are used as a
literal vertex index (connecting/rendering through the "gap", proving the strip was NOT
cut) — **upgraded from `docs/cmdstream/README.md`'s DATA-TRACE-only field observation
("restart comparand @+0x68 ... Metal always uses all-ones") to a full `HW-VALIDATED`
behavioral confirmation.** Secondary finding: an out-of-bounds vertex index (`8`, against
an 8-vertex, indices-0..7 buffer) does **not** fault — the GPU reads *some* defined memory
location and renders with it (no page fault, no command-buffer error). This is a real,
distinct, useful fact for driver safety margins (OOB vertex fetch is silently tolerated,
not caught), separate from the restart question itself, and is flagged as its own item
below.

**Whether the *raw* VDM restart-comparand field is genuinely programmable to an
arbitrary (non-sentinel) value remains `UNKNOWN`** — this would require direct VDM
command-stream patching, assessed infeasible to do safely in this session (see §7,
Blocked probes). For driver purposes this changes nothing: Metal's own encoder always
writes the all-ones sentinel regardless of what an OpenGL app's `glPrimitiveRestartIndex`
requested, so an implementer targeting arbitrary restart indices must remap index buffers
in software to use the all-ones convention — unchanged from the prior STRUCTURAL finding,
now resting on stronger (behavioral) evidence.

## 6. OBSERVED — No native geometry-shader/stream-output hardware path (H6)

**OBSERVED** (family `norender`, 2/2 cases, byte-identical both runs): a
`rasterizationEnabled=NO` render pipeline (public Metal API; requires a `void`-returning
vertex function) draws 3 vertices; an atomic counter proves the vertex stage executed
(`vertex_invocations_observed=3` in both the raster-on and raster-off case) while
`any_fragment_rendered` correctly reads 1 (raster-on) / 0 (raster-off).

**INTERPRETED.** `rasterizationEnabled=NO` is a real, working "vertex-only" pipeline mode:
vertex processing runs, fragment output is suppressed. This is exactly the API surface an
implementer would reach for to emulate OpenGL transform feedback / stream-output at the
Metal level. **Combined with the pre-existing, independently-established evidence that the
VDM draw-record field map is exhaustively decoded with zero leftover/unknown bytes**
(`docs/cmdstream/README.md`, "VDM draw record — full field map", EXP-M4-09/CMD-4 — no
room in that already-fully-explained record for an additional native "stream-out target"
binding) **and a non-recorded spike observation that the set of registered GPU BOs for a
raster-on vs. raster-off draw is nearly identical (41 vs 40 — the only difference being the
absent render-target texture) rather than structurally distinct** (spike-only, method
validation only, not independently promoted as a standalone fact — cited as corroborating
context for the primary VDM-field-map evidence, not as a substitute for it): **there is no
evidence of a distinct native geometry-amplification or stream-output hardware
mechanism.** `rasterizationEnabled=NO` runs the *same* VDM/tiler vertex pipeline with the
fragment stage elided, not a separate hardware path. **This is a clean negative result**,
directly answering the question EXP-0098 explicitly left open ("native GS/streamout
hardware... out of scope for this bundle... this experiment is the search").

**Verdict: OpenGL/Vulkan-style transform feedback and geometry shaders have no native
AGX9 hardware path and must be permanently emulated** (compute-based, per EXP-0098's
already-`HW-VALIDATED` closed-form model for capacity/multistream/discard semantics and
synchronization contract). This is distinct from **mesh shading**, which — per
`docs/isa/README.md` — IS a genuine native hardware graphics pipeline (object→mesh grid
amplification is real); mesh shading is not a substitute API shape for classic
geometry-shader/transform-feedback semantics, but is worth flagging to implementers as the
one place this SoC generation *does* do amplification natively.

## 7. Blocked probes (recorded per PRE_REGISTRATION.md §5, not silently dropped)

Two sub-questions were assessed **infeasible to probe safely in this session** and are
recorded as bounded `UNKNOWN`:

- **An arbitrary (non-sentinel) primitive-restart comparand value.**
- **A raw hardware bit for provoking-vertex or conservative-rasterization**, beyond the
  existing Metal-exposure-level negative results already established (EXP-0097: provoking
  vertex is fixed to first-fetched-vertex with no Metal API to change it; EXP-0123:
  conservative rasterization has no Metal API toggle at all).

Both would require writing into the raw VDM/tiler draw-stream or 3D fixed-function-state
BOs (`docs/cmdstream/README.md`: GPU VA `0x18000`/`0x58000`, both `(fw ctx)` —
firmware-context-relative). Unlike the Metal-userspace descriptor-pool heap this experiment
successfully patches (created once, read across many *separate* dispatches, patched in a
fully GPU-idle window with a verified-stable CPU address), the VDM/FF-state stream is
written and consumed within a *single* command-buffer submission whose doorbell ring is,
per EXP-0009, **invisible to `iotrace`** ("likely a store into a firmware-shared page +
barrier"). There is no established safe window to write into it without racing live GPU
consumption — under this repo's explicit no-out-of-band-recovery safety model, that is a
plausible host-wedge vector this experiment declines to attempt. This is a deliberate scope
boundary for a future experiment that first establishes a safe write window for
firmware-context BOs (plausibly requiring kernel-driver coordination, out of scope for
userspace-only RE).

## 8. Full probe log — works / no-op / faults / hangs (docs/hypotheses.md style)

| encoding probed | family | outcome | note |
|---|---|---|---|
| sampler aniso code 5/6/7 (32×/64×/128×) at ratio > 16 | aniso | **WORKS — measured quality improvement** | native support beyond Metal's 16× cap |
| sampler aniso code 5/6/7 at ratio ≤ existing coverage (16) | aniso | works, no-op relative to real aniso16 (already sufficient) | over-provisioning is harmless |
| sampler address code 4 | addrmode | **no-op — exact alias to code 0** | |
| sampler address code 6 | addrmode | **no-op — exact alias to code 3** | |
| sampler address code 7 | addrmode | **no-op — exact alias to code 3** | |
| sampler border code 3 | border | **no-op — exact alias to preset 0**, adversarially confirmed across 3 creation contexts | |
| texture swizzle code 6 (both components tested) | swizzle | **FAULTS — CMDBUF_ERROR, GPU-hang class** | fault-contained, no host wedge |
| texture swizzle code 7 (comp0) | swizzle | **FAULTS — CMDBUF_ERROR, GPU-hang class** | fault-contained, no host wedge |
| index value `0xFFFF`/`0xFFFFFFFF` in an indexed strip | restart | **WORKS — restart cut honored** | HW-VALIDATED upgrade of a prior STRUCTURAL fact |
| index value `0xFFFE`/`0xFFFFFFFE` | restart | works as a literal (no restart, no fault) | |
| out-of-bounds small index (`8`, only 8 real vertices) | restart | works as a literal, **no fault** (silent OOB tolerance) | driver-safety-relevant secondary finding |
| `rasterizationEnabled=NO` | norender | **WORKS as documented** (vertex-only pipeline) | no distinct native GS/streamout mechanism found |
| `device_load` `reserved7`/`reserved13` = 0x01/0xFF/0x55/0xAA, individually and combined | opcode | **no-op — confirmed inert** | both load instances in the test program |
| `device_store` `reserved7`/`reserved13` = 0xFF/0x55 | opcode | **no-op — confirmed inert** | |
| terminal `stop` word byte0 = 0x3f/0x99/0xd3/0x5a/0xc1/0xff | opcode | **no-op — confirmed inert** | replicates/extends EXP-0003/EXP-0010's existing finding to a broader byte0 value set (not a novel result) |

No case in either official run produced a HANG (process-level timeout); the only faults
observed were the two swizzle families' `CMDBUF_ERROR`s, both fault-contained.

## 9. Finite-resource / hard-capacity rows

| resource | encoding | HW-usable range | Metal-exposed range | first value beyond Metal's range that still works | evidence |
|---|---|---|---|---|---|
| Sampler max anisotropy | 3-bit log2 (sampler byte2 bits[4:6]) | **1×..128× (codes 0-7), all 8 values functionally distinct and correctly resolving** | 1×..16× (`MTLSamplerDescriptor.maxAnisotropy`, [1,16]) | **32× (code5) — first Metal-unreachable value, confirmed working with a measurable quality benefit at ratio>16** | `aniso` family, 16/16 cases, both runs |
| Sampler address mode | 3-bit field (sampler byte3 bits[5:7]) | **exactly 5 distinct hardware behaviors** (clampToEdge, repeat, mirrorRepeat, clampToBorder, mirrorClampToEdge) despite 8 encodable values | same 5, via `MTLSamplerAddressMode` | none — codes 4/6/7 are dead/aliased space, not additional capability | `addrmode` family, 32/32 cases |
| Sampler border color | 2-bit field (sampler byte7 bits[5:6]) | **exactly 3 presets**, no 4th, no arbitrary RGBA | same 3, via `MTLSamplerBorderColor` | none — code 3 is dead/aliased space | `border` family, 12/12 cases; confirms EXP-0015 |
| Texture swizzle codespace | 3-bit/component (texture byte2, 2 components tested) | **exactly 6 legal codes (R,G,B,A,One,Zero); codes 6/7 are illegal and hardware-enforced (hard fault)** | same 6, implicitly via pixel-format/component-mapping surface | none — codes 6/7 are actively rejected, not extra capability | `swizzle` family, 11/11 cases; confirms+extends EXP-0015 |
| Primitive restart comparand | fixed all-ones sentinel, u16/u32 | **hardware genuinely restarts on 0xFFFF/0xFFFFFFFF**; no evidence (nor counter-evidence — untested) of programmability to another value at the Metal-observable level | Metal always emits the all-ones sentinel; no API to choose another | N/A — the raw HW field's programmability is `UNKNOWN` (§7) | `restart` family, 6/6 cases |
| `device_load`/`device_store` `reserved7`/`reserved13` | 1 byte each, 2 instructions × 2 fields | confirmed **inert padding** across tested value range | N/A (compiler never emits nonzero here) | N/A | `opcode` family, 12/18 cases directly on this |

## 10. PROMOTE-TO-P0/P1 (per DRV-P2-05's own explicit rule: "unknown hard resource
capacities must be promoted to P0/P1 even if the performance model remains deferred")

- **PROMOTE: sampler `maxAnisotropy` hardware ceiling is 128× (3-bit log2 field), not
  Metal's advertised 16×.** This is a hard, previously-undocumented resource capacity with
  a `HW-VALIDATED` behavioral effect (not merely an accepted-but-inert encoding). An
  implementer building a Vulkan/GL driver on this hardware can expose
  `VK_EXT_sampler_filter_minmax`-adjacent / higher-aniso extensions natively instead of
  emulating them, and should NOT hard-code Metal's 16× as a hardware limit anywhere in the
  driver (e.g. `maxSamplerAnisotropy` in a Vulkan `VkPhysicalDeviceLimits` equivalent
  should report up to 128, not 16, if that surface is exposed). Recommend a new P1-adjacent
  row (or an addendum to the existing sampler-descriptor documentation, `docs/descriptors/`)
  capturing the full 0-7 code table with this experiment's evidence.
- **PROMOTE (documentation-completeness, not a new capability): the exact alias/failure
  behavior of every previously-"untested" finite-field code** (address modes 4/6/7,
  border code 3, swizzle codes 6/7) is now a closed, `HW-VALIDATED` fact rather than an
  open question in EXP-0015's "still opaque / recommended next" list. This does not change
  any driver's emittable-value set (the aliases/faults are all within Metal's own reachable
  value envelope, so no new capability is unlocked) but removes three open items from the
  capability-completeness ledger and should update `docs/descriptors/` (address-mode table
  footnote, border-color table footnote, swizzle-code table footnote) and
  `docs/capability-completeness.md`.
- **PROMOTE: texture swizzle codes 6/7 cause a genuine GPU-hang-class fault** (not a benign
  rejection) — worth a driver-facing note that these bit patterns must never be emitted or
  allowed to reach the hardware (e.g. must be validated/rejected at the driver's own
  encoding layer, not left to hardware fallback), distinguishing this family from the
  address-mode/border families (which silently and safely alias).
- **PROMOTE: out-of-bounds vertex-index fetch during an indexed draw does not fault** —
  a driver-relevant safety-margin fact (index buffers with stale/OOB data read *something*
  defined rather than crashing), worth a line in the userspace↔kernel interface notes or
  wherever index-buffer validation responsibilities are documented.
- **Restart comparand programmability and provoking-vertex/conservative-raster hardware
  bits remain explicitly `UNKNOWN`** (§7) — flagged for promotion to a *future* P0/P1 row
  only once a safe firmware-context BO write window is established; not promoted now
  because no positive or negative fact was actually established, only a scope boundary.
- **No native geometry-shader/stream-output hardware path exists** — this closes, rather
  than opens, a capacity question: implementers should permanently budget for
  compute-emulated transform feedback/geometry shading (per EXP-0098's already-`HW-
  VALIDATED` model) with no expectation of a future native fast path on this
  hardware generation.

## 11. Emulate vs. native list (for the GL/Vulkan driver surface)

| capability | native on AGX9? | note |
|---|---|---|
| Anisotropic filtering up to 16× | **Native** | matches Metal's own cap |
| Anisotropic filtering 32×/64×/128× | **Native** (this experiment) | Metal itself cannot reach it; a Vulkan/GL driver CAN expose it natively via direct descriptor construction |
| `clampToEdge`/`repeat`/`mirrorRepeat`/`clampToBorder`/`mirrorClampToEdge` addressing | **Native** | full 5-mode set, matches Vulkan/GL's standard address modes |
| Arbitrary (>5-mode) or custom addressing | **Not present** | codes 4/6/7 are dead space, not extra modes — nothing to expose |
| 3 border-color presets (transparent/opaque black/white) | **Native** | |
| `VK_EXT_custom_border_color` (arbitrary RGBA border) | **Emulate** | confirmed no 4th hardware slot exists (8-byte descriptor has no room; adversarially reconfirmed here) |
| Texture component swizzle (R/G/B/A/One/Zero) | **Native** | full Vulkan/GL swizzle model |
| Primitive restart (fixed sentinel) | **Native** | matches D3D10+/Vulkan `VK_EXT_primitive_topology_list_restart`-style fixed semantics |
| OpenGL arbitrary `glPrimitiveRestartIndex` | **Emulate** (index remap) | Metal always emits all-ones; raw HW programmability unresolved but irrelevant to the driver contract either way |
| Provoking-vertex selection (OpenGL last-vertex convention) | **Emulate** (index-buffer rewrite) | unchanged from EXP-0097; raw HW bit unresolved |
| Conservative rasterization | **Emulate** (geometry inflation) | unchanged from EXP-0123; raw HW bit unresolved |
| Geometry shaders / transform feedback / stream-output | **Emulate permanently** (compute-based) | this experiment's H6 finding: no native path exists on this hardware generation |
| Mesh/object shading (grid amplification) | **Native** | distinct API shape from classic GS/streamout; not a substitute, but the one genuine native amplification path on this SoC |

## 12. Limitations / what remains unknown

- Anisotropy was tested at 3 ratio points (16/64/128) crossed with 8 code values; the exact
  crossover curve at non-power-of-two ratios (e.g. does aniso=48 fully resolve a 50:1
  ratio?) was not mapped — the headline finding (128× works, 16× cap is artificial) does
  not depend on this.
- Address-mode signatures were built from 4 out-of-range UV points; in-range UV points and
  the 3D `address_r` axis were not independently tested (address-mode codes are documented
  as shared across axes in EXP-0015; not re-verified here).
- Swizzle was tested on 2 of 4 components (R-dst fully, G-dst as a 3-point cross-check);
  B-dst/A-dst were not independently tested, though the field's symmetric 3-bit/component
  structure and the R/G-dst agreement make an asymmetry unlikely.
- The raw VDM/tiler and 3D fixed-function-state command-stream fields (restart comparand
  programmability, provoking-vertex/conservative-raster hardware bits) remain `UNKNOWN` —
  see §7.
- The performance-model half of DRV-P2-05 (occupancy, latency/throughput, cache behavior,
  tile/parameter-buffer sizing, workgroup repacking) is entirely out of scope for this
  experiment, per the row's own explicit deferral.
