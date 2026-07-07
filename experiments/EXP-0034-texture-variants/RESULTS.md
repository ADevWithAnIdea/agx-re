# EXP-0034 Results — Texture-variant instruction completeness (HW-validated)

Clean-room: **OWN-SHADER** (+ PUBLIC for the ISA DB / Mach-O format). Every byte inspected is
the compiled form of MSL **we wrote** (`kernels/tv_*.metal`). HW runs force our own archived
machine code (`PIPELINE_SOURCE archive`). Raw: `raw/mains.txt`, `raw/field_map.txt`,
`raw/hw_validation.txt`, `raw/atomics.txt`. Zero GPU wedges / reboots.

## 0. TL;DR — the EXP-0016 bundle generalizes; four fields carry all variants
The 14-byte bundle (companion `C0 80 0c C3` + 10-byte sampler op) covers **every** texture
variant. The variant is selected by four fields (offsets are `op+N` inside the 10-byte sampler op):

| field | where | carries |
|---|---|---|
| **variant** | op+2 | LOD-mode + dimension + **compare (bit5 0x20)** + **offset (bit0)** |
| **mode** | op+6 | `0x10` filtered sample · `0x00` gather/read/compare · **`0x20` LOD-query** |
| **result desc** | companion +3 | vec4 `0xb8` · scalar `0xa0` · **gather comp** `0xa4/ac/b4/bc` (bits[3:5]=r/g/b/a) |
| **operands** | preceding ALU + op+1/op+3/op+5 | coord, **compare-ref**, LOD/bias/grad, array/face/z/sample-index, const offset |

Full aligned table: `raw/field_map.txt`. All five brief items answered below; **HW-validated**
vs **inferred (byte-diff)** marked throughout.

---

## 1. sample_compare (depth PCF / shadow) — HW-VALIDATED ✅
`sample_compare(sampler, coord, compare_value)` = the ordinary sample bundle with:
- **op+2 bit5 (0x20) = depth-compare** — `sample_compare(level)` = `0x29` (`0x20|0x09`),
  implicit = `0x20`. This is the cleanest orthogonal bit (0x00→0x20 sample, 0x09→0x29 level,
  0x00→0x20 gather). Companion low-nibble is `0xd` for the compute const/dynamic-ref form
  (a dependent compare-ref register), `0x5` in fragment.
- **compare-ref operand = a register**, set up by preceding ALU/load, packed with the
  coordinate block (right after u,v). **HW-proven it is a register, not baked:** `sc_lod`
  (const 0.5) and `sc_ref` (per-thread `ref[i]` from a buffer) compile to the **byte-identical
  sampler op** — only the preceding ALU differs. Result is a scalar (companion +3 = `0xa0`,
  op+0 hi = `0x9`); op+6 = `0x00`.
- **sampler compare-func linkage:** the result is driven entirely by the **sampler descriptor's
  compareFunction** (EXP-0015: sense bit39 + test [40:42]). The comparison evaluated is
  **`compareValue COMPARE sampledDepth`**.

**HW shadow test** (`depth[i]=i/16`, ref `0.5`, nearest) — all 8 Metal compare functions give the
exact expected shadow pattern (`raw/hw_validation.txt §1`):

| compareFunc | passing texels (result 1.0) | matches `0.5 COMPARE i/16` |
|---|---|---|
| less | i=9..15 (depth>0.5) | ✅ |
| lessEqual | i=8..15 | ✅ |
| greater | i=0..7 | ✅ |
| greaterEqual | i=0..8 | ✅ |
| equal | i=8 only | ✅ |
| notEqual | all but 8 | ✅ |
| always / never | all 1 / all 0 | ✅ |

- **Dynamic ref** (`sc_ref`, `ref[i]=depth[i]`): `less`→all fail, `lessEqual`→all pass — confirms
  the reference is a per-thread register operand. ✅
- **True hardware PCF:** with a **linear** compare sampler the result is **fractional** (0.5 at the
  i=8..11 boundary) — the texture unit filters the per-texel 0/1 comparisons (native 2×2 PCF),
  not a point compare. ✅

## 2. gather / gather_compare / offset-gather — HW-VALIDATED ✅
- **gather** = sample bundle with op+6 = `0x00` (unfiltered) and a **gather result descriptor**
  in companion +3: `0xa4/0xac/0xb4/0xbc` for component **x/y/z/w**. Decode: **bit2 (0x04) = gather**,
  **bits[3:5] = component 0/1/2/3 → r/g/b/a**. **HW-validated** over the rgba grid: `.x`→R,
  `.y`→G, `.z`→B (=0 in row 0, correct), `.w`→A (=1) — each returns that channel's 2×2 footprint
  (`§4`).
- **gather_compare** = gather + op+2 bit5 (`0x20`): `gc` op+2 = `0x20`, companion +3 = `0xa4`
  (gather.x result of the PCF), compare-ref register as in §1. (Byte-diff; the compare path itself
  is HW-validated in §1.)
- **texel-offset gather** (constant offset) = op+2 bit0 (`0x01`) + the **offset packed in op+5**:
  `(1,0)→0x08`, `(0,1)→0x80`, `(1,1)→0x88`, `(3,-2)→0x18` (+op+9 `0x0e` for the negative y).
  offset.x at op+5 bits[3:6] (value≪3), offset.y at bit7+. **HW-validated:** `g_off10` shifts the
  gathered 2×2 footprint one column right vs `b_gather` (`§5`). Sampler slot occupies op+5's low
  bits (EXP-0016) — no collision with the offset.

## 3. sample_lod / sample_bias / sample_grad operand map — confirmed
op+2 LOD-mode codes (byte-diff, matches EXP-0016): **`0x00` implicit · `0x04` grad · `0x07` bias ·
`0x09` level**. The LOD/bias/grad **value is a register operand** set up by preceding ALU
(`bias(1.0)`/`level(1.0)` materialize one reg; `gradient2d` sets up 4 gradient regs). **op+7 bit2
(0x04)** flags a nonzero explicit LOD/bias operand is present (`level(0.0)` omits it → op+7=`0x00`;
`level(1.0)` → `0x04`). op+6 = `0x10` (filtered) for all three. Offset combines: level+offset = op+2
`0x1b`, implicit+offset = `0x01`.

## 4. LOD query + texture atomics
- **LOD query** `calculate_clamped_lod` / `calculate_unclamped_lod` = a **real texture op** (NOT a
  uniform read): sample bundle with **op+6 = `0x20`** (LOD-query mode), scalar result; clamped vs
  unclamped in **companion +3** (`0xa0` vs `0xa8`, bit3). **HW:** the op runs (`STATUS OK`); in
  compute it returns `0` (no fragment derivatives) — real per-pixel LOD needs a fragment stage.
  (Contrast the `get_width/height/num_mip_levels/num_samples/array_size` *queries*, which remain
  **no-instruction** preloaded-uniform reads per EXP-0016 — those are descriptor-supplied, not ops.)
- **Texture atomics — SUPPORTED (not rejected by Metal), HW-VALIDATED ✅.** Contrary to the brief's
  expectation, MSL **accepts** `atomic_fetch_add`/`atomic_fetch_max` on
  `texture2d<uint, access::read_write>` (r32uint) and `texture_buffer<uint, access::read_write>`.
  There is **no dedicated texture-atomic opcode** — they lower to the **EXP-0018 memory-family device
  atomic** (byte0 `0x67`, byte+2 `0x54`), computing the texel byte-address in-shader from the texture
  descriptor:
  - `texture_buffer` atomic = plain EXP-0018 encoding (`67 01 54 … <op@+12>`; add = `0x20`).
  - `texture2d` (2D-addressed image) atomic = byte+1 `0x11` and **op-byte = EXP-0018 code | 0x40**
    (add `0x20`→`0x60`, umax `0x38`→`0x78`) — bit6 marks the image-addressed atomic variant.
  - **Atomicity HW-proven** (`§7`): 256 threads `atomic_fetch_add` to one texel → **exactly 256**
    (no lost updates); `atomic_fetch_max(i)` over 256 threads → **255**; distinct-texel add → each 1.
  → Capability matrix: **image/texture atomics are NATIVE** on Apple9 (via the buffer-atomic path on
  the linear backing store) — no emulation needed for r32uint image atomics.

## 5. array / cube / 3D / MSAA coordinate operands
The **access dimension** is encoded two ways:
- **texture.read** puts the dimension in **op+2**: `0x17` 2D · `0x79` 3D · `0x97` 2D-array
  (`0x17|0x80`, bit7=array) · `0x80` MSAA (EXP-0016; 3D/array/MSAA read byte-diff, 2D read HW).
- **texture.sample** keeps the 2D LOD-mode byte and encodes dimension in the upper bits for cube/3D:
  **`0x13` cube · `0x39` 3D · `0x53` cube-array** (byte-diff); **2D-array sample stays `0x09`** and
  passes the slice as an extra operand.
- The **extra index** (array slice / cube-array slice / 3D w / MSAA sample index / compare ref) is an
  **additional coordinate register** packed by preceding ALU immediately after u,v, selected via
  **op+3** (`s_array` op+3=`0x01`, `r_ms_s` op+3=`0x14`). Bit-exact index packing is a follow-up
  (byte-diff localized, not splice-validated).

## 6. Answers to the brief
1. **sample_compare** — op+2 bit5 (`0x20`) = compare; compare-ref is a register operand (const &
   dynamic byte-identical); sampler compareFunction (EXP-0015) drives it; **HW shadow validated for
   all 8 compare funcs + dynamic ref + fractional linear PCF**. §1.
2. **gather / gather_compare / offset-gather** — gather result-desc + component in companion +3
   (bits[3:5], HW x/y/z/w→r/g/b/a); gather_compare = gather+`0x20`; offset in op+5 (HW: +1 column
   shift). §2.
3. **sample_lod/bias/grad** — op+2 `0x09`/`0x07`/`0x04`; value in a preceding-ALU register; op+7 bit2
   = present. §3.
4. **LOD query + atomics** — LOD query = real op (op+6 `0x20`); **texture atomics SUPPORTED &
   HW-atomic**, lower to the 0x67 device atomic (|0x40 for the 2D image form). §4.
5. **array/cube/3D/MSAA** — read dimension in op+2 (`0x17/0x79/0x97/0x80`); cube/3D sample in op+2
   (`0x13/0x39/0x53`); extra index = an added coord register (op+3). HW: 2D read; rest byte-diff. §5.

**Recommended next:** fragment-context LOD-query values (real derivatives); op+3 extra-coord bit
decode; depth-array/cube shadow; op+5 offset for the full [-8,7]² range.

## 7. Deliverables & clean-room status
- `new_descriptors.json` — refined `tex_sample` (compare/gather/offset/LOD-query fields + full op+2
  enum) + `tex_atomic` note-descriptor. Schema-compatible with `tools/agx-isa/db.json`; **this
  experiment did NOT edit `tools/agx-isa/`** (orchestrator merges).
- Harnesses: `tvcmp.m` (depth+compare sampler / LOD), `atomtex.m` (r32uint atomics), reused
  `texcomp`/`shdump`/`agxparse.py`.
- Clean. Everything inspected is our own compiled MSL; `raw/` holds only hex/text — no `.metallib`
  or Apple blobs. No Apple binary disassembled.
