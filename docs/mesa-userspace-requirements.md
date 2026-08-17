# Mesa Userspace Requirements — the A18 Pro (G17P) documentation surface

**Purpose.** This is the master checklist for the clean-room effort. It surveys Mesa's existing
**Asahi userspace driver** (the MIT-licensed M1/M2 = G13/G14 driver in `../mesa/src/asahi` and
`../mesa/src/gallium/drivers/asahi`) and enumerates, module by module, every piece of
**A18-hardware-specific knowledge** a userspace port depends on. Each such thing is something our
`docs/` must supply before the acceptance gate (see `../CLAUDE.md` → Definition of Done) can pass:
a from-scratch A18 Mesa port must be implementable from `docs/` alone.

**Provenance / clean-room note.** Everything below was derived by **reading open-source Mesa**
(explicitly allowed — Mesa is the driver we target, not an Apple binary) plus the public
`gpu_knowledge/` references. No Apple binary was disassembled. All `file:line` citations point into
`../mesa`. This file records *what must be documented*; the *values* come later from our own
experiments (hardware probing, own-shader disassembly, data tracing) and land in the `docs/` areas
named in the matrix.

> How to read the matrix "Owning docs/ area": `isa/`, `cmdstream/`, `descriptors/`, `tiling/`,
> `pipeline/`, `hardware-overview.md` are the areas from `../CLAUDE.md`. `NEW:` marks a doc area we
> do not yet have a home for and should create. **Status** is prefilled from what exists in `docs/`
> today (only `hardware-overview.md` and the `isa/README.md` seed). **RE effort** S/M/L is how much
> reverse-engineering re-deriving that fact for A18 implies.

---

## 1. The M1/M2 userspace ↔ kernel split (the model we are documenting)

On G13/G14, **userspace (Mesa) owns essentially all GPU programming**; the kernel is a thin,
security-focused submission-and-memory broker. Userspace: (1) compiles shaders to AGX machine code
and links them with fast-link **prolog/main/epilog** stitching; (2) builds the three hardware
**control streams** — **VDM** (Vertex Data Master → tiler/"TA" work), **CDM** (Compute Data Master →
compute/"CL" work), and the **PPP** fixed-function state records they reference — word by word in GPU
memory; (3) packs all **descriptors** (24-byte TEXTURE/PBE, 8-byte SAMPLER, BORDER) and **USC**
binding words (the little "pipeline" program the shader core runs to bind uniforms/textures/samplers/
the shader before launch); (4) computes all **texture memory layout** (Morton/twiddle tiling, mip
trees, lossless-compression metadata) so the fixed-function texture/PBE units can address it; (5)
lays out its own **uniform/register ABI** (which GPRs are preloaded, which uniform registers hold
each sysval); and (6) manages the **GPU virtual address space** (carving a 4 GiB USC/shader window, a
robustness zero page, per-core scratch/spill buffers) and hands the kernel bind requests. The
**kernel** (Linux `drm/asahi`; on macOS the AGX kext + firmware) exposes a VM/Queue/Bind/Submit UAPI
(`../mesa/include/drm-uapi/asahi_drm.h`), reports read-only **hardware parameters**
(`drm_asahi_params_global`: `gpu_generation`, `gpu_variant`, `num_clusters_total`,
`num_cores_per_cluster`, `core_masks[]`, `vm_start/vm_end`, `command_timestamp_frequency_hz`, feature
bits like `SOFT_FAULTS`), and translates userspace's control streams into the actual
firmware-command pairs (vertex+fragment for render, with permeable barriers for partial renders).
Crucially, because the firmware command structs are unsafe to expose, the kernel wraps them
(`drm_asahi_cmd_render`/`cmd_compute`) — so a handful of "render command" fields (ZLS control, ISP
scissor/merge, tilebuffer sizing, sample control, timestamps) are also a userspace responsibility
even though they cross the UAPI boundary. **For A18 the split is assumed identical in shape;** the
kernel is out of scope here, but every field userspace must hand down is in scope as an
"interface note."

Generation is threaded through the driver as `dev->chip ∈ {G13G, G13X, G14G, G14X}`
(`../mesa/src/asahi/libagx/libagx_dgc.h:216`), selected from `gpu_generation` + `num_clusters_total`
(`../mesa/src/asahi/lib/agx_device.c:662`). **There is no G15/G16/G17 path anywhere** — A18/G17P is
entirely out-of-tree. The generation leaks into surprisingly few C branches (a handful of barrier
bits, one extra CDM word, an atomic-coherency bit); the real per-generation content is concentrated
in the **encoding tables** (ISA `AGX2.xml`, `genxml/cmdbuf.xml`) and the **layout math** — which is
exactly what our `docs/` must re-derive.

---

## 2. Coverage matrix

Columns: **Subsystem | Mesa location | A18 hardware facts required | Owning docs/ area | Status | RE effort | Notes**.
Status ∈ {not-started, partial, done}. Effort ∈ {S, M, L}.

> **Coverage summary (synced 2026-07-07 against `docs/`):** **done 5 · partial 39 · not-started 8** (of 52 rows).
> The 8 still **not-started** are the real remaining gaps: fragment-only ISA ops (2a), NIR-lowering HW-workaround
> facts (2a), UVS/varyings linkage (2b), device-generated indirect commands (2b), MSAA sample interleave in memory
> (2d), sparse page-table/folio geometry (2d), occlusion/visibility counters (2e), timestamps (2e). Most rows are
> **partial** — covered with named ⏳ gaps rather than fully closed. Status cites the owning doc §; ⏳ marks the gap.

### 2a. Shader ISA & compiler backend

| Subsystem | Mesa location | A18 hardware facts required | Owning docs/ area | Status | RE | Notes |
|---|---|---|---|---|---|---|
| Instruction encodings (opcode + operand bit-fields, variable length) | `isa/AGX2.xml`, `compiler/agx_opcodes.py`, `compiler/agx_pack.c` | Exact opcode values & scattered operand bit positions for ~80 ops (ALU `iadd/imadd/fadd/ffma/hfma`, funops `rcp/rsqrt/log2/exp2/sin_pt_1/2`, converts, bitfield); short/long forms + length bit | `isa/` | partial (isa/README EXP-0005/0006/0007/0012/0013 — float/int/mem ALU HW-validated; ⏳ full opcode table lives in `tools/agx-isa` not `docs/`, integer logic/compare/shift byte-diff-only, NR transcendentals) | L | The dominant task. Named "AGX2" (G13/G14); G17P likely a new revision — assume the whole table moves. `isa/README.md` has preliminary byte-level observations only. |
| Register-file model | `compiler/agx_compiler.h:23`, `agx_pack.c` | 128×32-bit GPRs = 256 half-regs (`AGX_NUM_REGS=256`), half-reg addressable, 32/64-bit alignment rules; register hint enum none/cache(`$`)/discard(`^`) | `isa/` | partial (isa/README "Machine model" EXP-0020 — 96 addressable GPRs, half-addressable 2/GPR, Dynamic-Caching spill; ⏳ register-hint enum, 32/64-bit alignment rules) | M | GPR count/occupancy could differ on A18 (Dynamic Caching). Load-bearing for the register allocator. |
| Uniform-register file | `compiler/agx_compiler.h:27`, `agx_lower_uniform_sources.c` | 512 half-uniforms (`AGX_NUM_UNIFORMS=512` = u0–u255); who can read uniforms, low-half-only for memory ops, no 64-bit-uniform ALU reads | `isa/` + `NEW: abi/` | partial (isa/README EXP-0010/0020 — uniform register file + per-source GPR-vs-uniform mode bit + `uniform_mov`; ⏳ exact count, docs say ≤128) | M | |
| Minifloat immediate | `isa/agx_minifloat.h` | 8-bit 1-sign/3-exp/4-mant, bias 7, denormal-as-zero special case, `agx_negzero()=0x80` | `isa/` | done (isa/README "Packed float immediate" EXP-0006 — 8-bit minifloat 4-exp/3-mant bias-11, sign at bit19, normal/subnormal formulas, 16 constants HW-validated; note A18 differs from G13's 3-exp/4-mant) | S | Small; probably unchanged but must be verified against real encodings. |
| Scoreboard / hazard model | `compiler/agx_insert_waits.c:10`, `agx_opcodes.py` (SCOREBOARD class) | 2 scoreboard slots, `AGX_MAX_PENDING=8` outstanding/slot, which ops are async (load/store/tex/atomic), barrier-drains-all rule | `isa/` + `pipeline/` | partial (isa/README "Async completion" EXP-0025 — G17P has NO software scoreboard; RAW hazards handled by a HW register interlock (no `wait` op, no AGX_MAX_PENDING); ⏳ fragment/tilebuffer ordering analogue) | M | Slot count/depth are microarchitectural; must re-derive on A18. Wrong values = corruption. |
| Special registers | `isa/AGX2.xml:715`, `compiler/agx_compile.c:104` | `sr` enum numbers: thread_index_in_simdgroup=52, simdgroup_index=53, internal_coverage_mask=60, backfacing=62, is_active_thread=63, input_sample_mask=124, helper_op=144, … + preload regs r4/r5/r6 | `isa/` + `NEW: abi/` | partial (isa/README EXP-0010 — `get_sr` mechanism (byte0 low-nibble 0xC, hi-nibble = SR-select); ⏳ SR-number enum table + preload-reg map not tabulated) | M | |
| Texture/image instruction encodings | `isa/AGX2.xml:1583`, `compiler/agx_pack.c:857`, `compiler/agx_nir_lower_texture.c` | `smp`(sample), texture/sampler/coord/lod/zs operand encodings; `dim`/`gather`/`lod_type`/`format` enums; image-store RAW-ordering bit 43; cache-control nibble `q3=0xc` | `isa/` | partial (isa/README "Texture / sample family" EXP-0016 — sample/read/write(0xd7)/query/derivative encodings + dim/LOD-mode/slot fields HW-validated; ⏳ result/coord register bit decode, `sample_compare`, array/3D/cube/MSAA index-operand positions) | L | 30 KB of texture quirks. See divergence §4 (buffer→2D-1024, RGB32 emulated, cube imageLoad erratum). |
| Fragment-only ops | `isa/AGX2.xml:1553`, `agx_pack.c:561` | `iter/iterproj/ldcf` (varying interpolation), `ld_tile/st_tile`, `sample_mask`, `zs_emit`, `st_var` encodings + ordering rules | `isa/` | not-started | M | |
| Subgroup/quad ops | `isa/AGX2.xml:1487`, `compiler/agx_nir_lower_subgroups.c`, `agx_lower_divergent_shuffle.c` | Subgroup width **32**; shuffle(+xor/up/down, quad); `simd_op` reduction subop enum (and=0,fadd=1,iadd=16,smin=20…); ballot 32-bit; quad-accumulate shuffle hazard (reserves r0h=0) | `isa/` | partial (isa/README "Subgroup / SIMD-group" EXP-0018 — SIMD width 32, `simd_reduce`/scan/`simd_shuffle`/`simd_ballot`/quad-op encodings HW-validated, prefix-scan native; ⏳ complete reduction-subop enum) | M | Which reductions/scans exist natively vs must be lowered. |
| Memory / atomic ops | `isa/AGX2.xml:1466`, `agx_pack.c:703`, `agx_nir_lower_address.c` | `load/store/atomic/local_*/stack_*` field layouts; `coherency` 2-bit + `waitgroup` scoreboard modifier; atomic-op enum; addressing mode (base+index<<shift, max shift=fmt_shift+2); barrier magic-constant table | `isa/` | done (isa/README "Memory access family" EXP-0012 + "Atomics" EXP-0018 — 0x67/0xe7 14-byte load/store field map (space/base_slot/count/width/elem_size), element addressing, native single-RMW atomic op-code table incl. fadd, HW-validated) | L | Barrier constants' individual meanings are unknown even on G13. |
| Control-flow encodings | `isa/AGX2.xml`, `compiler/agx_compile.c` | `if/else/while_icmp/_fcmp`, `jmp_exec_*`, `pop_exec`, `break`, nesting-counter (r0l) immediate; cross-workgroup barrier opcode *sequence* | `isa/` | partial (isa/README "Control flow" EXP-0010 — predication (compare→mask→select), backward-jump loops `0f 00 54 <off6>`, 0x0f group sub-ops (jump/push/else/pop), program termination, `threadgroup_barrier` HW-validated; ⏳ while_icmp/_fcmp forms, nesting-counter r0l immediate) | M | Barrier sequence "observed on G13D" — empirically RE'd, re-check A18. |
| Occupancy & cycle model | `compiler/agx_performance.c:16` | Halfregs→max-threads occupancy table `{104→1024 … 256→384}`; per-op unit/latency/throughput (F32/F16/SCIB/IC) | `isa/` + `pipeline/` | partial (isa/README EXP-0020 — coarse ~12-GPR occupancy tier (config bit23) + 96-GPR spill threshold; gap: no full halfregs→max-threads occupancy curve, no per-op latency/throughput/cycle model) | M–L | Explicitly "for G13G". Perf-only (wrong = slow, not broken); needs microbenchmarking. |
| Register allocation & spill | `compiler/agx_register_allocate.c`, `agx_spill.c`, `agx_scratch.c` | Register classes (GPR vs MEM/stack), occupancy↔register-count coupling, spill "stack" block mechanism (doorbell, see helper program below) | `isa/` + `NEW: memory-model` | partial (isa/README EXP-0020 — 96 GPRs then spill to per-thread scratch (stack), scratch size in `__GPU_METADATA`, spilled kernels HW-validated; ⏳ scratch-base location, per-core geometry + doorbell/stack-map mechanism (see 2e)) | M | Algorithm is portable; the numeric register model + per-core scratch geometry are A18-specific. |
| NIR lowering quirks (hardware workarounds) | `compiler/agx_nir_lower_*.c` | Each pass encodes a HW fact: interpolation via coefficient regs `<A,B,C>·<x,y,1>`; fmin/fmax denorm-flush canonicalization; depth=NEVER→NaN forced late-Z; shared-mem 16-bit offsets; "no float modifiers on G13"; cull-distance re-expression | `isa/` + `pipeline/` | partial (EXP-0047: M4 authored Metal source paths show fp32 DAZ/FTZ-like arithmetic, fp16 subnormal preservation, and operand-B min/max ties; not native-op isolation or A18 validation) | M | Each remains a candidate A18 divergence (see §4); finish with native-op tests and the other lowering predicates. |

### 2b. Command / control stream & state packets

| Subsystem | Mesa location | A18 hardware facts required | Owning docs/ area | Status | RE | Notes |
|---|---|---|---|---|---|---|
| Pack/encoding framework | `genxml/cmdbuf.xml`, `genxml/gen_pack.py`, `genxml/agx_pack_header.h` | 84 structs / 37 enums; `modifier` semantics: `shr(n)`, `minus(1)`, `groups(N)` where **0-encoding = "all"**, `log2`; 25 `exact=` magic/opcode constants; 4:6 fixed-point LOD pack | `cmdstream/` | partial (encoding conventions — shr units (`VA>>4`, `shaderVA>>6`), length-word-vs-present-mask — documented across cmdstream/descriptors/tiling; gap: no consolidated genxml-style struct/enum framework doc) | M | Single **un-versioned** XML — per-gen deltas are in C, not XML. 64 RE'd `unk/reserved` bits to re-verify. |
| VDM (draw/tiler stream) | `cmdbuf.xml` VDM* structs, `libagx/libagx_dgc.h:272`, `gallium/.../agx_state.c:3469` | Block-type = bits 29-31; `VDM Block Type` enum; State/Index-List presence-bit ordering; Pipeline addr shr(6); `Index List` (primitive/index-size/restart), `Vertex Shader Word 0/1`, `Vertex Outputs`, `Restart Index` | `cmdstream/` | partial (cmdstream/README EXP-0014/0024 — VDM at 0x18000, draw record primitive@+0x65/vertexCount@+0x68/instanceCount@+0x6c/index-VA@+0x70 HW-correlated, USC bind-pairs, PPP length word; ⏳ full VDM bit-decode, tessellation sub-words) | M | Core draw path well understood; **tessellation sub-words explicitly "guessed" ordering (L)**. |
| CDM (compute stream) | `cmdbuf.xml` CDM* structs, `libagx_dgc.h:224`, `agx_state.c:5340` | Block-type enum; `CDM Mode` (direct/indirect global/local); Launch Word 0/1 register counts; `CDM Indirect` (addr shr 2), Global/Local size; **`CDM Unk G14X`** conditional word; CDM Barrier ~24 unk bits | `cmdstream/` | partial (cmdstream/README EXP-0011/0024 — direct CDM launch record HW-validated: shader ptr@+0x08=`shaderVA>>6`, grid@+0x10/tg@+0x1c in threads, config bit23=occupancy tier; ⏳ indirect global/local mode, CDM barrier bits, per-gen extra word) | M | The G14X extra word is the canonical per-gen insertion → **highest-signal thing to re-check on A18 (S once a capture exists)**. |
| PPP (fixed-function 3D state) | `cmdbuf.xml` (25-bit PPP Header + ~15 sub-structs), `lib/agx_ppp.h`, `agx_state.c:3423` | PPP Header present-bit → struct map & **fixed emission order**; Fragment control/control-2 (tag_write_disable quirk), Fragment face/face-2/stencil, Region clip (32×32-tile granular), Viewport (clip→NDC), Output Select (16 clip planes+psiz/layer/vp/rt selects), Varying Counts, Cull/Cull-2, Depth bias (×2 units), FS Word 0-3 | `cmdstream/` + `pipeline/` | partial (cmdstream/README EXP-0019/0024 — depth/stencil + rasterizer packets HW-validated (compare/op/cull/winding/depth-clip/line-fill/depth-bias), header=monotonic length word not present-mask, per-group enable bits; ⏳ output-select/16 clip planes, varying counts, region clip, fragment control/control-2, FS Word 0-3) | L | Largest, most bit-fiddly surface; many unknown bits. Enums: Object Type, Shade model, Pass type. |
| USC binding words | `cmdbuf.xml:640` (USC Control enum), `lib/agx_usc.h`, `libagx_dgc.h:531`, `agx_state.c:2872` | Tag magic bytes: Preshader=0x38, FragProps=0x58, NoPreshader=0x88, Shader=0x0d, Uniform=0x1d, UniformHigh=0x3d, Shared=0x4d, Registers=0x8d, Sampler=0x9d, Texture=0xdd; Uniform start/size in **halfs**, buffer shr 2; Texture/Sampler count/buffer split (unknown even on M1/M2); Registers count groups(8); Preshader magic `0xc08000`; addresses **relative to `shader_base`** | `cmdstream/` + `NEW: abi/` | partial (cmdstream/README EXP-0019/0024 — USC program 0x10000130000 = three per-stage uniform-preamble programs (config `0x008800XX`, uniform-data ptrs, slot ids); ⏳ tag-magic-byte table (Shader/Uniform/Texture/Sampler…), Texture/Sampler count↔buffer split) | M | Compact, high-value; a Metal capture reveals tags quickly. |
| UVS / varyings linkage | `lib/agx_uvs.h`, `lib/agx_nir_lower_uvs.c`, `cmdbuf.xml` CF binding | Hardware group order POSITION/VARYINGS/PSIZ/LAYER_VIEWPORT/CLIP_DIST; varying-count (smooth/flat/linear) encoding; CF binding coefficient-register layout + Coefficient-source/Shade-model enums | `cmdstream/` + `pipeline/` | not-started | M | VS-outputs word ↔ FS Output-Select ↔ CF bindings are coupled. |
| ZLS / CR render-command control | `lib/agx_helpers.h:114`, `cmdbuf.xml` ZLS/CR, `agx_pipe.c:1222`, `hk_queue.c:106` | ZLS Control (Z/S load/store tiling+compress+resolve, ZLS Format/Tiling enums); CR ISP ZLS Pixels; CR PPP Control (GL clip, W-clamp, fixed-point format=1); depth/stencil **stride in pages**, meta stride in **cachelines**; `isp_merge_upper = tan(60°)/dim`; `isp_bgobjvals=0x300`, `ppp_ctrl=0x202` | `cmdstream/` + `pipeline/` | partial (kernel-interface.md §6.1 — `drm_asahi_cmd_render` field set (`zls_ctrl`, `depth`/`stencil`, `isp_zls_pixels`, `isp_merge_upper`, clears) + firmware boundary decided (G-11 reconciled); A18 ZLS-Control bit encoding not RE'd — firmware-managed, values carried from Mesa) | M | These live in `drm_asahi_cmd_render` — a UAPI boundary that gets a G17 revision. |
| Background / EOT programs | `lib/agx_bg_eot.c/.h`, `agx_state.c:3053` | bg=fragment (load/clear each RT), eot=compute (`image_store_block` at tile offset); clear values from preamble; bg/eot USC ptr low-3-bits carry flags (`& ~0x7`) | `pipeline/` | partial/open (EXP-0048: M4 empty Clear/Store and Load/Store behavior repeats exactly, but all four allowlisted state BOs are identical between those empty passes; no BG/EOT tag, resource spec, ABI, or `0x6f` ownership located. Earlier single-RT value `0x6f` remains an observation, not a firmware-ownership proof.) | S | Unchanged UAPI requires userspace records; generate programs from tilebuffer/USC facts rather than guessing or inspecting Apple code. |
| Device-generated commands (indirect draw/dispatch) | `libagx/libagx_dgc.h`, `libagx/draws.cl` | GPU-side emission of VDM/CDM words: barrier bit tables per chip, stream link/call/return, index robustness path | `cmdstream/` | not-started | L | Every barrier/launch bit is chip-versioned — guaranteed A18 work. |

### 2c. Resource descriptors

| Subsystem | Mesa location | A18 hardware facts required | Owning docs/ area | Status | RE | Notes |
|---|---|---|---|---|---|---|
| TEXTURE descriptor (24 B) | `cmdbuf.xml:283`, `gallium/.../agx_state.c:638`, `hk_image_view.c:260` | Full bit layout: Dimension(0:4)/Layout(4:2)/Channels(6:7)/Type(13:3)/Swizzle RGBA (3-bit each)/Width-1(28:14)/Height-1(42:14)/First+Last level/Samples(64)/Address(66:36 shr4)/Unk-mipmapped(102)/Compressed(103)/Mode(104:2)/Compression(106:2)/sRGB/Stride or Depth/Extended(127) + extended word (acceleration buffer / linear depth+layer-stride / buffer size+offset) | `descriptors/` | done (descriptors/README + descriptors/format-table.md EXP-0015/0017 — full **32-byte** layout: type/format code/swizzle/width/height/`VA>>4`/sRGB/depth-array/mip+compression flags, complete 31-format code table, HW-validated; note A18 desc is 32 B not 24 B) | L | Highest-value descriptor RE. `Channels` enum is a large HW format table. `Unk mipmapped` is an RE'd unknown. |
| PBE (image-write) descriptor (24 B) | `cmdbuf.xml:224`, `agx_state.c:1131` | Like TEXTURE but 2-bit swizzles, Address(64:36 shr4), Level/Levels-1/Layers-1, render-only Rotate90/Flip/Samples/Mode; SW sideband at bits 128+ (level offset, aligned-width-MSAA, sample-count-log2, tile w/h log2, layer stride) | `descriptors/` | partial (EXP-0048 repeats M4 0x20-byte MRT LOAD/STORE-PBE records for five formats plus mixed MRT; low-40 packed address reconstructs target VA, dimensions decode 32x32, sRGB changes upper control; actions/blend leave PBE unchanged. Still need full fields, dimensions, samples/layers/mips/resolve/memoryless/compression/D/S and Linux packing.) | L | Bounded DATA-TRACE structure, not a general packer; SW sideband remains a driver convention in HW-free bits. |
| SAMPLER descriptor (8 B) | `cmdbuf.xml:355`, `agx_state.c:514`, `hk_sampler.c:136` | Min/Max LOD **4:6 fixed-point** (clamp 0..14.0=0x380); anisotropy log2; Magnify/Minify/Mip filter; Wrap S/T/R enum (ClampEdge/Repeat/Mirror/ClampBorder/ClampGL/MirrorClampEdge); Pixel-coordinates; Compare func (**reversed** enum Lequal=0..Never=7); Border colour enum; Seamful cube; `Sampler states` compact/extended count encoding | `descriptors/` | done (descriptors/README + format-table.md §4 EXP-0015 — full **8-byte** layout: LOD min/max fixed-point, aniso log2, mag/min/mip filters, address-mode table, compare-func (sense+test) table, border-color presets, unnormalized, HW-validated) | M | Note reversed compare-func vs ZS-func enum. |
| BORDER descriptor (16 B) | `cmdbuf.xml:372`, `lib/agx_border.c` | Format-dependent custom border color: per-channel own 32-bit word, encoded as-if-in-memory; **sRGB→+4 bits (12-bit)**; compressed-format channel sizes special-cased (RGTC 14-bit, ETC2 R11 11-bit, BCn 8/12) | `descriptors/` | partial (descriptors/README + format-table §4c EXP-0015 — decided: NO arbitrary-border descriptor on A18, sampler carries only a 2-bit 3-preset field (transparent/black/white) → Vulkan custom border must be emulated; no separate custom-border format seen in captures) | M | Custom border needs 2 sampler planes (see §4). |
| Vulkan descriptor-set model (bindless) | `hk_descriptor_set.h`, `hk_nir_lower_descriptors.c` | Sampled-image=64 B (`agx_texture_packed`+`agx_sampler_packed`+heap index+lod_bias_fp16+min_lod_fp16+border[4]); storage-image=48 B (tex+pbe); buffer=16 B (64-bit-bounded-global, `.w=0` invariant); `AGX_TEXTURE_DESC_STRIDE=24`; sampler heap index bias=28; texture-state regs cap=16; sampler heap size=1024 (fw limit) | `descriptors/` | partial (cmdstream/descriptors EXP-0011/0015 — HW Tier-2 argument-buffer/bindless substrate documented: 8-B slot per resource, textures/samplers = pointer to descriptor block, buffers = inline 8-B VA; gap: Vulkan descriptor-set packing sizes/order (driver convention) not specified) | M | Bindless indexing is portable; the packed sizes/field-order must match A18 genxml exactly. |

### 2d. Texture / image memory layout (tiling & compression)

| Subsystem | Mesa location | A18 hardware facts required | Owning docs/ area | Status | RE | Notes |
|---|---|---|---|---|---|---|
| Morton/twiddle tiling order | `layout/tiling.cc:15`, `layout/layout.h:252` | Z-order interleave `[y6][x6]…[y0][x0]`, rectangular NxN/2NxN up to 128×128; `(X-mask)&mask` increment idiom; `ail_space_bits/mask` | `tiling/` | done (tiling/README §1.1 EXP-0017 + **RT-3 correction** — twiddle = **row-major grid of Morton tiles**, tile edge **T = largest pow2 with T²·bpp≤16KiB** (bpp1→**128**; EXP-M4-06); `element = (ty·cols+tx)·T² + morton_D(x&(T−1), y&(T−1))`, **`cols = round_up(ceil(W/T), G)`, G=0x4000/(T²·bpp)** (16KiB-row granule, not flat ceil); GF(2) HW-validated 0 mismatch incl. non-pow2 widths 192/300/384/448/576) | S | Core HW fact; load-bearing. RT-3 supersedes the earlier `morton(x,y)·bpp` / one-block model. |
| Tile-size table (per 16 KiB page) | `layout/layout.c:35` | tile dims so `w_el·h_el·blocksize=16384`: 1B→128×128 … 16B→32×32 … 64B→16×16; page=`AIL_PAGESIZE=0x4000`, cacheline=`0x80` | `tiling/` | partial (tiling/README §1.1 EXP-0017/RT-3 — A18 tiling is a **row-major grid of Morton tiles**, tile edge **T = 64 bpp≤4 / 32 bpp≥8** (RT-3, bpp-DEPENDENT — supersedes both G13's per-format table AND the earlier "whole texture is one Morton block" claim); compression metadata uses 16×16-tile / 8×4-block granularity) | S | Tied to 16 KiB page (A18 also 16 KiB) → should carry over; verify. |
| Two-tier mip tree | `layout/layout.c:70` | "large" page-tiled levels + POT miptree from `pot_level`; compressed "round-then-minify" vs uncompressed "minify-then-round"; miptail, page-aligned-layers, cacheline pad between levels | `tiling/` | partial (tiling/README §3 EXP-0017 — mip levels packed consecutively, each independent pow2-padded Morton plane, 0x80 min slot, offset formula HW-validated (128×128 + 96×96); ⏳ compression×mipmap interaction + array/layer packing untested) | M | Subtle corner cases; must match A18 texture unit exactly. |
| MSAA sample interleave | `layout/layout.h:305` | sample_count 4 doubles width, ≥2 doubles height (samples packed spatially into tile) | `tiling/` + `pipeline/` | not-started | M | |
| **Lossless compression metadata** | `layout/layout.h:463`, `layout/layout.c:268`, `libagx/compression.cl` | 8 bytes metadata per 16×16 tile, fully twiddled, cacheline-aligned, allocated only ≥16px; per-8×4-subtile 8-bit **mode bytes** (UNCOMPRESSED_*=0x1f/3f/7f/ff, SOLID_*=0x60/01/03/07); "seems to depend on format"; SWAR ×0x0101010101010101; acceleration-buffer layout | `tiling/` (or `NEW: compression`) | partial (tiling/README §4 EXP-0017 — trigger (no ShaderWrite AND ≥16×16), descriptor flags (word1 bit27/word3 bit31/secondary VA), aux placement + size (**numTexels/32** = 1 byte per 8×4 block; image/128 only at bpp4 — EXP-M4-07), per-block state bytes (0x03/0x15/0x7f) in Morton-of-blocks HW-validated; ⏳ block **codec** + state-value meaning opaque — documented disable-fallback) | L | **Single biggest RE unknown.** Already RE-uncertain on G13; Apple revises compression across generations — do NOT assume it carries over. |
| Per-format HW table | `layout/formats.c:20` | `ail_pixel_format[]`: pipe_format → Channels code, Texture Type, texturable flag, PBE-renderable format; which formats renderable/compressed-class | `tiling/` + `descriptors/` | partial (descriptors/format-table.md §2 EXP-0015 — 31-format → (byte0/byte1) code table + numtype/sizeclass/channel-arrangement decode done; ⏳ per-format renderable/PBE-renderable + compressed-class flags, many formats untested — see format-table §8) | M | Renderability & format codes must be re-validated per A18 (Apple adds/changes formats). |
| Sparse page-table geometry | `layout/layout.h:588` | `AIL_SPARSE_ELSIZE_B=4`, `AIL_PAGES_PER_FOLIO=256`, image-bytes/folio=4 MiB; DRM modifiers TILED / TILED_COMPRESSED | `tiling/` + `NEW: memory-model` | not-started | M | Page-size dependent; re-derive if A18 folio geometry differs. |

### 2e. TBDR pipeline, compute & tile model

| Subsystem | Mesa location | A18 hardware facts required | Owning docs/ area | Status | RE | Notes |
|---|---|---|---|---|---|---|
| Tilebuffer sizing | `lib/agx_tilebuffer.c:11` | `MAX_BYTES_PER_TILE=32768-1` ("on G13G, may change"), `MAX_BYTES_PER_SAMPLE=64`, `MIN_TILE_SIZE_PX=16×16`; tile ∈ {32×32,32×16,16×16}; Shared-layout USC magics 32x32=0x2f/32x16=0x3f/16x16=0x36, vtx/compute=0x24 | `pipeline/` | partial (pipeline/README EXP-0021 — tile is **fixed 32×32** (does NOT shrink with bpp — delta from G13/G14), 32 KiB tile SRAM budget + `Σ(tile_area·bpp·samples)` ≈32 B/sample formula HW-validated, tile counts at `0x68000+0x904/+0x908`; ⏳ USC shared-layout magic bytes) | M | 32 KiB budget is explicitly per-generation — **probe A18**. |
| Sample positions | `hk_cmd_draw.c:2276`, `agx_state.c:3258` | Packed 4-bit x/y nibbles in `ppp_multisamplectl`: 1x=0x88, 2x=0x44cc, 4x=0xeaa26e26; max 4 samples; programmable-sample-positions path | `pipeline/` | partial (pipeline/README EXP-0021 + **RT-4 correction** — **sample positions ARE userspace-emittable**, written to a **client BO** (`0x100000e8000` 4× / `0x100000e0000` 2×) at **+0x40** as N `(x,y)` f32 pairs on a 1/16 grid; **native-decoded, NOT firmware/kernel-managed** — EXP-0021's "byte-identical" diffed the wrong BOs) | S–M | Emitted directly by userspace into the sample-position BO; do NOT route via the kernel. |
| Compute dispatch model | `libagx/libagx_dgc.h:224`, `hk_cmd_dispatch.c`, `agx_state.c:5282` | CDM launch register-count fields; workgroup/grid encoding; indirect global vs local mode; `num_workgroups` must be in GPU memory; max threadgroup 1024, shared mem 32 KiB | `pipeline/` | partial (cmdstream CDM EXP-0011/0024 + hardware-overview §3 — direct dispatch encoding HW-validated (grid/tg in threads, config word, threadgroup-mem size `(bytes<<2)\|0x80`), 1024 max threads, 32 KiB shared, subgroup 32; ⏳ indirect global-vs-local mode + `num_workgroups`-in-memory path) | M | |
| Scratch / spill per-core geometry | `lib/agx_scratch.c`, `libagx/helper.cl` | `AGX_THREADS_PER_GROUP=32`, `AGX_SPILL_UNIT_DWORDS=8`, addr shift 8; `AGX_MAX_SUBGROUPS_PER_CORE=128` (flagged uncertain "96+8?"); `AGX_MAX_SCRATCH_BLOCK_LOG4=6`; per-core walk over clusters×cores×core_masks; doorbell/stack-map ISA mechanism (`DB_NEXT=32/ACK=48/NACK=49`, 4 block regs); `AGX_MAX_CORES_PER_CLUSTER=16`, `AGX_MAX_CLUSTERS=8` | `pipeline/` + `NEW: memory-model` | partial/open (EXP-0020 proves compiler-reported scratch; EXP-0041 runs M4 CS/VS/FS with 208–576 B scratch but finds no scratch-correlated allowlisted launch/state/resource-map change. This is a negative macOS-boundary result, not a kernel-ownership result. Helper cfg/data/binary, SR ABI, block geometry, tags, limits and failures remain un-RE'd.) | L | Public Mesa values are requirements/hypotheses, not Apple9 facts. Core/cluster geometry must be derived separately on A18 and M4; unchanged-UAPI userspace obligations remain until proven otherwise. |
| Partial-render / spill behavior | `hk_cmd_draw.c:281`, `agx_tilebuffer_spills` | When RTs exceed tile budget → partial bg/eot store/load; `PROCESS_EMPTY_TILES` bandwidth opt | `pipeline/` | partial (pipeline/README EXP-0021 + kernel-interface §4.4 — decided **firmware-triggered**: no userspace overflow knob; userspace supplies `partial_bg`/`partial_eot` programs + allocates the tiler parameter buffer; firmware detects overflow + flushes tiles; threshold/mechanism firmware-owned) | M | Ties directly to tilebuffer sizing. |
| Occlusion / visibility counters | `hk_query_pool.c:104`, `agx_query.c:47` | Device-wide 64-bit visibility-counter heap (`AGX_MAX_OCCLUSION_QUERIES=32768`), one active at a time; `FRAGMENT_CONTROL.visibility_mode` COUNTING/BOOLEAN; `isp_oclqry_base` | `pipeline/` | not-started | M | Native HW mechanism. |
| Timestamps | `hk_query_pool.c:66`, `agx_batch.c:190` | Firmware-written timestamp objects (kernel handle+offset, not GEM); compute-end/fragment-end granularity; `command_timestamp_frequency_hz`; **`timestampPeriod` unknown/FIXME** | `pipeline/` + `hardware-overview.md` | not-started | S–M | Timebase is a queryable param; confirm period on A18. |

### 2f. Device, memory/VM, submission

| Subsystem | Mesa location | A18 hardware facts required | Owning docs/ area | Status | RE | Notes |
|---|---|---|---|---|---|---|
| GPU identity / topology / params | `lib/agx_device.c`, `include/drm-uapi/asahi_drm.h:105` | `drm_asahi_params_global` shape: gpu_generation/variant/revision, chip_id (BCD), num_dies, num_clusters_total, num_cores_per_cluster, core_masks[], max_frequency, vm_start/vm_end/vm_kernel_min_size, max_commands_per_submission, max_attachments, timestamp freq; `SOFT_FAULTS` feature bit | `hardware-overview.md` | partial (hardware-overview §1/§2 — identity + topology done (A18 Pro, T8140, G17P, gen 17/var P, 6-core/5-active, 1 cluster, usc_gen=3, core_mask 61); kernel-interface §7 lists the `drm_asahi_params_global` shape; ⏳ chip_id BCD + vm_start/vm_end + max_commands values not measured) | S | hardware-overview already has topology (G17P, 6-core/5-active, usc_gen=3). Extend with the driver-facing param shape + chip_id. |
| Capability limits | `hk_physical_device.c`, `agx_pipe.c:2000` | Subgroup=32; MSAA 1/2/4; shared-mem 32 KiB; max image 16384, layers 2048, viewports 16, RTs 8, dual-source 1; align UBO 64/SSBO 16; fp16 denorm-preserve+RTE, fp32 FTZ, no fp64; line/point ranges; no depth-bounds | `hardware-overview.md` | partial (hardware-overview §3 — full Metal caps table (1024 threads, 32 KiB shared, arg-buffers Tier 2, RT/MSAA/etc.); capability-matrix cross-maps native-vs-emulated; ⏳ consolidated driver-limits table — UBO 64/SSBO 16 align, line/point ranges, fp16/fp32 denorm modes, no depth-bounds) | S–M | Metal caps captured in EXP-0002; cross-map to these driver limits. |
| Virtual-address space layout | `lib/agx_device.c:565`, `lib/agx_va.c`, `lib/agx_bo.c` | 36-bit robustness carveout (unmapped bottom `1<<36`); 4 GiB-aligned USC/shader window (addresses are 32-bit offsets from `shader_base`, all shader mem in one 4 GiB window); zero page at `1<<32`, scratch page +16 KiB; printf buffer at `1<<36`; sparse RO/RW address-bit shadow; kernel heap top; 16 KiB guard | `NEW: memory-model` + `hardware-overview.md` | partial (kernel-interface §3.2 — observed VA regions: Region A queue-context (`0x18000`/`0x58000`/`0x68000`, VA < 0x1_0000_0000) vs Region B resource heap (≥ 0x1_0000_0000); gap: 36-bit robustness carveout, 4 GiB USC/shader window, zero/scratch/printf pages, sparse RO/RW shadow — Mesa policy not RE'd) | M | Policy is portable but depends on A18 `vm_start/vm_end` + max load shift (=4). |
| BO / bind constraints | `lib/agx_bo.c:361`, `lib/agx_device.c:135` | 16 KiB alignment on all bind offset/addr/range; BO rounded to 16 KiB; POT cache buckets 2^14..2^22; BO flags LOW_VA/EXEC(→LOW_VA)/WRITEBACK/SHAREABLE/READONLY | `NEW: memory-model` | partial (kernel-interface §3/§7 + hardware-overview §2 — 16 KiB alignment on all bind offsets/addresses/ranges, BOs rounded to 16 KiB, device 16 KiB pages confirmed; gap: BO flags (LOW_VA/EXEC/WRITEBACK/SHAREABLE/READONLY) + POT cache buckets — Mesa-specific, not RE'd) | S | Page-size dependent; holds for A18 (16 KiB). |
| Userspace↔kernel submission shape | `lib/agx_device.h:74`, `hk_queue.c`, `agx_batch.c:642` | UAPI: VM_CREATE/QUEUE_CREATE/GEM_CREATE/GEM_MMAP_OFFSET/VM_BIND/GEM_BIND_OBJECT/GET_TIME/SUBMIT; `drm_asahi_cmd_render`/`cmd_compute` field set; barrier model (CDM↔VDM, ioctl-relative); per-submit command limit; queue wants `usc_exec_base=shader_base` | `NEW: memory-model` (interface notes) | partial (kernel-interface.md — shared-mem ring + doorbell model, sel-9 map→GPU-VA HW-confirmed, IOKit selector inventory, `drm_asahi_cmd_render`/`cmd_compute` field sets (§6), kernel-provides list (§7); ⏳ exact CPU→GPU doorbell store + some submit-field semantics remain kernel-side open items §8) | M | Lower priority per CLAUDE.md; macOS path differs but the *fields userspace hands down* are in scope. Coordinate with kernel team. |

### 2g. Shader ABI & the native-vs-emulated capability boundary

| Subsystem | Mesa location | A18 hardware facts required | Owning docs/ area | Status | RE | Notes |
|---|---|---|---|---|---|---|
| Register/preload ABI | `lib/agx_abi.h`, `compiler/README.md` | Special regs: r0l=nesting counter, r1=link, r5/r6=vertexID/instanceID preloaded; VS attrib at reg `2*(8+i)`; FS out sample_mask@2/Z@4/S@6/color(rt)@`2*(4+4rt)`; fragment epilog reg contract | `NEW: abi/` | partial (isa/README EXP-0010/0020 — buffer-base-pointer preload into uniform/binding slot (device_load byte+4), scalar-uniform-in-uniform-register mechanism, r0l=nesting counter + r1=link identified; ⏳ full VS attrib / FS output register-preload contract not tabulated) | M | Compiler↔driver contract, but pinned to register-file HW facts. |
| Sysval / uniform layout | `gallium/.../agx_nir_lower_sysvals.c`, `agx_uniforms.c`, `hk_cmd_buffer.h:47` | Sysval tables enum (ROOT/PARAMS/GRID/VS…/CS); root `agx_draw_uniforms` layout; per-stage `agx_stage_uniforms` (**texture_base first** = u0_u1); each sysval→table/offset; clip_z_coeff fp16 0.5=0x3800; push into 16-bit uniform regs via USC (max 64 halfs/range) | `NEW: abi/` + `cmdstream/` | partial (isa/README EXP-0010 + cmdstream USC EXP-0024 — the **push-into-uniform-registers-via-USC** mechanism (uniform-preamble programs, uniform-data ptrs) documented; gap: sysval table enum (ROOT/PARAMS/GRID/VS/CS) + per-sysval table/offset layout is a driver convention, not specified) | M | Driver convention, but the *push-into-uniform-registers-via-USC* mechanism is hardware. |
| Fast-link prolog/epilog | `hk_shader.c:1810`, `agx_state.c:2284` | Which state bakes into prolog (VS: vertex-input formats; FS: polygon stipple, sample-mask, cull-distance) vs epilog (blend, logic op, alpha-to-coverage/one, color-format conv, RT remap); `run_zs_tests`/`no_epilog_discard` sideband | `NEW: abi/` + `pipeline/` | partial (cmdstream/README EXP-0019 — blend/dual-source/logic-op **compiled into the FS epilog** (programmable-blend model) + constant/uniform-program prolog (isa EXP-0010/0020) documented; ⏳ full prolog/epilog state-baking split (vertex-input formats, polygon stipple, sample-mask, cull-distance, color-format conv)) | M | Stitching is software; the register-hand-off between segments is ABI. |
| **Native-vs-emulated feature matrix** | `libagx/`, `poly/`, `agx_streamout.c`, `hk_shader.c` | Which fixed-function stages are ABSENT (→ compute-emulated): geometry, tessellation, transform feedback, primitive-restart-with-GS, adjacency, tri-fan, edge flags, pipeline-stats, conditional render; which are native (occlusion, timestamps, HW prim-restart for plain draws, quads) | `NEW: capabilities.md` + `pipeline/` | partial (capability-matrix.md — decided native-vs-emulated matrix: **15 native / 6 emulate / 4 kernel-FW**; native RT+matrix+**mesh (EXP-0030)**+**tessellation (EXP-O2H)**+**sample positions (RT-4)**, emulate GS/XFB/custom-border; **mesh and tessellation are now RESOLVED native — only GS/XFB remain emulate**) | M | **Scoping resolved:** A18 has native mesh + native tessellation, so those emulation paths retire (compute-tess kept only as optional fallback). See §4. |
| Software-emulated pipeline engine | `mesa/src/poly/` (renamed libagx), `libagx/geometry.cl`, `tessellation.cl`, `tessellator.cl` | VS→compute lowering, GS→compute (4 sub-programs), TCS/TES→compute + D3D11-reference tessellator; heap bump-allocator; subgroup-32 prefix-sums; `POLY_TES_PATCH_ID_STRIDE=8192` | `NEW: capabilities.md` | partial (capability-matrix §2 + isa/README EXP-0018 — the A18 substrate the emulation depends on is confirmed: subgroup width 32, native atomics, native prefix-scan; the emulation engine itself is portable Mesa code (VS/GS/TCS→compute) not (re)documented here) | L (but mostly A18-agnostic) | Algorithm is portable; depends only on subgroup width + atomics + heap. Confirm A18 subgroup=32. |

---

## 3. Prioritized gap list (what a from-scratch A18 port needs that we have NOT documented)

Ordered by how **blocking** it is. Items 1–6 block *any* working shader/draw; 7–12 block correctness/
coverage; 13+ are refinements. Everything except the two `partial` device rows is **not-started**.

1. **Full A18 instruction encodings (`isa/`).** Opcode map + per-instruction bit layouts + operand
   sub-encodings + semantics, hardware-validated. Nothing runs without this. **[L]** — the whole
   Phase-1 deliverable; `isa/README.md` today is only preliminary byte observations.
2. **Register/uniform/immediate machine model (`isa/` + `NEW: abi/`).** 256 half-GPRs, 512
   half-uniforms, half-reg addressing/alignment, register hints, 3E4M minifloat, and the
   **Dynamic-Caching** implications for occupancy. Blocks the register allocator and every encoding. **[M]**
3. **Scoreboard / wait model (`isa/`).** Slot count (2?), max-pending (8?), which ops are async,
   barrier-drain rules. Wrong here → silent corruption. **[M]**
4. **Sysval/uniform ABI + USC binding words (`NEW: abi/` + `cmdstream/`).** How the driver feeds
   fixed-function state into the shader (which uniform register holds what) and the USC tag magic
   bytes + field splits. Blocks binding any resource or uniform. **[M]**
5. **VDM + CDM control-stream layout (`cmdstream/`).** Block-type framing, Index-List / Launch
   words, Pipeline-address encoding, barriers. Blocks issuing any draw or dispatch. **[M]** (draw
   core), **[L]** (the chip-specific barrier/`unk` bits — see §4).
6. **TEXTURE / PBE / SAMPLER descriptor bit layouts + `Channels` format table (`descriptors/`).**
   Blocks all texturing and render-target binding. **[L]**
7. **Texture memory layout: twiddle order + tile-size table + mip tree (`tiling/`).** Blocks correct
   sampling/storage of any non-linear image. **[S–M]** (order likely stable; mip-tree corner cases M).
8. **Lossless compression metadata format (`tiling/`).** The single **biggest unknown**; format is
   generation-specific and Apple revises it. Blocks compressed RT/texture (default fast path) and the
   decompress/fast-clear kernels. **[L]**
9. **PPP fixed-function state block (`cmdstream/` + `pipeline/`).** 25-entry header + ~15 sub-structs
   (depth/stencil, blend-adjacent, raster, viewport, cull, varyings). Blocks correct 3D state. **[L]**
10. **Tilebuffer sizing + sample positions + partial-render (`pipeline/`).** 32 KiB budget (per-gen),
    tile-size selection, MSAA sample layout, spill/partial programs. Blocks MSAA and large-RT correctness. **[M]**
11. **TBDR render-command fields (ZLS/CR/ISP) + submission shape (`cmdstream/` + `NEW: memory-model`).**
    ZLS control, ISP scissor/merge, depth/stencil page/cacheline strides, the `drm_asahi_cmd_render`
    field set userspace hands the kernel. **[M]**
12. **VA-space layout + scratch/spill per-core geometry (`NEW: memory-model` + `pipeline/`).** 4 GiB
    USC window, robustness carveout, zero/scratch pages, doorbell-driven spill, per-core scratch sizing
    (scales with A18's core topology). Blocks shaders that spill and robustness. **[M–L]**
13. **Native-vs-emulated capability matrix (`NEW: capabilities.md`).** Decides how much of the
    GS/tess/XFB compute-emulation stack is needed on A18 (mesh/RT could retire it). Scoping, not
    blocking, but steers effort. **[M]**
14. **Texture/image instruction quirks + NIR-lowering facts (`isa/` + `pipeline/`).** Buffer-texture
    lowering, RGB32 emulation, image-store ordering bit, interpolation coefficient model, denorm/fmin
    quirks, sample-mask ordering. Correctness across the CTS. **[M–L]**
15. **Subgroup/quad op inventory (`isa/`).** Width 32, available reductions/scans, quad-shuffle hazard,
    ballot. Blocks subgroup-using shaders and the emulation library. **[M]**
16. **Occupancy / cycle model (`isa/` + `pipeline/`).** Perf-only; last, since wrong values slow but
    don't break. **[M–L]**
17. **BORDER descriptor + custom-border two-plane trick, sampler heap limits (`descriptors/`).** **[M]**
18. **Capability limits cross-map (`hardware-overview.md`).** Turn EXP-0002 Metal caps into the
    driver-facing limits table. **[S]** (partly done).

---

## 4. A18 / Apple9 divergences from M1/M2 to probe explicitly

The M1/M2 driver encodes many facts that are **known to differ across generations** or are **flagged
uncertain even on G13/G14**. Each is a specific hypothesis for `hypotheses.md` / an experiment. Grouped
by likelihood of divergence.

**Almost certainly different on G17P (a bigger jump than G13→G14):**
- **The entire ISA encoding table.** The file is literally `AGX2.xml` (G13/G14). G17P is a new
  generation; assume opcodes/field positions do not carry over (this is already a stated project premise).
- **Lossless compression format.** `layout.c`/`compression.cl` comments: "AGX compression is not fully
  understood," modes "depend on format." Apple has changed compression across generations. The 8×4
  subtile / 16×16 tile / twiddled-metadata layout and the mode bytes (0x1f/0x60/…) must be
  re-reverse-engineered, not assumed.
- **CDM/VDM barrier bits & extra command words.** `chip_id_to_params` (`decode.c:924`) has **no case
  above gen 14** — A18 falls through to a wrong (gen-13) decode. Every generation so far added
  `unk`/barrier bits or a whole packet: `CDM_UNK_G14X` (`libagx_dgc.h:243`), VDM/CDM barrier
  `unk_4/unk_24/unk_26` toggled per chip (`libagx_dgc.h:355-413`). **Expect a "G17X"-style delta** and a
  new launch/barrier bit set. This is the single highest-signal, lowest-effort thing to re-check from a
  Metal capture.
- **Tilebuffer capacity (`MAX_BYTES_PER_TILE=32768-1`).** Commented "on G13G… may change in future
  versions." A larger on-chip tile budget on A18 would change tile-size selection and spill thresholds.
- **Scratch per-core geometry / `MAX_SUBGROUPS_PER_CORE`.** Already flagged uncertain on G13
  ("96+8?"). A18 has a different core/cluster topology (this unit: 5 active cores, 1 cluster,
  `usc_gen=3` vs G13/G14 usc_gen), so per-core scratch sizing and the doorbell stack mechanism must be
  re-derived.

**Present-on-M1/M2-as-emulation → may become NATIVE on Apple9 (retires emulation code):**
- **Mesh / task shaders.** Unsupported on G13/G14 (only stat enums exist). Apple9 is the plausible
  first mesh-capable generation. If present, could replace the whole VS→GS/TCS compute-emulation stack.
  **Probe for hardware mesh support and its command/ISA encoding.**
- **Hardware geometry shaders.** Emulated as compute (`poly_nir_lower_gs`, 4 sub-programs). Historically
  absent on Apple. Confirm still absent (or subsumed by mesh).
- **Hardware tessellation. → RESOLVED NATIVE (EXP-O2H).** M1/M2 emulate it (VS→TCS→D3D11-reference
  tessellator kernel as three compute dispatches), but **A18/G17P has a NATIVE hardware tessellation
  stage**: `drawPatches` → native VDM patch-dispatch record `0x40`, half-float factor buffer
  (`MTLTessellationFactorsHalf`), ordinary post-tess `__vertex` shader; domain generator
  firmware-managed. **NOT compute-emulated on A18** — the `libagx` compute path is now an OPTIONAL
  fallback only. (GS and transform feedback remain absent → emulate.)
- **Transform feedback / streamout.** Emulated on the GS path + CPU primitive counting
  (`agx_streamout.c`). Probe whether A18 has any streamout unit (Vulkan wants it; Metal does not expose it).
- **Hardware ray tracing.** Metal caps on this unit report `supportsRaytracing=YES` and
  `supportsRaytracingFromRender=YES` (EXP-0002) — but the Mesa driver has **no RT code at all** (M1/M2
  lack it). This is a **pure gap**: an A18 Vulkan port would need RT-acceleration-structure formats and
  RT shader/ISA intrinsics that are undocumented anywhere in our references. High-value probe target.
- **Dynamic Caching.** Apple9 marketing feature (register/occupancy behavior). May change the
  register-file/occupancy model (gap-list #2, #16) and the scratch/spill design. Probe its
  observable effect on GPR pressure vs thread count.

**Flagged M1/M2 quirks/errata to re-test (may be fixed or changed on A18):**
- **Two-sided polygon fill "doesn't work on G13"** (`agx_state.c:378`) — test if A18 does it natively
  (Vulkan/GL want it).
- **Cube `imageLoad` OOB wrong on G13** → lowered to 2D-array (`agx_compile.c:1139`). Re-test A18.
- **`txf` robustness LOD hack** — comment: "erratum workaround on G13… check if G15 is affected"
  (`texture.cl:97`). Re-validate on A18.
- **Atomic cluster-coherency bit 45** (`agx_pack.c:821`, only G13X). A18's coherency model
  (single-cluster phone SoC here) must be re-decided.
- **fmin/fmax denorm-flush + "no float modifiers on G13"** (`agx_nir_opt_preamble.c:70`,
  `agx_nir_lower_fminmax.c`) — re-check A18 ALU denorm/modifier behavior.
- **Cross-workgroup barrier opcode sequence "observed on G13D"** (`agx_compile.c:1527`) — re-derive.
- **No packed depth24-stencil8** (Metal/AGX) — EXP-0002 confirms `depth24Stencil8=NO` on A18;
  document that Z/S stay separate resources.
- **`timestampPeriod` unknown** (`hk_physical_device.c:790`) — pin down A18 timebase.

**Capabilities Metal exposes on A18 that our probing should turn into hardware facts** (Metal-subset
heuristic, per `hypotheses.md` backlog): programmable sample positions (Metal says YES — confirm bit
format), argument-buffer Tier 2 / bindless model, `readWriteTextureSupport` Tier 2, primitive motion
blur (RT-adjacent), function pointers / dynamic libraries. And the Vulkan/GL-vs-Metal gaps to probe
for native support vs emulation: logic ops, dual-source/extended blend, arbitrary sampler border
colors (emulated via 2 sampler planes today), wide/smooth lines (Bresenham-only today), provoking
vertex, depth clip-vs-clamp, conditional rendering (CPU-emulated today).

---

## 5. Module dependency I could not fully pin down from code

- **Exact USC Texture/Sampler count↔buffer bit split** — `cmdbuf.xml:667` explicitly says "Exact split
  is unknown. Count is at least 5 bits, less than 8." Unknown even on M1/M2; must be RE'd fresh on A18.
- **Many PPP/CR `unk`/reserved bits** (64 across `cmdbuf.xml`) — meanings unconfirmed in Mesa; each is
  its own A18 verification item.
- **CDM/VDM barrier bit semantics** — `libagx_dgc.h:386` sets a pile of cache-flush bits "to be safe"
  with the admission "we don't know what the bits mean." We must document them from data traces, and
  cannot rely on Mesa's meanings.
- **`num_gps`, `num_frags`, `is_sksm`** from the A18 accel node (EXP-0002) — raw config values whose
  semantics are unconfirmed; no Mesa analog. Flag for the pipeline/topology docs.
- **Tessellation VDM sub-word ordering** — `cmdbuf.xml` marks it "XXX: order is a guess / out of bits."
  Even the M1/M2 layout is uncertain; A18 needs a clean derivation (or is mooted if A18 has HW tess).
- **Whether G17P is still the "AGX2" ISA encoding family or a new revision** — the whole ISA-effort
  scope hinges on this; only hardware disassembly (Phase 1) answers it.
