# EXP-0029 Results — fragment-shader ISA cluster

Clean-room category: **OWN-SHADER** (+ PUBLIC for the ISA DB). Every byte below is the compiled
form of MSL we wrote (`kernels/*.metal`); no Apple binary was disassembled. HW-validated facts
were confirmed by splicing a byte into our own archive and rendering it on the real A18 Pro GPU
(`agxrender_ext`, `PIPELINE_SOURCE archive` proves the spliced code ran).

All fragment interpolation/output kernels tokenize to **0 leftover** with the updated DB, and
`tools/agx-isa/roundtrip_test.py` is **ALL PASS** (compute decoding unaffected).

---

## 1. Varying interpolation (CRITICAL) — the `iter` op, byte0 `0x2f`/`0xaf`, byte+2==0x54, 10 B

Encoding `2f BB 54 DD 03 SS MM 02 NN 00` (one op per interpolated component):

| field | byte | meaning |
|---|---|---|
| group | +0 | `0x2f` / `0xaf` (bit7 = fn-hi, shared low-7 with the compute SFU) |
| lead | +1 | `0x0d` on the first op of a group, `0x05` after |
| — | +2 | `0x54` (the fragment-coefficient marker; compute SFU uses `0x56`) |
| **dst** | +3 | destination GPR, `(reg<<1)` |
| — | +4 | `0x03` |
| **src_slot** | +5 | **source varying-slot / per-triangle coefficient index, `(slot<<1)`** — HW-splice-proven |
| **mode** | +6 | `0x00` centre/linear · `0x02` centroid/sample · `0x04` perspective-denominator (W) |
| — | +7 | `0x02` |
| loc | +8 | `0x10` centre / `0x08` centroid\|sample / `0x20` last-component |

**How a varying's per-triangle coefficients are addressed:** byte+5 selects the coefficient
slot. **HW-PROVEN:** splicing `interp_noperspective` comp-0 byte+5 `0x00→0x02` switched the red
output from `color.x` (an x-gradient: corners 0.063/0.439/0.063/0.439) to `color.y` (a
y-gradient: 0.439/0.439/0.063/0.063) — the interpolator read a different coefficient
(`raw/validations.log §3`).

**Interpolation modes:**
- **`[[flat]]` / nointerpolation** — a *different, shorter* op: `iter_flat` = byte0 `0x1f`,
  byte+2==0x54, **6 B**, one per component. It loads the provoking-vertex attribute with **no
  barycentric interpolation**. HW-PROVEN behaviourally: the flat fragment renders a **constant**
  `(0,0,0.251,1)` (the provoking vertex value) at all 16 pixels of a 4×4 target, while every
  interpolated variant shows a gradient (`§1`).
- **Perspective vs no-perspective is a multi-instruction lowering, NOT a single mode bit.**
  Linear/no-perspective = four `iter` ops with byte+6==0x00. Perspective-correct adds a
  W-denominator `iter` (byte+6==0x04) + an `0xaf` reciprocal (rcp of the interpolated 1/w) + a
  per-component `fmul`. With w-varying geometry (`persp_*` kernels) perspective, linear and flat
  produce **three distinct** pixels (e.g. corner (5,0): 0.220 / 0.459 / 0.000 — `§2`); at w=1 they
  coincide (as expected). Splicing the W-op's byte+6 alone is a no-op at w=1 — consistent with
  perspective correctness being the rcp+fmul, not that bit.
- **`centroid` / `sample`** — the component `iter` ops set byte+6==0x02 and are preceded by an
  8-byte **`iter_at` setup** op (byte0 `0x2f`/`0xaf`, byte+2==0x54, byte+6==0x0a) that computes the
  custom barycentric location, plus a position preamble read (byte0 `0x04` centroid / `0x03`
  sample). Centroid vs sample differ only in the setup op's byte+7 (`0x01` centroid / `0x03`
  sample). (At full pixel coverage centroid≡sample≡centre, so no pixel difference in the testbed.)
- **Pull-model `interpolate_at_center/centroid/sample`** compile **byte-identically** to the
  matching `[[center/centroid/sample_perspective]]` qualifier (diff = 0). `interpolate_at_offset`
  is a longer custom-offset lowering. So the pull model is not a separate instruction.

---

## 2. Fragment output / epilog — colour store `frag_color_store`, byte0 `0xe7`, byte+1==0x06, 12 B

Per render target the compiler emits: `frag_color_pack` (`0x97`, packs the shader output value
into a GPR — byte+6 carries a colour component, HW-proven in EXP-0008) → `frag_tile_setup`
(`0x87 02 54`, byte+3 = per-RT tile selector) → **`frag_color_store`** → `frag_end` (`0x07 02 54`).

`frag_color_store` = `e7 06 54 <src> 00 <rt> 01 4e 00 00 00 00`:
- byte+1 = `0x06` — the **fragment** tile-store variant (compute device store is `0x00`, 14 B).
- byte+3 = **source colour register**.
- byte+5 = **render-target index**, `(rt<<1)`: RT0=0x00, RT1=0x02, RT2=0x04.

**HW-PROVEN (`§6`):** splicing `out_const` byte+5 `0x00→0x02` (store to the absent RT1) leaves RT0
at the **clear colour** → byte+5 is the RT index. Corrupting byte+1 `0x06→0x00` also leaves RT0
clear → byte+1==0x06 is the tile-store variant.

**MRT** (`out_mrt`, 3 targets) emits three of these, byte+3/byte+5 = r2/0x04, r1/0x02, r0/0x00 —
one store per target, each in its own `0x87`/`0x07` tile bracket (byte+3 = 0xc0/0x30/0x0c).
`out_half` (half4) is byte-identical-length to `out_const` (float4). **Dual-source blend**
(`color(0) index(0)/index(1)`) is just an extra output register + one store (no distinct op),
matching EXP-0019.

**`discard_fragment()`** — HW-PROVEN: `out_discard2` kills `x<2` fragments (they keep the clear
colour — nothing stored) and colours `x≥2` (`§5`). Discard suppresses the colour store.

**`[[depth]]` output** — `frag_depth_store` = byte0 `0xd7`, byte+1==0x14, byte+2==0x54, **6 B**
(distinct from the 16-byte texture write). It sits in a `0x87`/`0x07` bracket whose byte+3==0x01
selects the depth attachment (vs 0x0c for colour RT0). Structural only (agxrender has no readable
depth attachment).

---

## 3. Tilebuffer / programmable-blend read — `tile_read`, byte0 `0x67`, byte+1==0x0e, 12 B

Reading a `[[color(n)]]` **input** (the current framebuffer value, for in-shader blending) compiles
to a **load-family** op `67 0e 54 <dst> 00 <rt> 01 ce …` — the **ld_tile analogue**. byte+1==0x0e is
the fragment tilebuffer-read variant (compute device load uses byte+1 ∈ {0x10,0x00,0x11,…}). This
confirms EXP-0019: on Apple TBDR the framebuffer lives in tile memory and blend is done in-shader —
the shader reads the destination with this op and blends with ordinary float ALU, then stores.

**HW-PROVEN (`§4`):** `blend_read` returns `src*src.a + dst*(1-src.a)` (src.a=0.5). Rendered over
three clear colours it produced `out == src*0.5 + clear*0.5` **exactly**:
clear 0 → `0.400,0.102,0.051,0.251`; clear 1 → `0.898,0.600,0.549,0.749`;
clear (0.4,0.6,0.8,1.0) → `0.600,0.400,0.451,0.749`. The op read the tilebuffer and fed the blend.

`half4` tile read (`blend_read_half`, typical G-buffer format) uses the same op. Explicit
`imageblock<GBuffer>` (`imageblock.metal`) compiles to the same `0x97`/`0x87`/`0xe7` colour-slice
path per `[[color(n)]]` slot.

---

## 4. Pixel ordering (raster-order-groups) — `pixel_order`, byte0 `0x07`, byte+2==0x54, byte+4==0x06, 6 B

There is **no dedicated one-shot pixel wait/signal opcode**. Raster-order-group ordering is done by
**memory-fence ops in the same `0x07` family as the compute `threadgroup_barrier`** (EXP-0025).

Diffing `rog` (a `read_write` texture RMW tagged `[[raster_order_group(0)]]`) against `rog_none`
(identical RMW, no tag): rog adds **exactly** these ops (`raw/rog*.frag.hex`):
- `07 14 54 50 06 00` — **acquire / wait** (byte+1==0x14) — wait for prior overlapping fragments.
- `07 04 54 d0 06 00` — **release / signal** (byte+1==0x04) — this fragment done.
- two `0x87 02 54` tile-access setup ops (byte+3 = 0x08 / 0x04) bracketing the ordered access.

byte+4==0x06 (the raster-order / device fence flag) distinguishes these from a compute barrier
(byte+4 ∈ {0x08,0x09}) and from the fragment epilog `0x07` (byte+4==0x02). So the fragment
tilebuffer-ordering primitive is a barrier/fence, exactly the fragment analogue of EXP-0025's
compute interlock. (Inferred by byte-diff; not splice-proven for a stale read — needs
overlapping-fragment geometry.)

---

## 5. Round-trip / faults / recommended next
- **Round-trip:** `tools/agx-isa/roundtrip_test.py` **ALL PASS** with 9 new fragment descriptors
  added (`iter`, `iter_at`, `iter_flat`, `frag_color_store`, `tile_read`, `frag_tile_setup`,
  `frag_color_pack`, `frag_depth_store`, `pixel_order`) + 4 whole fragment programs. Compute
  decoding unchanged (the shared `0x2f/0x1f/0x67/0xe7/0x07` groups are gated on fragment-specific
  byte signatures; `9f 11 54` compute-integer collision found and fixed).
- **Faults / reboots:** none. Every splice was fault-contained; the device never wedged; no reboot.
- **Recommended next:** decode the fragment texture-sample/derivative groups (`0x18/0xb0/0x37`, only
  partly tokenized here); full bit-decode of `iter` byte+8 and the W-coefficient addressing; a
  depth-store splice (needs a readable depth attachment); an overlapping-fragment ROG stale-read.

---

## For `docs/hypotheses.md` (interpolation modes / capabilities — orchestrator to fold in)
- **Perspective-correct interpolation is a shader-software lowering** (linear `iter` + W-denominator
  `iter` + `rcp` + `fmul`), not a fixed-function unit or a single mode bit — matches "TBDR does
  interpolation in-shader". A Vulkan/GL driver must emit this sequence for smooth varyings; `flat`
  is a cheaper distinct op (`iter_flat`, provoking-vertex load).
- **All Vulkan interpolation qualifiers are representable:** perspective, no-perspective (linear),
  centroid, sample, and flat each have a distinct encoding; the pull-model `interpolate_at_center/
  centroid/sample` map onto the same ops as the qualifiers (byte-identical). `interpolate_at_offset`
  is a custom-offset lowering. → no interpolation gap for Vulkan.
- **Programmable blending is native and in-shader** (tilebuffer `tile_read` `0x67 0e`), corroborating
  EXP-0019 — Vulkan/GL fixed-function blend and logic-ops lower into the fragment shader; no ROP
  blend-hardware table to emit.
- **Fragment-shader-interlock / raster-order-groups exist** as `0x07`-family fence ops
  (`pixel_order`) — the Vulkan `FRAGMENT_SHADER_INTERLOCK` analogue is available.
- **Provoking vertex:** flat shading takes vertex 0's value (the constant-colour result equals the
  `vid==0` vertex attribute) — relevant to Vulkan provoking-vertex convention.
