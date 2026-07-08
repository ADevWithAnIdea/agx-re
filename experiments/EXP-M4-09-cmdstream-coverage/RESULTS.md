# EXP-M4-09 RESULTS — cmdstream/pipeline coverage closure

Device: **Apple M4** (primary) with **A18 (G17P)** cross-confirmation on the one CORRECTION.
All dispatches `status=4` (GPU-completed). Verdicts per gap: **CONFIRM** = matches the current
`docs/`; **CORRECT** = doc was wrong, fixed + A18-cross-confirmed; **NEW** = decoded field the
doc did not specify.

---

## CMD-1 — Blend STATE-POOL side (all 19 factors × 5 ops + dual-source) — NEW spec
Harness: `harness/cmd1_blend.sh` + `svar.m`. Method: sweep every blend factor/op on
srcRGB/dstRGB/srcAlpha/dstAlpha + write mask + dual-source; diff **only** the `0x58000`
state pool; separately **count** (never interpret) changed words in the FS code BO
`0x10000000000` to classify state-only vs FS-rewrite.

**Structural result (sharpens the existing programmable-blend finding):** the 19 factors × 5
ops × dual-source identity is **entirely in the FS blend microprogram** — changing any factor/op
rewrites ~5,600–7,800 FS code words (or leaves it near-identical when the new equation lowers to
a similar program). **Nothing in `0x58000` selects a factor or op.** The impl team writes its own
blend-lowering compiler (as Asahi does). The state pool carries only these orthogonal side-flags a
driver must still emit **alongside** the compiled FS:

| field | offset | meaning | evidence |
|---|---|---|---|
| **Color write mask** | `0x58000+0x5c` bits[3:0] | 4-bit mask, **bit-reversed RGBA**: R→bit3, G→bit2, B→bit1, A→bit0 (full=0xf) | wmask 0/1/2/4/8/…/15 → nibble 0/8/4/2/1/…/f; holds with blend on OR off |
| **Store-epilog engaged** | `0x58000+0x50` bit29 (0x2000_0000) | set iff blending enabled **OR** write mask ≠ 0xf | noblend+wm15 = 0x0000_0200; blend OR wm≠0xf = 0x2000_0200 |
| **Blend-constant-color needed** | `0x58000+0x10` bit6 (0x40) | set iff any factor ∈ {blendColor,1-blendColor,blendAlpha,1-blendAlpha}; driver must then supply the constant | +0x10 0x0100_0000→0x0100_0040 for exactly those factors, on all 4 factor slots |
| **Blend/store program-class** | `0x58000+0x08` bits[10:6] | small enum co-selected by the FS lowering (0x4c0 plain-store, 0x500 default-blend, 0x540 extended) — **not** a driver-independent field | noblend 0x4c0 / blend 0x500 / 1-srccolor 0x540 |
| **Extended-source/saturate class** | `0x58000+0x18` bit0 | FS-class covariant (observed set by srcAlphaSaturate and several one-minus-dst factors); driver sets it as part of its blend lowering, not an orthogonal knob | see `b_an/factor_*.txt` |

**Blend-constant-color storage (HW-located):** the RGBA constant from `setBlendColor` is **not** a
fixed-function register — it is a **4×f32 RGBA uniform the FS reads**, placed in the uniform/arg BO
`0x10000248000` (observed at +0x620; exact offset is the driver's own uniform-allocation choice).
So: set `+0x10` bit6 and place the RGBA constant into the FS uniform stream.

**Dual-source:** vs single-source ref the `0x58000` pool is **unchanged** (the src1 factors change
only ~27 FS words). Dual-source is realized entirely in the FS (which declares `color(0) index(0)`
+ `color(0) index(1)` outputs); there is **no `0x58000` flag distinguishing dual-source**.

**Ops (add/sub/revsub/min/max, RGB and alpha):** zero `0x58000` change — all five ops are in the FS.

Verdict: **NEW** (state-side spec now complete). Consistent with (and sharper than) the doc's
"blend is programmable" note.

---

## CMD-2 — Stencil ops 0–7 on all three fields — CONFIRM (subagent `cmd2-stencil/`)
Swept all 8 ops independently on pass/zfail/sfail. All three fields share the identical enum at the
documented bit positions of the `0x58000+0x3c` stencil word: **pass[18:16], zfail[21:19],
sfail[24:22]**, enum `0 keep,1 zero,2 replace,3 incrClamp,4 decrClamp,5 invert,6 incrWrap,7 decrWrap`;
compare[27:25]; [31:28] unused. Back-face uses the **identical** encoding at `+0x44` (independent of
front `+0x3c`). No correction. Verdict: **CONFIRM** (sfail/zfail now 8-of-8 HW-validated).

---

## CMD-3 — MRT 5–8 attachments + mixed formats — CONFIRM (k-stride) + CORRECT (clear color)
Subagent `cmd3-mrt/` (extended `mrtvar.m` with per-RT `--fmts`), verified by me + A18 cross-confirm.

- **k·0x20 descriptor array extends to k=7 — CONFIRM.** Tiler-heap BO `0x10000018200`: 8 LOAD records
  at `+0x20+k·0x20`, 8 STORE/PBE records at `+0x220+k·0x20`, exact 0x20 stride, each with its own
  surface VA (rt0..rt7 = 0x58000..0x90000). Incremental bodiff shows each +1 attachment adds exactly
  one LOAD + one STORE record at the predicted offset.
- **Per-attachment format words — CONFIRM.** Each record's format byte is genuinely per-attachment
  (not shared) and equals the `numtype<<5|sizeclass` code from `docs/descriptors/format-table.md`,
  across bgra8/rgba8/r8/rg8/r16f/rg16f/r32f/rgba16f/rgba32f/rgb10a2 (+ r32uint with an integer FS).
  No renderable format rejected in 8-way mixed MRT.
- **CORRECT — clear-color location.** The old claim *"clear-color @ `+0x500+k·0x18` inside
  `0x10000018200`"* is a **vertex-buffer allocator alias**: `vtxBuf` lands at `0x10000018700` =
  `0x18200+0x500`, and that region is byte-identical to the triangle verts (`-1,-1,3,-1,-1,3` →
  `000080bf 000080bf 00004040 …`; the phantom "0x18 stride" is the 6-float triangle). **A18-confirmed
  identical.** The **real** per-attachment clear colors are a **float4 RGBA array at 0x10 stride** in a
  separate tiler BO — `0x10000128000` on **both** M4 and A18 — at `+0x170 + k·0x10` (RT0=(0,0,0,1) @
  `+0x170`, RT1 @ `+0x180`, …), **mirrored at `+0x470 + k·0x10`** (0x300 apart = the LOAD/RENDER
  segment spacing). The `0x18200` k·0x20 records hold LOAD/STORE descriptors, **not** the clear color.

---

## CMD-4 — Primitive × index-type × instancing matrix (u32 RUN) — CONFIRM + solidified
Harness: `dvar4.m` + `harness/cmd4_draw.sh`. Ran all 5 prims × {non-indexed, u16, u32} (15 combos)
+ instancing, **all `status=4`**. The u32-index path (opcode **0x61f4**), previously "inferred, not
re-run," is now **HW-validated**.

**VDM draw record (`0x18000`) — full field map:**
- **Non-indexed:** opcode **0x61c4** (bytes @+0x66/+0x67); **primitive type byte @+0x65** =
  {point 0x00, line 0x01, lineStrip 0x03, tri 0x06, triStrip 0x09}; **vertexCount @+0x68**;
  **instanceCount @+0x6c**.
- **Indexed (record shifts):** opcode word @+0x6c–0x6f = **`0x61f2 | strip | (u32<<1)`** →
  0x61f2 (u16 list) / 0x61f3 (u16 strip) / **0x61f4 (u32 list)** / 0x61f5 (u32 strip), all RUN;
  **primitive byte @+0x6d** (same enum); **restart comparand @+0x68**; **idx-buf config @+0x70**;
  **indexCount @+0x74**; **instanceCount @+0x78** (moved from +0x6c); **baseVertex @+0x7c** (=5
  confirmed, u16 & u32); **index-buffer extent-in-dwords−1 @+0x80** (= ⌈idxCount·idxSize/4⌉−1;
  u16×6=2, u32×6=5, u16strip×8=3 — confirms the O2A note); config word @+0x64 = 0x40000001.
- **baseInstance:** **not** in the VDM record (both indexed & non-indexed unchanged); surfaces only
  via the vertex-attribute path when the shader consumes `[[instance_id]]` (our probe didn't, so it
  was elided — consistent with the doc's "not in the VDM record").

Verdict: **CONFIRM** + u32 path now HW-validated + opcode strip/u32 bit-decode solidified across all combos.

---

## CMD-5 — Multi-viewport / clip to max + restart comparand — CONFIRM
Harness: `ovar.m` + `o_caps/`.
- **Viewport count** `0x68000+0x900 = ((n−1)<<12) | 0x0C00` — **MATCH for all n = 1..16** (0x0c00,
  0x1c00, …, 0xfc00). CONFIRM to the max.
- **Clip-distance plane mask** `0x58000+0x20` bits[7:0] = `(1<<n)−1` — confirmed **n = 1..8**
  (0x01,0x03,0x07,0x0f,0x1f,0x3f,0x7f,0xff); bit16 = a constant "present" flag. CONFIRM to the max.
- **Primitive-restart comparand** `0x18000+0x68`: **always present, no separate enable bit**; a
  genuine **per-draw userspace-written comparand** that **tracks the index width** — 0x0000ffff (u16) /
  0xffffffff (u32), HW-confirmed by the u16→u32 diff and present on every indexed draw (restart or
  not). Metal only ever writes the **index-type maximum**, which is exactly the Vulkan/D3D10+ restart
  semantics a Mesa Vulkan driver needs. A truly *arbitrary* (OpenGL `glPrimitiveRestartIndex`-style)
  value is **not emittable through Metal** and its HW acceptance is therefore **formally untested**;
  but because `+0x68` is proven a settable per-draw comparand (width-tracking), a GL frontend writing
  an arbitrary value there is well-founded (HW-plausible, unverified). This is the one residual
  can't-emit-from-Metal item, now precisely located and characterized.

---

## CMD-7 — MSAA / occlusion / timestamp breadth — CONFIRM (subagent `cmd7-msaa-query-ts/`)
- **MSAA:** `supportsTextureSampleCount` 1/2/4 = YES, **8/16/32 = NO**. 8× is **Metal-rejected** two
  ways (texture create hard-asserts; pipeline returns nil+NSError) — upgrades doc's "8× unsupported"
  to *shown Metal-rejected*. `+0x24` sample word (in the **RENDER/STORE** segment): 1×=0x0000fc03,
  2×=0x0800fc03, 4×=0x0900fc03; bit24 = count LSB, bit27 = MSAA-store. CONFIRM.
- **Occlusion:** `0x58000+0xa0 = byteOffset<<14` verified for offsets 0/8/16/64/256/1024/4096; mode
  `0x58000+0x8c` bit14 (Boolean=1 / Counting=0). Readback proves accumulation (count = 4096 = 64×64;
  boolean = 1, u64). Tiler mirror `0x10000258000+0x00 = byteOffset>>2`. CONFIRM.
- **Timestamps:** uint64 ns, `timestampPeriod = 1.0` (cpu==gpu). Stage-boundary works (monotone ns);
  dispatch/draw-boundary read all-zero (Vulkan emulation flag). CONFIRM.

---

## CMD-8 — Threadgroup rounding + occupancy tier GPR flip — CORRECT ×2 (A18-cross-confirmed)
Subagent `cmd8-tg-occupancy/` (full tables there), both corrections cross-confirmed by me on the A18.

- **Threadgroup field `+0x1c/+0x20/+0x24` — CORRECT.** It is the **physical launch threadgroup size**,
  **verbatim** = requested `threadsPerThreadgroup` whenever boundaries carry semantics (every single-group
  dispatch; every kernel with a **barrier or threadgroup memory**). The doc's "round up to pow2, product
  ≥32" was a **Metal occupancy repack** of **barrier-free** kernels only, and is neither pow2 nor mult-32.
  **A18 cross-confirm (numGroups=4):** barrier `tgmem` kernel → 16→16, 48→48, 100→100 (verbatim);
  barrier-free `add3` → 16→32, 48→64, 100→128 (repacked) — identical to M4. Driver emits **verbatim**.
- **Occupancy tier `+0x00` bit23 — CORRECT.** A single-bit 2-tier boolean (`0x00080000`↔`0x00880000`),
  driven by **peak register pressure**, not total-GPR count; the doc's "≥12 GPRs" is false. **A18
  cross-confirm** (dispatch identical MSL, read cfg word; f0 measured on A18 via shdump):
  f0=8 splits — `N2E0` (2 loop-carried chains) **SET**, `N1E3`/`N0E7` **CLEAR**; f0=9 splits — `N1E4`/`N3E0`
  **SET**, `N0E8` **CLEAR**; lowest SET = half kernel at **f0=5**; trivial f0=2 **CLEAR**; f0=23 **SET**.
  Byte-identical bit23 outcomes on A18 and M4. The old A18 "f0=8→clear, ≥12" was one low-peak f0=8 kernel;
  a different f0=8 kernel sets bit23. Driver sets bit23 from its **own allocator's occupancy class**.

Cross-confirm artifacts on the A18: `~/cleanroom_work/exp-m4-09-cmd8/` (`tg/`, `kc/`, `k/`). Local subagent
evidence: `cmd8-tg-occupancy/` (`caps_tg*`, `caps_gpr`, `caps_pf*`, `caps_hi`, `run_gpr.py`, `gprmeas.py`).
