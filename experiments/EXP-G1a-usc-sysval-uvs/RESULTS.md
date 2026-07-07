# EXP-G1a Results — USC bind grammar (G1-a) · sysval→uniform (G1-c) · UVS linkage (G1-e)

**TL;DR.** Change-one-Metal-parameter byte-diffing of our own control BOs (34 draws, all `status=4`,
0 faults/reboots) + OWN-SHADER splice/render closes objective-1 gaps G1-a/G1-c/G1-e.

* **G1-a.** G17P graphics has **no G13-style single tagged "USC control-word list."** Binding is split
  across three structures, each with a clean grammar:
  1. **Textures + samplers** → Tier-2 **argument buffer `0x10000248000`**: a **2-pointer header**
     `[texture-array VA][sampler-array VA]` (8-byte LE GPU VAs) followed by contiguous **32-byte
     texture descriptors** then **8-byte sampler descriptors**. The **count↔split field** is the
     header itself: `num_textures = (samp_ptr − tex_ptr)/0x20`; `num_samplers = (term − samp_ptr)/8`.
  2. **Buffers** → **`0x10000100000+0xa0`**: a table of **8-byte LE GPU VAs**, one per bound buffer
     in binding-index order (vertex/uniform buffers alike). FS scalar/constant buffers additionally
     push into a **staging region** whose base sits at `0x10000100000+0x30/+0x38` (+0x100 per buffer).
  3. **Uniform preload** → the per-stage **USC uniform-preamble program `0x10000130000`**, led by a
     fixed header of tagged 8-byte words — **`0x0088_00XX`** register/shader-config (`XX`=stage×0x0c),
     **`0x0042_XXXX`** uniform-data pointer, **`0x0020_00XX`** uniform-slot count/id (+2 per preloaded
     resource) — then a compiler-generated program that copies pointers/data into uniform registers.
* **G1-c.** **System values are NOT preloaded into uniform registers.** Reading `vertex_id`/
  `instance_id` changes **only** the shader code; the USC preamble is byte-identical (0 words) →
  sysvals are read via `get_sr` on demand (confirms EXP-0031). What the preamble **does** preload:
  buffer/vertex base pointers (from the `0x10000100000` VA table; vertex base = slot 3, EXP-0031) and
  scalar/constant uniforms/push-constants (from the `0x0042XXXX` uniform-data pointer). Viewport/FF
  state stays in `0x68000`/`0x58000` descriptors consumed by fixed-function, not uniform regs.
* **G1-e.** VS UVS output slots: **`[[position]]` = slots 0–3, user varyings = slots 4+** (one slot
  per scalar component, in declaration order). FS `iter` reads them by coefficient index; the linkage
  is **positional** and cross-stage-compacted (only varyings the FS consumes are emitted).
  **HW-validated by reorder**: an identical FS reading the middle UVS slot rendered **0.200 vs 0.302**
  depending only on which value the VS wrote to that slot.

All raw tables in `raw/ana/`; captures in `raw/pick*/`; our own shader bytes in `raw/shaders/`.

---

## G1-a — USC / resource bind-word grammar

### Method that isolated it
Vary **one** resource type at a time from a byte-identical baseline (`base` = 1 vtx buffer, no
tex/samp/ubuf) and byte-diff every registered control BO. `whichbo` shows exactly which BO absorbs
each resource type; `diff`/`dump` decode the field.

### Finding 1 — where each resource type binds (HW-clean, `whichbo`)
| add one… | BO that changes | what changes |
|---|---|---|
| **texture** (`read`) | `0x10000248000` (+FS code/USC program) | +1 32-byte texture descriptor + header split-ptr advances 0x20 |
| **sampler** (`sample`) | `0x10000248000` (+FS code) | +1 8-byte sampler descriptor after the texture array |
| **FS uniform buffer** | `0x10000100000` (+FS code/USC program) | staging base `+0x30/+0x38` += 0x100 |
| **VS uniform buffer** | `0x10000100000` (+VS code) | +1 8-byte VA in the `+0xa0` buffer table |
| **vertex_id / instance_id** | shader code only | USC preamble byte-identical (see G1-c) |

### Finding 2 — argument buffer `0x10000248000` (textures + samplers) — HW-clean
Self-describing, all pointers are **8-byte LE GPU VA** (high32 = `0x00000100` = the BO's own VA high
bits; verified self-referential: `0x00000100_002484a0` = BO base `0x10000248000` + `0x4a0`).

```
+0x480  [texture-array VA]   ── 8B ── → first texture descriptor
+0x488  [sampler-array VA]   ── 8B ── → first sampler descriptor
        (texture array)      32B each: <format/type/swizzle> <..> <dataVA>>4> <..> <16B zero>
        (sampler  array)      8B each: <filter/LOD/addr words>
        <terminator 0x60000000> <size word 0x0000035b>
```
Texture sweep (`base→tex1→tex2→tex3`, all HW-clean single-structure diffs):

| cfg | `+0x480` tex-arr | `+0x488` samp-arr | Δptr = tex_ptr..samp_ptr | # tex descs |
|---|---|---|---|---|
| base (0 tex) | — (terminator at +0x480) | — | — | 0 |
| tex1 | `…4a0` | `…4c0` | 0x20 | 1 (`16880a22 … 00001c60 …`) |
| tex2 | `…4a0` | `…4e0` | 0x40 | 2 (`…1c60`, `…1c70`) |
| tex3 | `…4a0` | `…500` | 0x60 | 3 (`…1c60/1c70/1c80`) |

Sampler sweep (`smp1→smp2→smp3`, 1 tex + N samplers) grows the **sampler array** after the texture
array: `000e0000 00000780` (nearest s0), `028e0000 00000780` (linear s1), … — 8 bytes each,
confirming `num_samplers = (terminator − samp_ptr)/8`. Mixed `2tex+2samp+1buf` reproduces exactly:
tex-arr@`4a0` (2×32B), samp-arr@`4e0` (2×8B), split Δ=0x40 → 2 textures.

**This is the "Texture/Sampler count↔buffer split field":** the 2-pointer header. The shader's
`tex_sample` **op+4 = texture slot** and **op+5 = sampler slot** (EXP-0016) index these two arrays.
Buffers are a **separate** table (below), so the "buffer split" is that buffers never appear here.

### Finding 3 — buffer table `0x10000100000+0xa0` (HW-clean, VA-correlated)
A flat table of **8-byte LE GPU VAs**, one per bound buffer in index order (HW-correlated to the VAs
`uvar` printed): base → `+0xa0 = 0x10000018700` (vtxBuf 0); `+2 vbuf` → `+0xa8/+0xb0 =
0x10000018800/…8900` (buffers 1,2). FS constant buffers do not add table entries; they shift the
**staging base** `+0x30`(`0x00019b00→+0x100/buf`)/`+0x38` and are `device_load`ed by the FS preamble.

### Finding 4 — USC uniform-preamble header tags `0x10000130000` (HW-clean)
Three per-stage blocks (block0≡block1 = vertex, block2 = fragment, EXP-0024). Each begins with a
**fixed header** of tagged 8-byte words before the program body (which starts with a `0x67` load):

| header word | tag (high16) | meaning | evidence |
|---|---|---|---|
| `+0x04` = `0x0088_00XX` | `0x0088` | register/shader config; `XX`=stage×0x0c (00/0c/18) | invariant per stage |
| `+0x10`,`+0x18` (VS) / `+0x490` (FS) = `0x0042_XXXX` | `0x0042` | **uniform-data pointer** (shifts +0x4000/16 KB, EXP-0024) | ptr, not code |
| `+0x14` = `0x0020_00XX` | `0x0020` | **uniform-slot count/id** (+2 per preloaded FS uniform buffer) | `0x0020000e→0x00200010` on fbuf1 |

**The per-resource preload itself is done by the program body**, not by expanding a tagged word list:
adding a texture/buffer *inserts `0x67`-load + store instructions* into the preamble (the block reflows
downstream) — so there is **no fixed Shader/Texture/Sampler bind-word table** to emit. The
driver-emittable descriptor data is the header tags above + the two resource tables (Findings 2–3).

---

## G1-c — system-value / FF datum → uniform register

### Sysvals are read on demand, not preloaded (HW-clean negative)
`vary1 → vid` and `vary1 → iid` change **only** `0x10000000000` (shader code); the USC preamble
`0x10000130000` is **byte-identical (0 words)**, and no buffer/arg BO changes. So `vertex_id`,
`instance_id` (and by EXP-0031: thread IDs, `[[position]]`, `front_facing`) are materialized by
`get_sr` inside the shader — **they occupy no uniform-register slot** and there is no sysval→slot
preload table to emit.

### What the uniform-preamble program *does* put in uniform registers (established)
| datum | how it reaches a uniform register | slot |
|---|---|---|
| buffer / vertex-buffer base pointers | preamble `0x67` load from the `0x10000100000` VA table; consumer `device_load byte+4=base_slot` | vertex base = **slot 3** (EXP-0031); others per binding index |
| scalar / constant uniforms, push constants | preamble load from the `0x0042XXXX` uniform-data pointer → uniform reg read directly by ALU (EXP-0010) | uniform-slot count in USC header `0x0020_00XX` (+2/resource) |
| **viewport transform, FF raster/depth/blend** | **NOT a uniform register** — lives in `0x68000` (viewport `+0x910`) / `0x58000` (FF packets), consumed by fixed-function | — |
| FS `[[position]]`, `front_facing` | `get_sr` `0xa0/0xa1` / `0xc5` (EXP-0031), not preloaded | — |

**Net:** the only things in the uniform register file are **buffer/vertex base pointers** and
**scalar/constant/push uniforms**; every system value and viewport/FF datum reaches the shader by
another path (`get_sr` or a fixed-function descriptor). This is the concrete slot→meaning answer.

---

## G1-e — UVS / varying VS↔FS linkage

### VS UVS output-slot layout (HW-validated, our own `_agc.main`)
Decoding the VS `0x57` varying-stores of `vary3` (`[[position]]` + 3 `float4` varyings), all 16
stores tokenize cleanly (`raw/ana/G1e_uvs_linkage.txt`):

| varying | VS output slot indices | 0x57 `byte+4` (`slot<<5`) |
|---|---|---|
| `[[position]]` .x/.y/.z/.w | 0,1,2,3 | 0x00,0x20,0x40,0x60 |
| user varying #0 .x/.y/.z/.w | 4,5,6,7 | 0x80,0xa0,0xc0,0xe0 |
| user varying #1 .x/.y/.z/.w | 8,9,10,11 | slot≥8 ⇒ `byte+4=(slot<<5)&0xff`, **`byte+5` bit0 = slot bit8** |
| user varying #2 .x/.y/.z/.w | 12,13,14,15 | 0x180…0x1e0 |

**Slot index = 4 + 4·(user-varying number) + component.** Position is slots 0–3 (a *range*, not a
distinct op — confirms EXP-0037). The 9-bit slot (byte+4 + byte+5 bit0) for index ≥ 8 is
**byte-diff-inferred** (EXP-0037 HW-tested only ≤ slot 0xc0); it tokenizes byte-exact.

### FS iter coefficient side (HW-validated by prior + cross-checked here)
FS `iter` (`0x2f`, `byte+5 = coefIdx<<1`, EXP-0029) reads plane-equation coefficients. Coefficient
**0 = the perspective 1/W denominator** (mode `byte+6=0x04`); user-varying components follow. The FS
table is **compacted to only the varyings the FS consumes** (constant `.w`=1 components are DCE'd).

### The linkage is POSITIONAL and cross-stage-compacted (HW-validated by reorder)
`linkA` FS reads only `v1` → the compiler emits **only that one varying** in the VS (UVS slots 4–7)
and reads it in the FS (coef 1–4, coef 0 = 1/W). So a driver's job is to **assign each cross-stage
varying a matching UVS slot in both stages at link time** (position implicit at 0–3, user varyings
compacted from slot 4). Proven end-to-end on hardware:

| test | VS writes to middle output slot (v1) | identical FS returns `in.v1` | rendered blue |
|---|---|---|---|
| **linkA** | B (z=0.2) | reads middle slot | **0.200** ✅ |
| **linkB** | C (z=0.3) (v1/v2 swapped) | reads middle slot | **0.302** ✅ |

The FS output tracks the **slot**, not the source expression → the coupling is the UVS slot number.
Corroborated by `uvar --vout k` (vary=3): FS echoing varying k renders blue = `(k+1)·0.1`
(0.102/0.200/0.302). Each end was already splice-proven independently — VS slot (EXP-0037 `0x57`
byte+4) and FS coefficient (EXP-0029 `0x2f` byte+5).

### Varying-count descriptor fields (HW-clean, `vary0..vary8`)
| field | value | meaning |
|---|---|---|
| **`0x58000+0x2c`** | `4 + 4·nvary` | total UVS scalar-output count (position 4 + varying scalars) |
| `0x18000+0x10` | `count | count<<8` | VDM output-count word (both bytes = count) |
| `0x58000+0x20` | bit16 set (≥1 out) | output-select (clip[7:0]/point_size b18/viewport b19 — EXP-O2A) |

So the tiler parameter-buffer size the driver must declare = `0x58000+0x2c` = `4 + Σ(varying scalar
components emitted)`. (`0x10000120000` is the vertex-output uniform-preamble program; its per-varying
operands reflow but the byte-addressable count a driver emits is `0x58000+0x2c`.)

---

## Marking: HW-validated vs inferred

**HW-validated** (single/clean multi-word diff, or dispatch/render confirmed):
- G1-a: which-BO absorbs each resource type; arg-buffer `0x10000248000` 2-pointer header + 32B tex /
  8B samp descriptor sizes + split = pointer-delta (tex/samp/mixed sweeps); buffer table
  `0x10000100000+0xa0` 8-byte VAs (VA-correlated); USC header tags; uniform-slot id +2/buffer.
- G1-c: sysval-not-preloaded negative (USC byte-identical on vid/iid); vertex base = slot 3 (EXP-0031).
- G1-e: VS slot layout (position 0–3 / varying 4+, our own `0x57` stores); **reorder render**
  (linkA 0.200 / linkB 0.302); `--vout` readback; count descriptor `0x58000+0x2c = 4+4·nvary`.

**Inferred / architectural:**
- G1-a: exact meaning of the `0x0002_80XX` header words and the arg-buffer `0x0000035b` size word;
  the `0x0042XXXX` uniform-data heap base (kernel item, EXP-0024).
- G1-c: the exact per-datum uniform-slot numbers inside the preamble program (not transcribed —
  rule 5; the mechanism is `device_load byte+4=base_slot`, EXP-0012).
- G1-e: 9-bit UVS slot (byte+5 bit0 = slot bit8) for index ≥ 8; the FS coef↔VS slot offset in
  perspective mode is compiler-scheduled (coef 0 = 1/W) — a *linker* assigns matching slots, there is
  no separate byte-addressable remap descriptor.

## Recommended next
1. Confirm the 9-bit UVS slot (byte+5 bit0) by splicing an index-≥8 varying store on hardware.
2. Decode the `0x0042XXXX` uniform-data heap base (which allocation it indexes) — closes the last
   uniform-preload pointer.
3. Multi-render-target / flat+perspective mixed varying set to enumerate the full FS coefficient
   ordering rule a linker reproduces.
