# EXP-0016 Results — Texture / sample instruction family (HW-validated)

Clean-room category: **OWN-SHADER** (+ PUBLIC for the ISA DB / Mach-O format). Every
byte inspected or spliced is the compiled form of MSL **we wrote** (`kernels/tex_*.metal`).
No Apple binary was disassembled. Splice-and-observe forces our own archived (modified)
machine code via `MTLPipelineOptionFailOnBinaryArchiveMiss` (`PIPELINE_SOURCE archive`
proves it ran). Raw: `raw/mains.txt`, `raw/field_map.txt`, `raw/hw_validation.txt`.

## 0. TL;DR
The texture family is a small set of ops shared by **compute and fragment**:

| op | encoding | how proven |
|---|---|---|
| **sample / read** | 14-byte bundle: 4-byte coord/result **companion** (`05 80 0c CC`, low-nibble-5 byte0) + 10-byte **sampler op** (byte0 `0xb0`/`0x90`, low-nibble 0) | HW-validated |
| **write** | **`0xd7`**, 16 bytes (memory-family store, sibling of `0x67/0xe7`) | HW-validated |
| **derivative** (dfdx/dfdy/fwidth) | **`0x37`**, 10 bytes; axis at byte+6 (`0x92`=X, `0x90`=Y) | inferred (byte-diff) + HW-runs |
| **queries** (width/height/mips/samples/array) | **no instruction** — a preloaded-uniform read; value supplied by the driver from the texture descriptor | HW (byte-identical proof) |
| **sample_compare** (depth PCF) | distinct variant: companion byte0 **low-nibble 0xd** + a preceding compare-ref op | inferred (follow-up) |

`tools/agx-isa/` gained `tex_sample`, `tex_write`, `tex_deriv` descriptors + length rules;
`roundtrip_test.py` = **ALL PASS**.

## 1. Sample instruction field map (brief #1)

The sample is a **two-instruction bundle**: a 4-byte **companion** `05 80 0c CC` (byte0
low-nibble 5; bit5 set = a chained 2nd texture op in the same shader) immediately followed
by the 10-byte **sampler op** whose byte0 low-nibble is 0 and whose high nibble is a
result-register selector (`0xb0`/`0x90`/`0x30`). Offsets below are `op+N` inside the 10-byte
sampler op (see `raw/field_map.txt` for the aligned table).

| field | location | values / meaning | status |
|---|---|---|---|
| **variant / LOD-mode / dimension** | **op+2** | `0x00` sample(implicit LOD) · `0x04` grad · `0x07` bias · `0x09` level(explicit LOD) · `0x13` cube sample · `0x17` 2D read · `0x79` 3D read · `0x97` 2D-array read (`0x17\|0x80`, bit7=array) · `0x80` MSAA read | HW (sample/read); byte-diff (rest) |
| **texture-slot ref** | **op+4** | bit7 (`0x80`) = the texture-index bit (index 0↔1 proven). Indexes the per-stage bound-texture table → the arg-buffer texture-descriptor pointer (§3) | **HW-validated** |
| **sampler-slot ref** | **op+5** | sampler index (0→`0x00`, 1→`0x01`). Indexes the bound-sampler table → arg-buffer sampler-descriptor pointer | **HW-validated** |
| **coordinate register** | **op+1** (+ preceding ALU) | the interpolated/computed coordinate reg; array-slice / 3D-z / MSAA-sample index are extra coord regs set up by preceding ALU, referenced via op+3 | byte-diff |
| **result register(s)** | sampler-op byte0 high nibble + companion byte+3 | high nibble = result-reg selector; companion byte+3 `CC` = result width / gather component (`0xb8` full 4-comp sample, `0xa0` `.x`, `0xa4` gather.x, `0xac` gather.y). The 4 result comps are moved out by the following `0x97`/mov ops | byte-diff |
| **filtered flag** | **op+6** | `0x10` = filtered sample (uses the sampler + LOD); `0x00` for gather / read (unfiltered) | byte-diff |
| **explicit-LOD/bias present** | **op+7** | bit2 (`0x04`) set for `bias` / `level` / `read(lod)` | byte-diff |

**LOD / bias / gradient operands.** The *mode* is `op+2`; the *value* lives in a register
set up by the preceding ALU (bias(1.0)/level(1.0) materialize a constant reg; `gradient2d`
sets up 4 gradient regs — the `f_grad` shader shows the `4b/5b/6b/7b .. 29 04` moves right
before the bundle). `op+7` bit2 flags that such an operand is present.

**Gather** (`op+2` unchanged from sample but `op+6`=`0x00` unfiltered, companion byte+3
`0xa4`/`0xac`): the component selector is in the companion byte+3 (`x`→`0xa4`, `y`→`0xac`).

## 2. Texture read / write / query (brief #2)

- **Read** = the *same* sampler op as sample, with `op+2`=`0x17` (2D), `0x79` (3D),
  `0x97` (2D-array), `0x80` (MSAA); no sampler, `op+6`=`0x00`. Integer coordinates come in
  as the coordinate register(s); array/3D-z/MSAA-sample index are extra operands (op+3).
  **HW-validated:** `c_read` returned `texel[coord]` for all 16 texels exactly
  (`raw/hw_validation.txt` §5).
- **Write** = **`0xd7`**, 16 bytes — a memory-family *store* (low-nibble 7, sibling of the
  `0x67/0xe7` buffer load/store), NOT the sampler path. Source color register at byte+4;
  coordinate + texture-state in the tail. **HW-validated:** `c_write` moved buffer colors
  into `texel[coord]` exactly (`§6`).
- **Queries** `get_width/height/num_mip_levels/num_samples/get_array_size` — **no dedicated
  instruction.** All five compile to **byte-identical** code: a preloaded-uniform read
  (`0x97`/`0x1b` move family) of an abstract slot; the value is supplied by the driver from
  the texture descriptor. A width+height kernel reads two adjacent uniform slots (uniform
  offset byte `0x08` vs `0x18`) → property→slot by declaration order, resolved at bind.
  (Same "not in the shader code" phenomenon as buffer/texture binding indices.)

## 3. Texture & sampler slots ↔ argument-buffer descriptor pointers (brief #3)

- The sample op's **op+4 (texture slot)** and **op+5 (sampler slot)** are small indices into
  the shader's *per-stage bound-texture / bound-sampler tables*. HW-proven by splice:
  flipping op+4 bit `0x80` switched which **bound texture** was read (t1→t0), and splicing
  op+5 switched which **bound sampler** was applied (linear→nearest).
- Those tables are exactly the **Tier-2 argument buffer** decoded in **EXP-0011**
  (`BO 0x100000e0000 + 0x14a0`): each `[[texture(i)]]` is an **8-byte pointer** to a 32-byte
  texture descriptor, each `[[sampler(i)]]` an 8-byte pointer to a sampler descriptor. So the
  ISA texture-slot index → the *i*-th 8-byte pointer → the descriptor block the driver wrote.
- **Single-texture / single-sampler shaders always encode slot 0** (`f_sample`, `f_tex1`,
  `f_samp1` are **byte-identical** regardless of the Metal `[[texture(1)]]`/`[[sampler(1)]]`
  binding index) — the compiler assigns a fixed local slot and the Metal binding index is
  resolved at bind time via the argument buffer (same negative result as buffers, EXP-0001).
  Distinct slot values only appear when *two* textures/samplers are live in one shader.

## 4. Derivatives / implicit-LOD (brief #4)

- **Derivative op = byte0 `0x37`, 10 bytes.** `render_deriv` (`dfdx(uv)`, `dfdy(uv)`) emits
  four of them — `dfdx.x`, `dfdx.y`, `dfdy.x`, `dfdy.y` — with **byte+6 = `0x92` for the two
  dfdx (X axis) and `0x90` for the two dfdy (Y axis)** (differ by bit1). byte+7 = `0x40`
  const; byte+1/+3/+5 carry the src/dst regs and source component. Fine/coarse decode is a
  follow-up. HW: `render_deriv` produces the correct `dfdx+dfdy` pixel (EXP-0008).
- **Implicit-LOD sample does NOT emit a separate `0x37`** — the LOD is computed inside the
  texture unit (`op+2`=`0x00`, `op+6` filtered). A `0x37` appears only for *source-level*
  `dfdx`/`dfdy`/`fwidth`. (The `0x38/0x39/0x90/0x92` EXP-0008 flagged are sub-byte values of
  the `0x37` op and adjacent `0x09` combine ALU, not independent byte0 leaders.)

## 5. HW validations (all `PIPELINE_SOURCE archive`, zero GPU wedges) — `raw/hw_validation.txt`
1. **sample runs + coordinate→texel** — `f_sample` over a 4×4 distinct-texel grid maps each
   pixel 1:1 to the texel its coordinate selects (16 distinct values; Y-flipped as expected).
2. **two_tex baseline** — `t0(60,20,0,128)+t1(0,0,180,64)` = `(60,20,180,192)` exactly.
3. **texture slot** — splicing sample#2 `op+4` bit `0x80` (tex1→tex0) changed the pixel from
   `t0+t1`=`(0.235,0.078,0.706,0.753)` to `t0+t0`=`(0.471,0.157,0.000,1.000)` (blue→0). ✅
4. **sampler slot** — splicing two_samp sample#2 `op+5` (samp1→samp0) flipped 55/64 pixels
   from linear-interpolated to nearest-quantized green. ✅
5. **texture.read** (`0xb0` mode `0x17`) — `c_read` returns `texel[coord]` for all 16. ✅
6. **texture.write** (`0xd7`) — `c_write` writes `in[i]` into `texel[coord]` for all 16. ✅

## 6. Capabilities richer than / different from Metal's surface (for `hypotheses.md`)
- **Read and write use different hardware paths.** `texture.read` goes through the *sampler*
  op (format-converting, `op+2`=`0x17`, no sampler bound), while `texture.write` is a plain
  *memory-family store* (`0xd7`). Read supports the full dimension matrix (2D/array/3D/MSAA)
  via one `op+2` byte.
- **Gather carries a component selector** (companion byte+3 `0xa4`/`0xac`), and `op+2` is a
  single dimension/mode byte with room for more values than Metal exposes (e.g. an unused-bit
  sweep of `op+2`/companion byte+3 is a good capability probe — offset-gather, other gather
  components, LOD-query modes).
- **Texture queries are free** (preloaded uniforms from the descriptor), so `get_*` costs no
  ALU — but it means array/size info must be *bound* by the driver, not derived in-shader.
- Sampler *state* (address/filter/border/aniso/compare) is **not** in the AGX stream — it is
  the sampler descriptor the op+5 slot points at (a `docs/descriptors/` item; EXP-0015).

## 7. Answers to the brief
1. **Sample field map** — §1: variant/dimension `op+2`, texture slot `op+4` (HW), sampler
   slot `op+5` (HW), coordinate `op+1`, result reg (sampler-op byte0 hi + companion byte+3),
   filtered `op+6`, LOD/bias/grad present `op+7` bit2, operand value in a preceding ALU reg.
2. **Read / write / query** — §2: read = sampler op mode `0x17/0x79/0x97/0x80`; write = `0xd7`
   (16B store); queries = preloaded uniforms (no instruction).
3. **Slot ↔ arg-buffer** — §3: op+4/op+5 index the per-stage texture/sampler tables = the
   EXP-0011 Tier-2 argument-buffer 8-byte descriptor pointers at `+0x14a0`.
4. **Derivatives** — §4: `0x37` (10B), axis in byte+6 (`0x92` X / `0x90` Y); implicit-LOD is
   internal to the sample op.
5. **Round-trip / faults / next** — `roundtrip_test.py` **ALL PASS** (29 descriptors, +3
   texture). **Zero GPU wedges / reboots** across all extraction + HW runs. Recommended next:
   full result/coordinate-register bit decode; depth-compare (`sample_compare`) op; array/3D/
   cube/MSAA index-operand bit positions; derivative fine/coarse; sampler-descriptor bits
   (with EXP-0015).

## 8. Clean-room status
Clean. Everything inspected/spliced is the compiled form of our own MSL. Tools are ours
(`shdump`, `agxparse.py`, `texr.m`, `texcomp.m`, `analyze.py`); the only third-party code is
the public ISA DB (`tools/agx-isa/`) applied to our own bytes. No Apple binary was
disassembled; `raw/` holds only hex/text — the `.bin` archives stay on the device.
