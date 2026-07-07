# GAP-ANALYSIS-01 — Adversarial acceptance dry-run

**Reviewer role:** gap-finder for the final acceptance gate. Premise: implement Apple A18 Pro
(G17P) support in Mesa's `asahi` userspace driver **from scratch**, using **only `docs/`** as the
source of A18-specific hardware truth. `mesa/src/asahi` was read only to understand the *target
structure* (what a userspace driver must produce), never as a source of A18 facts.

**Date:** 2026-07-07. Scope reviewed: `hardware-overview.md`, `isa/README.md`,
`isa/msl-feature-map.md`, `cmdstream/README.md`, `descriptors/README.md`, `tiling/README.md`,
`pipeline/README.md`, `hypotheses.md`, `mesa-userspace-requirements.md`, `ROADMAP.md`.

---

## Overall verdict: **FAIL — cannot be implemented from `docs/` alone.**

The documentation is a strong, honest *foundation* — the clean-room method is proven, the machine
model (96 GPRs, uniform file, spill), the core float/int ALU operand encodings, the descriptor and
tiling layouts, and the TBDR tile model are real, hardware-validated, and well written. But an
implementer restricted to `docs/` would be **blocked before completing a single non-trivial shader
or any textured draw**, and would have to "just figure out" or go to out-of-bounds sources
(`tools/agx-isa/db.json`, the `experiments/*/RESULTS.md` files, or Apple's stack) for facts that are
*essential*, not cosmetic.

**How far could you actually get?**
- ✅ A pure-arithmetic compute kernel (add/mul/fma/int-add), single dispatch, no memory reuse — yes.
- ⚠️ Any compute shader that does **more than one dependent memory/texture/atomic access** — **no**,
  because the **scoreboard/wait model is entirely undocumented** and its absence produces *silent
  data corruption*, not a fault.
- ⚠️ Any shader using **division, `sqrt`, `normalize`, `rsqrt`, or trig** — **no**; the
  reciprocal/transcendental instruction *sequences* are explicitly `⏳ follow-up`.
- ❌ **Any draw** — **no**; the graphics **shader-entry word in the USC block is explicitly "opaque"**
  (`cmdstream` calls this out three times), so you cannot bind a VS/FS to a VDM draw.
- ❌ **Any textured / interpolated fragment shader** — **no**; fragment varying interpolation
  (`iter`/`ldcf`) is only a list of byte-0 leaders "⏳ pending a decode experiment," and the full
  texture-format→descriptor table is deferred to an experiment RESULTS file outside `docs/`.
- ❌ **Ray tracing, mesh/object, cooperative matrix** — **no**; there is *zero* hardware
  documentation for any of these (only MSL *provocation snippets*, self-labeled "planning index, not
  a hardware claim").

Estimated completeness against a working GL/Vulkan userspace: the *documented* surface is real and
useful, but as a self-contained implementation spec it is roughly **one-third of the way** — enough
to bring up the RE tooling and validate a compute add-kernel, not enough to pass a triangle.

**A structural problem that pervades the ISA section:** `isa/README.md` states outright that "the
machine-readable, **authoritative** encoding lives in **`tools/agx-isa/`** … Prose summary below;
**treat the DB as source of truth**." The prose is explicitly a *summary*, and the source of truth
is a file the acceptance gate forbids as an A18 source. Per the gate rules ("If it would have to
look at … just figure it out, that is a gap"), **the ISA spec fails its own completeness bar by
construction** — the doc points the reader out of `docs/` for the exact bit layouts. The same
pattern recurs for the descriptor **format table** ("Full 31-format table in EXP-0015 RESULTS") and
the tiling evidence ("RESULTS.md has the full evidence table").

---

## Per-subsystem PASS / GAP

| # | Subsystem | Verdict | One-line reason |
|---|-----------|---------|-----------------|
| 1 | Shader compiler backend (emit AGX from NIR) | **GAP (blocking)** | No scoreboard/wait model at all; transcendentals/rcp/rsqrt undocumented; fragment interp undecoded; SR enum + preload ABI absent; "authoritative" encoding deferred to out-of-bounds `tools/`. |
| 2 | Command stream (compute + draw) | **GAP (blocking)** | Compute CDM mostly there but threadgroup-memory-size field unknown & config word ⏳; **graphics USC shader-entry word explicitly opaque** → cannot bind shaders to a draw; PPP header/emission-order grammar absent; doorbell mechanism unknown. |
| 3 | State (depth/stencil/blend/raster) | **PARTIAL / GAP** | Depth/stencil + raster packets well decoded. Programmable-blend *requirement* is documented but the **blend/epilog microprogram codegen + register contract is not** (deliberately not disassembled) → you know you must compile blend into the FS but not how. |
| 4 | Descriptors (texture/sampler/buffer) | **PARTIAL / GAP** | Sampler (8B) and buffer PASS; texture 32B layout scheme PASS, but the **full per-format Channels/sizeclass table is not in `docs/`** (deferred to EXP-0015 RESULTS); render-target/PBE attachment descriptor only partially decoded (format byte + clear color). |
| 5 | Tiling (twiddle/mip/compression) | **PARTIAL / GAP** | 2D uncompressed twiddle, linear stride, mip packing = PASS. BC/ASTC block twiddle *inferred, not probed*; 3D/cube/array/MSAA layouts untested; compression codec opaque (documented disable-fallback exists). |
| 6 | TBDR / pipeline | **PARTIAL / GAP** | Tile size (32×32 fixed), imageblock budget, memoryless, MSAA *count* = PASS. Sample **positions** + **ZLS/depth store** punted to firmware without a userspace field contract; MSAA sample-interleave layout and occlusion-query mechanism absent. |
| 7 | Kernel-interface assumptions | **GAP** | Documented only as *macOS IOKit* black-box observations (selectors 8/7/9/11, ring +0x58/submit); the abstract "fields userspace hands down" contract, VA-space layout, and the actual doorbell store are missing/unknown → two teams cannot agree from this. |
| 8 | Cross-cutting (coherence, emulate-vs-native, magic values) | **GAP** | No coherency/waitgroup modifier documented; **native-vs-emulated capability matrix does not exist as a decided doc**; RT/mesh/matrix wholly undocumented; several unexplained magic values (see below); one firmware-vs-userspace contradiction on ZLS/sample positions. |

Only subsystems with a genuine "you could emit this today" core are **descriptors** (sampler/buffer)
and **tiling** (2D+mip) — and even those have blocking sub-gaps (format table; BC/3D/MSAA).

---

## Prioritized gap list (most-blocking first)

Each entry: **subsystem — the specific missing fact — severity — where `docs/` falls short.**

1. **Shader compiler — Scoreboard / async-completion (wait) model is completely absent.**
   **Severity: CRITICAL, silent-corruption.** There is *no* mention anywhere in `docs/isa` of
   scoreboard slots, async-instruction completion, `wait`/barrier-drain, or which ops are
   asynchronous. Mesa treats this as a hard correctness requirement (async = texture/load/store/
   atomic; "Must not exceed AGX_MAX_PENDING for correct results"). Without the slot count, the
   max-pending depth, the per-op async flag, and the wait-encoding, any shader that reuses the result
   of a memory/texture/atomic op will race. **Cite: `isa/README.md` memory (EXP-0012), atomics
   (EXP-0018), texture (EXP-0016) sections describe the *ops* but never their completion/wait
   semantics.** This is the single most dangerous omission because it fails without a fault.

2. **Shader compiler — Reciprocal / rsqrt / sqrt / sin / cos instruction sequences undocumented.**
   **Severity: CRITICAL, blocking.** `isa/README.md` (EXP-0013): "frcp/frsqrt/fsqrt/fsin/fcos are
   **multi-instruction Newton-Raphson** (0x29 estimate seed) — ⏳ follow-up." The estimate opcode, the
   refinement sequence, and the range-reduction for sin/cos are not given. Division, `normalize`, and
   trig appear in almost every real shader; you cannot emit them. **Cite: `isa/README.md`
   "Transcendental/round group" bullet.**

3. **Command stream — Graphics USC shader-entry word is explicitly opaque.**
   **Severity: CRITICAL, blocks all draws.** `cmdstream/README.md` states three times: "⏳ the exact
   graphics shader-entry word inside the USC blocks is not yet decoded" / "the exact graphics
   shader-entry pointer bit-encoding inside the USC block is still opaque." Compute binds via
   `shaderVA>>6`, but a draw binds VS/FS *indirectly through the USC program* whose entry encoding is
   unknown. No triangle can be drawn. **Cite: `cmdstream/README.md` "Graphics (draw) command stream"
   and "USC bind grammar" sections + Open items.**

4. **Shader compiler — Fragment varying interpolation not decoded.**
   **Severity: CRITICAL, blocks all interpolated/textured fragment shaders.** `isa/README.md` lists
   only byte-0 leaders for vtx/frag ops (`0x2f/0x3f/0xaf`, varying-stores `0x05/0x06/0x57`) with
   "⏳ lengths/semantics pending a decode experiment." Mesa needs real `iter`/`iterproj`/`ldcf`/
   `st_vary` encodings + the coefficient-register interpolation model (`<A,B,C>·<x,y,1>`). Perspective/
   flat/centroid/sample/pull-model are all unaddressed. **Cite: `isa/README.md` "Extraction & testbed
   … EXP-0008" bullet; `msl-feature-map.md` A17 marked blocked on fragment extractor.**

5. **Shader compiler — Special-register (SR) enum and preload ABI absent.**
   **Severity: HIGH, blocks most non-toy shaders.** `docs/` mentions `get_sr` (byte-0 low-nibble
   `0xC`, high nibble = SR-select) and that `thread_position_in_grid` is materialized, but gives **no
   SR number table** (thread_index_in_simdgroup, simdgroup_index, coverage_mask, backfacing,
   input_sample_mask, is_active_thread, threadgroup_position, threads_per_threadgroup, …) and **no
   preload register ABI** (which GPRs arrive preloaded: vertex_id/instance_id, VS attribute base,
   FS output/epilog register contract, link register, nesting counter). This is the missing
   `NEW: abi/` area from the requirements matrix. **Cite: `isa/README.md` control-flow (EXP-0010)
   preamble bullet; `mesa-userspace-requirements.md` §2a "Special registers" and §2g "Register/preload
   ABI".**

6. **ISA as a whole — the authoritative encoding is outside `docs/`, and many operand widths are ⏳.**
   **Severity: HIGH, structural.** `isa/README.md` defers "source of truth" to `tools/agx-isa/db.json`
   (out of bounds). Within the prose, register-field *widths* for the integer group are unresolved
   ("srcA/srcB packed in the b7:b8:b9 tail … exact widths a follow-up"); bitwise `0x0b`, compare-select
   byte-diff, shifts, popcount are `⏳` (inferred, not splice-validated); only fadd/fmul op-selects are
   HW-validated (sub/min/max/fma "use different formats (inferred)"). A register allocator + encoder
   cannot be written to the prose alone. **Cite: `isa/README.md` "Integer ALU family" and "How we get
   the bytes" note; the `⏳` markers throughout.**

7. **Descriptors — the full texture format table (Channels + sizeclass per pipe_format) is not in
   `docs/`.** **Severity: HIGH, blocks binding most textures/RTs.** `descriptors/README.md` gives the
   *encoding scheme* (`byte1 = numtype<<5 | sizeclass`, numtype codes) but says "(Full 31-format table
   in EXP-0015 RESULTS.)" — i.e. the actual channel-arrangement + sizeclass code for R8/RG8/RGBA8/
   R16F/RGBA32F/BC*/ASTC/etc. lives in the experiment, not the deliverable. Renderability per format
   and the render-target attachment format codes (only BGRA8=`0x0a`, RGBA8=`0x88` shown) are likewise
   absent. **Cite: `descriptors/README.md` "format numeric type + size" row; `cmdstream` attachment
   "pixel format byte @+0x22".**

8. **Command stream — PPP fixed-function header + emission-order grammar not documented.**
   **Severity: HIGH.** Individual `0x58000` packet offsets (depth `+0x38`, stencil `+0x3c`, raster
   `+0x70`) are decoded, but the **PPP present-bit header → sub-struct map and the fixed emission
   order** (Mesa's largest, most bit-fiddly 3D-state surface: viewport, cull, output-select, varying
   counts, region clip) is not. You cannot assemble a valid 3D state stream from disjoint offsets
   without the header/ordering. **Cite: `cmdstream/README.md` state-packet section; `mesa-userspace-
   requirements.md` §2b PPP row (gap #9).**

9. **Command stream — Compute threadgroup-memory-size field + CDM config word `+0x00` undecoded.**
   **Severity: HIGH, blocks compute with shared memory.** `cmdstream/README.md`: "⏳ threadgroup-memory-
   size field is elsewhere (not here)" and "`+0x00` shader config/register word … ⏳"; Open items list
   both. A compute shader using `threadgroup` memory (very common) cannot be dispatched correctly.
   **Cite: `cmdstream/README.md` "Compute launch (CDM) descriptor" + Open items.**

10. **Cross-cutting — Ray tracing, mesh/object, cooperative matrix: zero hardware documentation.**
    **Severity: HIGH for Vulkan (RT), scoping for the rest.** `msl-feature-map.md` Part B provides only
    MSL *provocation snippets* and self-declares "planning index, **not a hardware claim**." No AGX
    encoding exists in `docs/` for ray-intersect, acceleration-structure format, `ray_data` payload
    ABI, mesh-output buffer layout, grid amplification, or `simdgroup_matrix`. Metal caps report
    `supportsRaytracing=YES` (`hardware-overview.md` §3), so an A18 Vulkan port needs these — they are a
    **pure gap**. **Cite: `msl-feature-map.md` Part B intro + "open empirical question" notes.**

11. **Cross-cutting — Native-vs-emulated capability matrix does not exist as a decided document.**
    **Severity: HIGH (scoping), it steers how much emulation code is needed.** The requirements matrix
    calls for a `NEW: capabilities.md` deciding geometry/tessellation/transform-feedback/mesh/RT native
    vs emulated. `hypotheses.md` resolves several point capabilities (logic ops native, border color
    emulated, depth clamp native, blend programmable, fixed tile), but the **big structural
    emulate-vs-native boundaries (GS/tess/XFB/mesh)** are untested and undocumented. An implementer
    cannot decide whether to port the whole VS→compute emulation stack. **Cite: `mesa-userspace-
    requirements.md` §2g + §4 "Present-on-M1/M2-as-emulation → may become NATIVE".**

12. **State — Programmable-blend / epilog codegen mechanism is not documented (only its existence).**
    **Severity: MEDIUM-HIGH.** `cmdstream/README.md` (EXP-0019) proves blend is compiled into the FS
    and *deliberately does not* document the blend microprogram (clean-room rule 5). Correct, but that
    leaves the implementer without: the FS-epilog register contract (which reg holds each RT color / the
    loaded dst color), how RT format conversion is emitted, dual-source output-index encoding, and
    alpha-to-coverage. This is the missing epilog half of the `NEW: abi/` area. You are told *what* to
    do (compile blend in) but not the ABI to do it. **Cite: `cmdstream/README.md` "Blend is
    programmable" ⚠ box.**

13. **Kernel interface / memory model — no VA-space layout, no abstract hand-down contract, doorbell
    unknown.** **Severity: MEDIUM (lower priority per CLAUDE.md, but a real gap).** `docs/` documents
    the macOS IOKit surface only (selectors, ring producer index +0x58/submit) and explicitly cannot
    see the doorbell store ("invisible to this interposer"). Missing: the VA-space layout (robustness
    carveout, 4 GiB USC/shader window, zero/scratch pages), BO/bind alignment constraints, and the
    field-set (`drm_asahi_cmd_render`/`cmd_compute`-shaped) that userspace must hand the *Linux* kernel
    team. There is no `NEW: memory-model` doc. **Cite: `cmdstream/README.md` submission/ring sections;
    `mesa-userspace-requirements.md` §2f (gaps #11–12).**

14. **Tiling — block-compressed (BC/ASTC/ETC) twiddle inferred-only; 3D/cube/array/MSAA untested.**
    **Severity: MEDIUM.** `tiling/README.md` §1.5: BC twiddle over block coords is "*inferred, not
    probed*"; §4.5: "3D/array/cube/MSAA twiddle are untested." BC/ASTC are ubiquitous. Sampling a
    compressed or a volume/cube/array texture cannot be laid out with confidence. **Cite:
    `tiling/README.md` §1.5, §4.5.**

15. **Pipeline — MSAA sample-interleave layout + occlusion/visibility query mechanism absent.**
    **Severity: MEDIUM.** `pipeline/README.md` gives the MSAA *count* encoding and says the color
    descriptor relocates to the tiler heap under MSAA, but the *spatial sample interleave within a
    tile* (needed to read/resolve MSAA) is not given; and there is no documentation of the visibility/
    occlusion-counter mechanism (heap, `visibility_mode`, `isp_oclqry_base`) that Mesa needs for
    occlusion queries and conditional render. **Cite: `pipeline/README.md` MSAA section; absence of any
    query doc; `mesa-userspace-requirements.md` §2e occlusion row.**

(Additional, lower-severity: sample-position firmware path (documented as kernel-routed but no
contract); ZLS/depth store control (firmware — see contradiction below); timestamp period unknown;
1D/CubeArray/MSArray texture types ⏳; register hints / 32-64b alignment rules; UVS/varying linkage
group order; occupancy/cycle model (perf-only).)

---

## Contradictions & unexplained magic values found

**Contradiction / unresolved boundary — ZLS and sample positions: firmware or userspace?**
`pipeline/README.md` states depth store-action/ZLS and programmable sample positions are
"firmware-managed … route via kernel," implying they are *not* a userspace responsibility. But the
requirements matrix (`mesa-userspace-requirements.md` §2b/§1) documents that in the Mesa/Linux model
these very fields (ZLS control, ISP scissor/merge, tilebuffer sizing, sample control) are **filled by
userspace** in `drm_asahi_cmd_render` even though they cross the UAPI. The two docs disagree on which
side of the boundary these live, and `docs/` never reconciles them into a concrete "userspace fills
field X, firmware owns Y" contract. **This must be resolved before the kernel and userspace teams can
agree** — exactly the coordination the gate is meant to guarantee.

**Unexplained / unpinned magic values (each should be explained or at least bounded):**
- `cmdstream` CDM launch `+0x00` config word: `0x00080000 → 0x00880000` for a register-heavy shader —
  **⏳, meaning not decoded** (only the isa doc's occupancy-tier bit 23 partially explains bit 23).
- `cmdstream` USC graphics stage blocks each "led by config word **`0x00880000`**" — unexplained magic
  (and coincides with the CDM value above — is that significant? undocumented).
- `pipeline`/`cmdstream` store-program id **`0x6f`** in the attachment store segment — magic, no decode.
- `cmdstream` VDM indexed-draw opcode switch **`0x61c4 → 0x61f2`** — observed, not explained (what do
  the bits mean? which is the base VDM draw opcode?).
- `cmdstream` attachment descriptor is "chained **0x300-byte** segments (load/render/store)" — segment
  count/meaning only partially assigned; `pipeline` adds clear-enable bit24 @seg+0x168 but the segment
  grammar is ⏳.
- `hardware-overview` accel-node config `num_gps=2`, `num_frags=6`, `is_sksm=1` — raw values,
  "semantics unconfirmed"; `kickid_qid_shift=40 / _mask=127` used but not tied to any emitted field.
- `descriptors` sampler `lodMax` "default 14.0", aniso field "3-bit log2 → up to 128×" while Metal
  caps 16× — a documented *unprobed* capability (probe candidate), fine, but flag it's unverified >16×.

None of these are fatal individually, but per the CLAUDE.md corollary ("every 'magic value' must be
explained or at least pinned down"), they are open items the gate should not wave through.

---

## What is genuinely solid (so the RE team keeps it)

- Machine model: 96 GPRs, 2 halves/GPR, uniform register file + uniform program, spill-to-scratch
  (`isa` EXP-0020) — clear and validated.
- Float/int ALU 2-src operand encodings, minifloat immediate, integer immediate — HW-validated.
- Control-flow shape: predication vs real backward jump (`0f 00 54 <off6>`), loop back-edge — good.
- Memory family `0x67/0xe7` field layout + element-addressing model — good.
- Atomics op-code table (EXP-0018), subgroup/quad groups, SIMD width = 32 — good.
- Sampler (8B) + buffer descriptors; texture descriptor *scheme*; twiddle/mip/linear layout;
  compression *wiring* (with disable-fallback) — good.
- Depth/stencil + rasterizer packets; the **programmable-blend structural finding** (huge for a Mesa
  port); tile size 32×32 fixed (don't port G13 shrink-tile) — high-value, correct deltas.
- The honest `⏳`/negative-result discipline and `hypotheses.md` register — exactly right; the gaps
  above are *known* to the team, just not yet closed.

**Bottom line for steering the remaining RE:** close #1–#5 first (scoreboard, transcendentals,
graphics shader-entry, fragment interpolation, SR/preload ABI) — those are the difference between
"runs an add kernel" and "runs a shader / draws a triangle." Then #6–#9 (finish the ISA operand
widths & migrate the DB's truth into `docs/`, the format table, PPP grammar, compute shared-mem
field). #10–#11 (RT/mesh/matrix + the native-vs-emulated matrix) gate Vulkan feature scope. Fold the
`tools/` DB and `experiments/*/RESULTS.md` format table **into `docs/`** — as written, the gate
cannot pass while the "source of truth" lives outside the deliverable directory.
