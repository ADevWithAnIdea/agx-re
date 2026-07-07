# A18 Pro (G17P) AGX Shader ISA

Clean-room documentation of the Apple G17P shader instruction set. All facts here come from
disassembling **shaders we compiled ourselves** (OWN-SHADER) + public references (PUBLIC) —
never from Apple binaries. See `../../CLAUDE.md`.

> **Status: early, but the validation loop is live.** The extraction pipeline AND the hardware
> testbed (`tools/agxtest/`, EXP-0003) both work: we can splice arbitrary bytes into our own
> compiled shader and run them on the real GPU (Metal runs tampered code with **no integrity
> check**, given a binary archive + `MTLPipelineOptionFailOnBinaryArchiveMiss`). So encodings can
> now be **hardware-validated** (✅), not just inferred from byte diffs (⏳ pending round-trip).
> Do not treat ⏳ items as final; ✅ items are proven by running modified code and observing output.

## How we get the bytes (validated — EXP-0001)

Our own MSL → runtime `newLibraryWithSource:` → compute pipeline → `MTLBinaryArchive`
`serializeToURL:` → parse with **our own** parser (`tools/shdump/agxparse.py`):

- The serialized archive is a **Metal fat binary** (magic `0xCBFEBABE`).
- Inside, the **AppleGPU** image = Mach-O `cputype 0x1000013` (the native GPU code we want),
  distinct from the **AIR64** image `cputype 0x1000017` (LLVM bitcode; `MTLB`/`BC\xC0\xDE`).
- The AppleGPU image's `__TEXT,__compute` section is itself a **nested Mach-O**; its
  `__TEXT,__text` holds the code, split by symbols into:
  - `_agc.main` — the shader program.
  - `_agc.main.constant_program` — a fixed 64-byte prolog ("constant program").
- **Evidence it is machine code, not IR:** the AIR64 image carries the `BC\xC0\xDE` magic; the
  AppleGPU `__text` does not and does not parse as bitcode. An empty kernel's whole body is a
  single 4-byte word (raw instruction, not IR). Determinism: identical source → byte-identical
  `_agc.main` across repeated compiles (sha256-stable).

## Preliminary encoding observations (EXP-0001)

Byte-level facts (established) and their interpretations (⏳ pending round-trip validation):

- **Instruction parcels are 2 bytes.** All observed region lengths are even. ⏳ (variable-length
  instructions built from 2-byte parcels, as on G13, is the working hypothesis.)
- **✅ Float ALU op-select (HARDWARE-VALIDATED, EXP-0003):** in a `c=a+b` kernel, the byte at
  file/program offset **`0x22`**, **bit 0**, selects the float ALU op: **`1c`=fadd, `1d`=fmul**.
  Proven by splicing `1c→1d` and observing the dispatch output change from `a+b` to `a*b`
  (`1,2,3…×10,20,30…` → `10,40,90,…`), byte-identical to the compiler's own `fmul` output.
- **`0e000000` is NOT a simple required trailing stop (revised, EXP-0003).** Corrupting it (past
  the store) did not fault; program extent appears bounded by metadata / the final store, not by
  a mandatory terminator word. ⏳ true program-end / control-flow-termination encoding still TBD.
- **Fixed preamble:** every non-empty `_agc.main` begins `1c a0 10 06 …`. ⏳ role TBD.
- **Packed float immediate:** `a+1.0` vs `a+2.0` differ in **one byte** (bits 4–6), and the
  value is **not** IEEE-754 (`3f800000`/`40000000` do not appear) — a compact/packed float
  immediate encoding. ⏳ exact encoding TBD (sweep needed).
- **Source-register selectors:** `a-b` vs `b-a` swap two bytes (complementary `00↔01`) → the
  two source operand fields. ⏳ register-index bit layout TBD.
- **Integer vs float ALU use different encoding paths** (int-add vs float-add differ in length
  and many bytes).

### Negative result (EXP-0001)
- **Buffer *binding index* is not in the shader code.** Writing `buffer(0)` vs `buffer(1)`
  produced byte-identical `_agc.main`, prolog, *and* `__TEXT,__descriptor`. The compiler assigns
  the referenced buffer a fixed uniform slot; the Metal binding index is resolved at bind time
  (argument/uniform table), outside the AGX program. → A cmdstream/descriptor-phase question.

## Extraction & testbed now cover compute, vertex, AND fragment (EXP-0008)
- `shdump --render` compiles our own `[[vertex]]`+`[[fragment]]` MSL and extracts both stages.
  Archive layout: the same Metal fat binary → one AppleGPU image, with **vertex and fragment as
  separate `__TEXT,__vertex` / `__TEXT,__fragment` sections** in that one image (compute is
  `__TEXT,__compute`); each is a nested Mach-O carved by `_agc.main`/`_agc.main.constant_program`
  exactly like compute. `agxparse.py --stage {compute,vertex,fragment}` selects the stage.
- `tools/agxtest/agxrender.m` — a **render testbed**: draws a full-screen triangle with our own
  archived vertex+fragment code into a small target and reads back pixels, and **runs modified
  fragment code** (splice-and-observe validated: editing a fragment byte moved the output pixel
  color). The extrapolate-and-test loop now works for fragment shaders too.
- **New instruction groups seen only in vertex/fragment code** (byte0 leaders; ⏳ lengths/semantics
  pending a decode experiment): low-nibble-`f` ALU `0x2f/0x3f/0xaf` (interp/tex/deriv), extra
  memory `0x07/0x87/0x97/0xa7`, vertex varying-stores `0x05/0x06/0x57`; by feature-attribution,
  **texture sample** adds `0x18/0xb0`, **derivatives** add `0x37/0x38/0x39/0x90/0x92`.

## Instruction encoding (EXP-0005)

The machine-readable, authoritative encoding lives in **`tools/agx-isa/`** — one descriptor
table (`db.json` / `isadb.py`) drives both the **assembler** and **disassembler**, with a
passing round-trip test (`asm(disasm(bytes))==bytes` on 14 real instructions; `disasm(asm(x))==x`
on 5 synthesized). Prose summary below; treat the DB as source of truth.

> **Encoding tables (all instruction descriptors, rendered):** [`encoding-tables.md`](encoding-tables.md) — the self-contained, per-instruction bit-field tables (byte0 group, length, match bits, every field + enum), grouped by family; generated from `db.json` by `tools/agx-isa/gen_encoding_tables.py` (EXP-0036).

Encoding is **little-endian**: instruction bit 16 = byte +2 bit 0.

### ✅ Instruction-length rule (validated — tokenizes all our shaders cleanly)
Parcels are 2 bytes. **Unlike G13, the *first* parcel does not encode length** (e.g. `fsub` 6B
and `fma` 8B share an identical first parcel). Length is a function of the byte-0 group, with a
per-group length bit where needed:

| byte 0 | group | length (bytes) |
|---|---|---|
| `0x0e` | stop | 4 |
| low-nibble `0xC` | preamble | 4 |
| low-nibble `0x7` (`67`/`e7`) | device load/store | 14 |
| `0x09` | **float ALU (2-src)** | 6, or **8 if `byte[+2] & 0x02`** (the fma/length bit) |
| `0x0b` | float unary | 10 |
| `0x12` | float min/max | 6 |
| `0x9f` | integer ALU | 10/12 — **not yet solved (follow-up)** |

Proof: `agxisa.py tokenize` splits all 11 float `_agc.main` programs into instructions with 0
leftover bytes and re-serializes byte-exact. (Integer kernels, byte0 `0x9f`, still uncovered.)

### ✅ Float ALU 2-source op-select (HARDWARE-VALIDATED, 256-value sweep)
For the `0x09` float-ALU instruction, the op-select is a **3-bit field = instruction bits
[16:19]** (low 3 bits of byte +2):

| bits[16:19] | op | status |
|---|---|---|
| `0b100` | **fadd** (`a+b`) | ✅ HW-validated (all 8 don't-care combos) |
| `0b101` | **fmul** (`a*b`) | ✅ HW-validated |
| `0b111` | illegal → contained GPU hang | HW-observed |

Field decomposition (from the sweep): bit 0 = add/mul (the EXP-0003 bit, now seen as bit 0 of a
wider field); bit 1 = length/fma bit; bit 2 = arithmetic-enable; bits 3–5 = don't-care; bits 6–7
set ⇒ srcA passthrough. Only add/mul are *validated*; sub/min/max/fma use different formats
(inferred, tracked in `db.json` provenance — not claimed as op-select values).

### ✅ Float ALU 2-source operand encoding (HARDWARE-VALIDATED, EXP-0006)
6-byte `falu2` instruction, little-endian (bit b → byte b//8, bit b%8):

| bits | field | meaning |
|---|---|---|
| `[0:4]` | group | `0x9` = float ALU |
| `[4:8]` | **dst** | destination register number |
| `[8]` | srcA size | 1 = 32-bit, 0 = 16-bit (reads low halfword) |
| `[9:16]` | srcA reg | source-A register number |
| `[16:19]` | op-select | `100`=fadd, `101`=fmul (see above) |
| `[19]` | imm sign | sign bit when srcB is an immediate |
| `[24]` | srcB size | 1 = 32-bit, 0 = 16-bit low half |
| `[25:32]` | srcB reg | source-B register number (or minifloat when imm mode) |
| `[39]` | **srcB imm mode** | 0 = srcB is a register, 1 = srcB is an immediate |
| `[43]` | **srcB negate** | negate source B (`a + (−b)` ⇒ subtract) |

- **Source operand byte = `(reg << 1) | is32`.** 16-bit reads the low halfword of the 32-bit
  register (HW-confirmed: a 16-bit read returned the low half of the float32).
- **No srcA-negate bit in the 6-byte form**; the compiler commutes operands to reuse srcB-negate.
- **abs / extended modifiers** live in a distinct **10-byte** extended form (`09 01 1c 05 02 00
  00 80 0X 00`); HW-validated `a+|b|`. There is also a `0x10` native-half 2-source group — both
  noted for follow-up.

### ✅ Machine model — registers, uniforms, Dynamic Caching (EXP-0020, supersedes EXP-0006 "64")
- **96 addressable 32-bit GPRs per thread** (r0–r95). The compiler's register footprint grows then
  caps at exactly 96; a kernel with 93 live regs + zero scratch runs correctly. (EXP-0006's "64" was a
  tiny-shader artifact of the nibble-compacted `falu2` dst field.)
- **16-bit halves are independently addressable, packed 2 per GPR** (64 `half` values → 50 GPRs).
  Native-half access is via the `0x10`/`0x11` groups; the `0x09` 32-bit form's size bit reaches only the
  low half.
- **Register-field widths:** the 6-byte `falu2` dst is a 4-bit nibble (r0–r15 compaction); high float dst
  uses the 8-byte `falu3` form (`dst=byte+1`, 7-bit; r64 observed). Integer `dst=b3` and all source
  fields are 7-bit `(reg<<1)|size` (span r0–r127, covering the 96-reg file).
- **Uniform register file:** a source operand selects **GPR vs uniform** via a per-source mode bit
  (int `0x9f`: uniform-srcB byte+5 bit4, uniform-srcA byte+6; float `0x09`: byte+2 bit4 / byte+5 bit1 —
  ⏳ byte-diff inferred, not yet splice-validated). `uniform_mov` (4 B, `Xb YY 01 08`) copies uniform→GPR.
  ≤128 uniform regs (8-bit index); exact count ⏳.
- **Footprint declaration:** the exact GPR/scratch/uniform/threadgroup footprint is in the shader
  binary's own `__GPU_METADATA` FlatBuffer (field 0 = GPR count, 14/41 = scratch bytes, 31 = uniform,
  9 = threadgroup) — this is *our own* compiled shader's metadata (OWN-SHADER). The launch-descriptor
  `+0x00` config word carries only a coarse **2-level occupancy tier** (bit 23: clear ≤11 GPRs, set ≥12).
- **Dynamic Caching / spill:** above 96 GPRs the compiler spills to **per-thread scratch (stack)** memory
  (scratch size in `__GPU_METADATA`); spilled kernels (80–256 regs) compute correctly. A compiler must
  know: 96 GPRs before spill, 2 halves/GPR, scratch cost, and the ~12-GPR occupancy tier. ⏳ whether 96 is
  hard silicon or a policy cap, and the scratch-base location, are follow-ups.

### ✅ Packed float immediate = 8-bit minifloat (HARDWARE-VALIDATED, EXP-0006)
When srcB imm mode (bit 39) is set, srcB byte encodes an **8-bit minifloat** (NOT IEEE-754):
`[exp:4 (bits 7:4, bias 11)][mant:3 (bits 3:1)][flag:1 (bit 0 = 1)]`, sign at instruction bit 19.
- normal (exp ≥ 9): `value = (1 + mant/8) · 2^(exp−11)`
- subnormal (exp = 8): `value = (mant/8) · 2^−2`
- representable magnitudes: `{0, 1/32 … 30.0}`; out-of-range / non-dyadic constants fall back to a
  register-load form. Worked examples: `1.0→0xb1`, `2.0→0xc1`, `1.5→0xb9`, `3.5→0xcd`,
  `0.0625→0x85`, `30.0→0xff` (max). All 16 tested constants spliced and produced exact `a+K`.

### ✅ Integer ALU family (EXP-0007)
Integer ops are **spread across several byte0 groups** (each its own format), mirroring the float
split — there is **no single unified integer op-select**. `isub` = `iadd` with srcA-negate +
operand-commute (same trick the compiler uses for `fsub`).

| byte0 | len | operation(s) | op-select | status |
|---|---|---|---|---|
| `0x9f`/`0x1f` | 10 | iadd / isub | `b0 bit7` = srcA-negate | ✅ HW |
| `0x9f`/`0x1f` | 12 | imul / imad | 3-source multiply-add (imul = imad, c=0) | ✅ HW (behaviour) |
| `0x02` | 6 | imin/imax/umin/umax | `b4[0:3]`: bit0 min/max, bit1 signed/uns, bit2 int | ✅ HW |
| `0x0b` | 10 | iand/ior/ixor | `b2[0:4]` + `b4/b5` src-invert | ⏳ toggle/byte-diff |
| `0x12` | 14 | compare → select 0/1 | `b4` cond, `b6` sign | ⏳ byte-diff |
| `0xa7` | 10/12 | shift-right / bitfield-extract | multi-instr for reg shifts | ⏳ byte-diff |
| `0x27` | 8 | popcount / unary | — | ⏳ byte-diff |

- **Integer length rule:** for `0x9f`/`0x1f`/`0xa7`, the 10-vs-12-byte selector is **byte +1 bit 0**
  (contrast the float group's byte +2 bit 1). Tokenizes all 26 integer shaders with 0 leftover.
- **Operand encoding (differs from float):** **dst = `b3`** as `(reg<<1)|size` (float dst was
  `b0[4:8]`) — the wider field leaves room for **>16 registers**; srcA/srcB packed in the `b7:b8:b9`
  tail (`(reg<<1)` convention, exact widths a follow-up).
- **Integer immediate = `(K<<1)`**, plain 8-bit unsigned inline at `b5` (+`b6` bit 0) — HW-validated
  for K∈{0..255}; ≥256/negative materialize to a register. **Not** the float minifloat encoding.
- Note: a load/store opcode-keying bug was fixed here (`0x67`/`0xe7` exact, was low-nibble `0x7`
  which collided with `0xa7`/`0x27`).

### ✅ Control flow, predication & program structure (EXP-0010)
- **Preamble = get-special-register** (`get_sr`, byte0 low-nibble `0xC`, 4B): materializes special
  registers into a GPR. **(Corrected by EXP-0031: the SR number is in `byte1`; the byte0 high nibble is
  the destination GPR — not the SR-select.)** See the SR-enum + ABI section below. There is also a 2-byte
  **`mov_imm`** (byte0 low-nibble `0xC`, byte1 = imm8) sharing the nibble.
- **Simple divergence is predication, not branches.** `if/else`/ternary/early-return compile to
  **compare → per-lane execution mask → masked op / select** (no jump). Compare producers: `0x0a`
  (6B, control predicate) and `0x02` (6B, feeds a select); compare immediate at **byte+3**. Selects:
  `0x05`/`0x16` (4B). Proven: splicing the compare immediate moves the active-lane boundary; flipping
  `0x0a`↔`0x02` inverts the condition.
- **Loops use a real backward jump:** `0f 00 54 <off6> 00` (10B), `off6` = **signed little-endian
  byte-relative offset**. `0x0f` is the control-flow / execution-mask group (byte+1 sub-op: `00`=jump,
  `05`/`01`=mask push/else, `06`=pop/reconverge). Zeroing the back-edge → contained infinite-loop hang
  (proves it's the taken edge). Fixed-count loops are fully **unrolled**.
- **Program termination:** `0e000000` is **not** a required terminator (splicing it is a no-op); the HW
  stops after the last real instruction — **program length is out-of-band (section/pipeline metadata)**,
  the final `device_store` is the last effective instruction. A `0f 06 …` reconverge word follows
  predicated blocks (block-end, not shader-end).

### ✅ How uniforms & buffer pointers reach registers (EXP-0010)
- **Buffer base pointers are preloaded into a uniform/binding slot**, selected by **`device_load`
  byte+4** (HW-proven: splicing the slot changes which bound buffer is read). The pointer is *not* in
  the shader code (consistent with EXP-0001's negative result) and *not* in the constant_program — it
  is supplied by the command stream / USC (see `../cmdstream/`).
- **Scalar uniforms** (`constant T&`) are preloaded into a **uniform register** read directly by the
  ALU (no `device_load` emitted). ⟶ There *is* a uniform register file, surfaced here as source slots;
  its full addressing is a follow-up (ties into Dynamic Caching).
- The `_agc.main.constant_program` prolog is the **"uniform program"** (EXP-0020): a separate
  uniform/scalar datapath that `device_load`s the uniform buffers and runs the uniform ALU to compute
  **thread-invariant** expressions, leaving results in uniform registers (read directly by the main
  program). This resolves its earlier "advisory prolog" mystery.

### ✅ Memory access family (EXP-0012)
Device & threadgroup load/store share opcodes `0x67` (load) / `0xe7` (store), 14 bytes:

| byte | field | meaning | status |
|---|---|---|---|
| +0 | opcode | `0x67` load / `0xe7` store | ✅ |
| +1 | space + index | **bit1 (`0x02`) = threadgroup** (else device/global); higher bits = index GPR | ✅ space / ⏳ reg |
| +3 | extmode | bit1 = unsigned/zero-extend variant | ⏳ |
| +4 | **base_slot** | preloaded buffer-base uniform slot (0=buf0, 1=buf1, …) | ✅ |
| +5 | **count** | # consecutive 32-bit words = **vector width** (1/2/3/4), not a mask | ✅ |
| +8 | dst/data + width | dest/data reg + data width (`51`=32b, `41`=16b, `61`=8b, `59`=64b) | ✅ width / ⏳ reg |
| +12 | **elem_size** | address element size, bits[1:4]=k → `2^(k-1)` bytes (`42`=1,`44`=2,`46`=4,`48`=8) | ✅ |

- **Addressing model: element addressing, no in-instruction offset.** Effective byte address =
  `index_GPR × element_size`. `a[i+k]` / `a[i*s]` are computed by a **prior integer ALU op** on the
  index (in element units); the load just consumes the result GPR. (HW-proven: `a[gid+1/+2/+4]` and
  `a[gid*2/*4]` all share a byte-identical load; the offset lives in the preceding `iadd` immediate.)
- **Vectors:** `float4`/`int4` = one load + one store moving 4 words (`count`=4 at +5).
- **Sign extension:** signed sub-32-bit loads are **sign-extended by a following ALU shift** (`0xa7`),
  not by the load; unsigned use the zero-extend load variant (byte+3 bit1). HW-validated.
- **Threadgroup memory:** same `0x67`/`0xe7` with byte+1 = `0x02` (address-space selector) and
  base_slot `0x08` (local); lid-derived offset. (The vtx/frag `0x07/0x87/0x97/0xa7` groups are *not*
  threadgroup memory.)
- **Constant address space** (`constant T*` indexing) is **byte-identical** to a device load — the
  device/constant distinction is not in the ISA (it's in the binding). Scalar `constant T&` stays a
  preloaded uniform-register read (no load), per EXP-0010.
- **Atomics** are in the **memory family** (byte0 `0x67`) as **native single-RMW ops** — see the
  Atomics section below. (Corrects EXP-0012's initial guess of a "`0xbf` CAS loop": `0xbf` is actually
  the SIMD-reduce op, and the surrounding `0f05`/`0f06` are elect-one-lane predication, not a retry loop.)

### ✅ Scalar ALU completion — conversions, fma, unary, transcendentals, bitwise, shift, compare (EXP-0013)
DB now has **24 HW-validated descriptors**. Summary (all HW-validated unless noted):

- **Conversions:** fp32→fp16 = new group **`0x11`** (half-ALU, 6B); fp16→fp32 = ordinary `falu2` with a
  16-bit srcA (the *only* size-bit reuse). float→int = **`0x27`** (10B, **rounds toward zero**);
  int→float = **`0xa7`** (8B). **Signedness for both = byte+7 bit6.** int narrow+sign-ext = `0x9f`;
  zero-extend-16 = **`0x13`** (4B); `int↔uint`/`as_type` bitcast = **no instruction** (free).
- **FMA** (`d=a*b+c`): `0x09` 8-byte form, srcA=byte+3, srcB=byte+4, **srcC=byte+5**.
- **Float unary** (`0x0b`, 10B): byte+5 = `0x00 fmov / 0x02 fabs / 0x0a fneg`.
- **Transcendental/round group** (`0x2f`/`0xaf`, 10B): exp2/log2/floor/ceil/trunc/rint, with a
  **round-mode field at byte+8** (0 nearest, 2 floor, 4 ceil, 6 trunc). frcp/frsqrt/fsqrt/fsin/fcos are
  **multi-instruction Newton-Raphson** (0x29 estimate seed) — ⏳ follow-up.
- **fmin/fmax** (`0x12`, 6B): byte+4 bit0 = min/max; IEEE minNum/maxNum (returns the non-NaN operand).
- **Bitwise** (`ilogic`, `0x0b`): a **full 2-input LUT covering all 16 boolean functions** (selectors
  byte+2 + byte+4/+5 inverts) — covers every Vulkan/GL logic op. See `../hypotheses.md`.
- **Shifts:** arithmetic `>>` imm = `0xa7` 10B (amount = byte+6>>2); logical `>>` imm = `0xa7` 12B
  extract; `<<` imm = `0x9f` 10B; `extract_bits` = `0xa7` 12B. Register-amount shifts are multi-instruction.
- **Compare condition codes** (`0x12` icmpsel, 14B): byte+6 = `0x02 f> / 0x03 f< / 0x04 u> / 0x05 u< /
  0x06 s> / 0x07 s<` (bits[1:3]=type float/uint/sint, bit0=lt/gt); byte+4 = `0x22 ordered / 0x26 equality`;
  result-negate (ge/le/ne) = byte+5 bit0 + byte+9 bit0. One op handles float and signed/unsigned int.

### ✅ Texture / sample family (EXP-0016)
- **Sample = 14-byte bundle:** a 4-byte coord/result **companion** (`05 80 0c CC`, byte0 low-nibble 5;
  bit5 = chained 2nd tex op) + a 10-byte **sampler op** (byte0 `0xb0`/`0x90`, high nibble = result-reg
  selector). Fields (`op+N`):
  - **variant / dimension / LOD-mode = op+2:** `0x00` sample(implicit-LOD) · `0x04` grad · `0x07` bias ·
    `0x09` level · `0x13` cube · `0x17` 2D read · `0x79` 3D read · `0x97` 2D-array read (bit7=array) ·
    `0x80` MSAA read.
  - **texture-slot = op+4** (bit `0x80` = index) — HW-validated (splice tex1→tex0 changed the pixel).
  - **sampler-slot = op+5** — HW-validated (splice samp1→samp0 flipped linear→nearest).
  - **coord = op+1** (+ preceding ALU); result reg = sampler-op byte0 hi + companion byte+3;
    **filtered = op+6** (`0x10` sample vs `0x00` gather/read); explicit-LOD/bias present = op+7 bit2
    (the LOD/bias/grad *value* comes from a register set up by a preceding ALU op).
- **Texture read** = same sampler op, mode op+2 = `0x17/0x79/0x97/0x80`, no sampler (HW-validated).
- **Texture write = `0xd7`, 16 bytes** — a **memory-family store** (sibling of `0x67`/`0xe7`), *not* the
  sampler path (HW-validated).
- **Texture queries** (`get_width/height/num_mip_levels/num_samples/array_size`) = **no instruction**:
  compile to a preloaded-uniform read; the driver supplies the value from the texture descriptor.
- **Derivatives = `0x37`, 10 bytes** (axis byte+6: `0x92`=dfdx, `0x90`=dfdy). Implicit-LOD sampling does
  *not* emit `0x37` — LOD is computed inside the texture unit; `0x37` is only for source `dfdx/dfdy/fwidth`.
- Slots op+4/op+5 index the Tier-2 argument-buffer texture/sampler tables (see `../cmdstream/`,
  `../descriptors/`); single-resource shaders always encode slot 0.
- ⏳ Follow-ups: result/coord register bit decode; `sample_compare` (depth PCF, distinct companion
  low-nibble `0xd`); array/3D/cube/MSAA index-operand bit positions; derivative fine/coarse.

### ✅ Atomics (EXP-0018)
Atomics are **native single-RMW ops in the memory family** (byte0 `0x67`), *not* CAS loops.
`atomic_rmw` = `67 11 54 00 00 <addr> 42 00 00 <OP> 00` (14 B). **base_slot at byte+4** (same slot model
as loads); **device vs threadgroup = byte+1 bit1** (as in `../isa` memory). **Operation at byte+12**
(HW splice-proven):

| op | code | op | code | op | code |
|---|---|---|---|---|---|
| add | `0x20` | sub | `0x36` | and | `0x22` |
| or | `0x2c` | xor | `0x3e` | fadd | `0x26` |
| smax | `0x28` | smin | `0x2a` | umax | `0x38` |
| umin | `0x3a` | exchange/store | `0x3c` | cmpxchg | `0x24` |

`cmpxchg` is a single op + a following `icmp` for the bool (no loop). Device atomics to a *uniform*
address get a compiler optimization: SIMD-reduce → one-lane RMW → prefix-broadcast (32 transactions → 1
per simdgroup). Aggregate HW-validated (1024 threads → counter 1024; op-splice add→max → 32).

### ✅ Subgroup / SIMD-group & quad ops (EXP-0018) — SIMD width = 32
- **`simd_reduce`** (byte0 `0xbf`/`0x3f`, 8 B, byte+2=`0x56`): reduce & prefix-scan. Op = (byte0 bit7,
  byte+1); byte+7 = datatype/shape (`0x03` int, `0x07` int-minmax, `0x12` float, `0x0b` exclusive-scan,
  `0x09` inclusive-scan). **Prefix-scan is native.**
- **`simd_shuffle`** (byte0 `0x47`/`0xc7`, 10 B): broadcast / shuffle(xor/up/down) / rotate / dynamic
  shuffle. byte+1 = simd/quad/rotate; byte+6 = lane/mask as `(value<<1)`.
- **`simd_ballot`** (byte0 `0x17`, 10 B): ballot / active-mask / all / any / is_first.
- **Quad ops** reuse the same two groups at **width 4** (reduce with scope bit3=0 → byte0 `0xb7`/`0x37`;
  shuffle with byte+1=`0x00`). Note `0x37` disambiguates quad-reduce (byte+2=`0x56`, 8 B) from the
  derivative op (10 B).

Capability notes (`../hypotheses.md`): float atomic min/max and 64-bit atomic-add are **not exposed by
MSL** (→ Vulkan must emulate); prefix-scan is native (not a shuffle-tree lowering).

### ✅ Dedicated matrix unit — `simdgroup_matrix` (EXP-0022)
Apple9 has a **dedicated matrix/MAC-array unit**, not a lane-cooperative FMA emulation:
`simdgroup_multiply_accumulate` compiles to a **single novel opcode `0xcf`** (12 B) that performs a full
**8×8×8 tile MAC** (512 scalar MACs). Proven dedicated: a hand-written FMA matmul and a
`simd_shuffle`+`fma` cooperative matmul both contain **zero** `0xcf`.
- **`matrix_mac` (`0xcf`, 12 B):** `d = a·b (+c)`, row-major 8×8. **byte+7 = C accumulator source reg**;
  **byte+11 bit0 = accumulate-enable** (splice `01→00` drops the `+c`) — both HW-proven. Inferred:
  byte+1 = dtype (`0x00` half / `0x02` float-bf16), byte+2 = mode (`0x56` standalone / `0x54` tiled),
  A/B/dst selectors packed across byte+3..+6/+8..+9 (partial).
- **Dims:** MSL exposes only **8×8** (16×16/8×16/4×4/32×32 rejected). **Types:** fp16, fp32, bfloat, and
  mixed fp16/bf16 → fp32 accumulate; **all integer types rejected** (no int8 coopmat via Metal → Vulkan
  int8 cooperative-matrix must emulate).
- **Fragment load/store** = ordinary `0x67`/`0xe7` memory ops (64-bit load = 2 fp32/lane; 32 lanes × 2 =
  the 64-element 8×8 tile); `make_filled` = a `0x2c`/`0x3c` constant splat. Only the MAC is dedicated silicon.
- **Tensor ops** (`mpp::tensor_ops::matmul2d`, 32×32×32) compile on-device and lower to **259× the same
  `0xcf`** — larger shapes are software-tiled over the 8×8×8 primitive.
- HW-validated: A·B+C with distinct known A,B,C returns correct C.

### ✅ Hardware ray tracing — HYBRID (EXP-0023)
Apple9 has **dedicated ray-tracing instructions** that drive a **compiler-generated (software) BVH-
traversal loop** in the shader — not one fire-and-forget "trace ray" op. Proven dedicated: both novel
opcodes are absent from a hand-written Möller-Trumbore ray/triangle control.
- **`rt_intersect`** (byte0 low-nibble `0x4`, byte+1 `0xea`, 8 B): the hardware ray/box/triangle
  intersection primitive. byte0 hi = result reg; byte+2 mode (`0x90` const-origin / `0x10` dynamic-origin
  / `0xd0` + function-table); byte+3/+4 = ray/AS operand regs (instance-AS flips byte+4 `0x8b→0x1b`);
  byte+6 bit7 = intersection-function-table bound. Emitted twice (traverse, then result-read). Fields
  byte-diff-inferred; role + end-to-end correctness HW-validated.
- **`rt_as_load`** (byte0 `0xdf`, 14 B): dedicated acceleration-structure / ray-data node loads
  (14–37 per RT kernel). The traversal is a shader loop (a `−88`-byte back-edge whose body holds a `0xdf`
  node-load + `0x0a` loop-condition compare).
- **Acceleration structure** is referenced by an **8-byte GPU VA in the Tier-2 argument buffer**. ⚠ The
  **BVH *build* is GPU/firmware-managed** — userspace supplies vertices + a build descriptor; the GPU
  writes the BVH; the **BVH node format is NOT userspace-visible** (kernel-interface item, like ZLS /
  sample positions).
- **Intersection functions** compile as separate callable functions bound via an
  **`intersection_function_table`** (same model as `visible_function_table`); `ray_data` payload is a
  distinct address space.
- HW-validated: 6 known rays vs a built `MTLAccelerationStructure` (triangle at z=3) → correct t / prim /
  barycentrics; above-apex ray correctly misses. ⏳ Follow-ups: full operand bit-decode; the WWDC
  "reorder" stage; RT-from-render + motion blur.

### ✅ Async completion = hardware register interlock, NOT a software scoreboard (EXP-0025) — CRITICAL compiler guidance
**G17P has no explicit per-op scoreboard `wait` instruction.** Long-latency ops (device load/store,
atomics, texture sample/read) feed their consumers directly; completion is enforced by a **hardware
register interlock** — a consumer that reads a still-pending destination register **stalls in hardware**
until the op retires. This is a **fundamental departure from G13** (which used an explicit 2-byte `wait`
op + a 2-slot software scoreboard, `AGX_MAX_PENDING=8`).
- **Compiler implication:** do **NOT** emit G13-style scoreboard waits / slot assignments — they do not
  exist on G17P, and there is no `AGX_MAX_PENDING` analog (20 independent loads stayed in flight and summed
  correctly; max-in-flight is a HW resource bounded by the register file). The RAW hazard is handled by
  hardware. This makes the backend simpler than G13's.
- **The one remaining silent-corruption surface — the barrier:** cross-lane / threadgroup-memory ordering
  still needs an explicit **barrier**: `threadgroup_barrier` = byte0 `0x07`, 6 B: `07 04 54 <mem_scope>
  <flags> 00`, **byte+3 = fenced memory scope** (`0x61` threadgroup / `0x85` device). `simdgroup_barrier`
  emits no op (lockstep SIMD). Splice-proven: on a 256-thread divergent-writer kernel, corrupting byte+3
  `0x61→0x00` makes **128/256 lanes read stale zeros** (STATUS OK, no fault) — the exact G-1 hazard, and
  the thing a driver author must get right.
- ⏳ This run was compute-only; the fragment/tilebuffer ordering analogue (`wait_pix`/`signal_pix`-style,
  for imageblock/tilebuffer access) is a follow-up.

### ✅ Transcendentals / special functions (EXP-0026, closes G-2)
Two mechanisms; a compiler picks by fast-math vs precise:
- **Special-function unit (SFU)** — the `fspecial` group (byte0 `0x2f`/`0xaf`, 10 B) computes each as a
  **single op**. Function = (byte0 bit7, byte+1): `0xaf`+`00/01/02` = **rcp / rsqrt / exp2**;
  `0x2f`+`00/01/02` = **round / sqrt / log2**. Accuracy: rcp/rsqrt 0 ULP, sqrt/exp2/log2 ~1 ULP.
- **Estimate + Newton-Raphson (precise mode)** — `fspecial_est` (byte0 `0x29`, 6 B: `29 81 25 <fn> 00 c2`;
  byte+2=`0x25` discriminator; **byte+3 = function**: `0x09` rcp / `0x0b` rsqrt / `0x0d` sqrt). The
  estimate is a classic **~8-bit seed** (measured rcp ~8.0, rsqrt ~7.9, sqrt ~7.5 good mantissa bits);
  the compiler refines with **2 NR iterations** (fma/fmul) → 0 ULP. `precise::sqrt` forces this path.
- **Composites:** `exp = exp2(x·k)`, `log = log2(x)·k`, **`pow(a,b) = exp2(b·log2(a))`**, **`a/b = a·rcp(b)`**.
- **sin/cos/tan** = range-reduction (a `0x2b` reduce op + quadrant select) + polynomial (fma chains);
  `tan = sin·rcp(cos)`. Fast and precise are byte-identical. ⚠ **Driver-facing gap:** ~1 ULP for moderate
  args but **~5·10⁵ ULP at large args** (limited built-in range reduction) — a conformant Vulkan/GL
  `sin/cos` must add **software Payne-Hanek range reduction**.
- *(Clean-room: encodings, semantics, precision, and the textbook NR structure are documented; Apple's
  exact scheduled instruction list is not transcribed — rule 5.)*

### ✅ Mesh / object shaders — HW pipeline, compute-style emit (EXP-0030)
Apple9 mesh shading is a **genuine hardware graphics pipeline**, but — unlike matrix (`0xcf`) and RT
(`0xea`) — **the vertex/primitive emit is NOT a dedicated opcode**. It lowers to ordinary stores:
- `set_vertex` / `set_index` / `set_primitive` = runs of **`0xe7` device stores** into a HW-managed
  mesh-output ("UVB") buffer (proven by opcode-diff vs a hand-written compute control that stores the
  same primitives — identical store family; the mesh `_agc.main` shrinks 306→98 B when it emits nothing).
- `set_primitive_count` = a predicated `lane==0` store of the count. Object payload = ordinary stores.
- Mesh has **no truly mesh-unique opcode** (corrected by EXP-0035): the `0x43` marker seen here is actually
  the **generic call/frame-setup marker** — mesh shows it only because mesh stages call helper subroutines
  (`_agc.object.write_childcount`, `_agc.mesh.write_uvb`). object→mesh **grid amplification** is real
  fixed-function dispatch computed in object `main`.
- Stages extract as `__TEXT,__object` / `__TEXT,__mesh` sections (like vertex/fragment).
- **Implication for Mesa:** compile object/mesh as compute-like store kernels + a child-count write; no
  magic emit op exists. Classify **native (pipeline) + emulated-style (emit via stores)**. Submission is
  in `../cmdstream/` (reuses the graphics path). HW-validated end-to-end (correct triangle rendered).
- *(ISA descriptors for `0x43` + stage-map additions are in `experiments/EXP-0030-mesh/new_descriptors.json`,
  pending merge into `tools/agx-isa/db.json`.)*

### ✅ Fragment-shader ISA (EXP-0029, closes G-4 + backlog #2/#5/#7)
- **Varying interpolation — `iter`** (byte0 `0x2f`/`0xaf`, byte+2=`0x54`, 10 B; `2f BB 54 DD 03 SS MM 02 NN 00`),
  one op per component. **byte+5 = varying-slot / per-triangle coefficient index (`slot<<1`)** (splice-proven:
  `0x00→0x02` switched output from `color.x` to `color.y`). **byte+6 = mode:** `0x00` center/linear,
  `0x02` centroid/sample, `0x04` perspective-denominator.
  - **`[[flat]]`** = a different, shorter op **`iter_flat`** (byte0 `0x1f`, 6 B) — provoking-vertex load, no interp.
  - **Perspective-correct is a multi-instruction lowering** (not a mode bit): linear `iter`s + a W-denominator
    `iter` + `0xaf` reciprocal + per-component `fmul`.
  - **centroid/sample** add an 8-B `iter_at` setup (byte+6=`0x0a`; byte+7 `0x01` centroid / `0x03` sample).
    Pull-model `interpolate_at_*` == the matching `[[*_perspective]]` qualifier.
- **Fragment output — `frag_color_store`** (byte0 `0xe7`, byte+1=`0x06`, 12 B): **byte+3 = source colour reg,
  byte+5 = render-target index (`rt<<1`)** (splice-proven). MRT = one store per target. `discard_fragment()`
  HW-proven (killed fragments write nothing). `[[depth]]` out = `0xd7 14 54` (6 B). Dual-source = extra output
  reg, no distinct op.
- **Tilebuffer read — `tile_read`** (byte0 `0x67`, byte+1=`0x0e`, 12 B): a `[[color(n)]]` *input* reads the
  tilebuffer (the `ld_tile` analogue). HW-proven: `out = src*0.5 + clear*0.5` — confirms in-shader
  programmable blend (EXP-0019).
- **Pixel ordering (raster-order-groups) — `pixel_order`** (byte0 `0x07` fence family, same as the compute
  `threadgroup_barrier`): `07 14 54 50 06 00` (acquire) + `07 04 54 d0 06 00` (release). ⏳ byte-diff inferred.

### ✅ Special-register enum + shader ABI (EXP-0031, closes G-5)
**`get_sr` SR number = byte1** (splice-proven: splicing byte1 makes the output become that SR's value):

| SR | code (byte1) | SR | code |
|---|---|---|---|
| thread_position_in_grid .x/.y/.z | `0xa0/a1/a2` | threadgroup_position_in_grid | `0x9c/9d/9e` |
| thread_position_in_threadgroup | `0xa4/a5/a6` | threads_per_threadgroup | `0x98/99/9a` |
| thread_index_in_threadgroup | `0xa7` | threadgroups_per_grid | `0xa8/a9/aa` |
| simd_lane_id | `0x82` | simd_group_id | `0x85` |
| vertex_id | `0xdd` | instance_id | `0xd8` |
| base_vertex / base_instance | `0x88` / `0x8a` (inferred) | `[[position]]`.xy (FS) | `0xa0/0xa1` |
| front_facing (FS) | `0xc5` | | |

- **Folded/computed (not `get_sr`):** `threads_per_simdgroup` → `mov_imm 0x20` (=32); simdgroups_per_tg,
  quad indices are ALU-computed; FS `barycentric_coord`/`point_coord` are **interpolated** (`0x2f` family);
  `primitive_id` = flat tiler-output load; `sample_id` folds to 0 on a 1-sample target.
- **Preloaded-register ABI:** **no stage preloads IDs into GPRs** — IDs are read via `get_sr` on demand.
  Only **buffer/vertex base pointers + scalar uniforms** are preloaded into the **uniform register file**
  (selected by `device_load` byte+4 `base_slot`; the **vertex-buffer base = slot `0x03`**).
- **Vertex attribute fetch is IN-SHADER SOFTWARE (no fixed-function fetch).** Metal lowers the
  `MTLVertexDescriptor` into the VS prologue: **per attribute** a `device_load` (`0x67`) from the vertex
  base (uniform slot 3) at **`index×stride + offset`** + a format-convert ALU; `index` = `get_sr` `vertex_id`
  (`0xdd`) or `instance_id` (`0xd8`) per step-rate. **stride/offset/format live in the compiled shader**
  (shader-specialized); the attribute table `0x10000100000` (EXP-0014) supplies only the base pointer. ⟶ A
  Mesa driver must **generate attribute-fetch code from the vertex format** (like Asahi does).
- **FS input/epilog:** varyings via the `0x2f/0xaf` interpolation datapath reading plane-equation
  coefficients loaded by `0x97` from tiler output; color return via the shared epilog (see `frag_color_store`).

### ✅ Integer / bitfield completeness (EXP-0033, closes backlog #12)
- **Bit-count / scan** — single-op family (byte0 `0x27`/`0xa7`, byte+2 `0x56`, 8 B; op-select = byte0 bit7 +
  byte+1): `popcount` = `27 05 56`, `reverse_bits` = `a7 04 56`, **find-MSB / bit-scan-reverse** = `a7 05 56`
  (a primitive Metal doesn't name; `0x80000000`→31). `clz`/`ctz` are **multi-instruction lowerings** (find-MSB
  + sub + clamp; `ctz` adds a `0x2b` low-bit-isolate).
- **Bitfield:** unsigned `extract_bits` = single `0xa7` 12 B ibfe; **signed extract = ibfe + sign-ext shift**
  (signedness is a lowering). **`insert_bits` has no dedicated op** (mask `0x0b` + shift `0x2b` + combine `0x9f`).
- **Rotate:** by **immediate** = a single 12 B `0x27` funnel op (byte+1=`0x01`); by **register** = multi-instr.
- **min3/max3/median3:** MSL exposes them but there is **no dedicated silicon** — lowered to 2-input int
  min/max (`0x02` group). `clamp` = max-then-min.
- **Pack/unpack + 16-bit:** `as_type` bitcast is **free**. Native fp16 = the **`0x10`** group (`0x1c` hadd /
  `0x1d` hmul); **`half2` packs both lanes into one `0x10` op**, but **`int16` does NOT pack** (two 32-bit
  `0x9f` adds). `pack_unorm2x16` = single `0x97`, unpack = single `0x17` (byte+2-gated vs frag-pack/ballot).
- **64-bit integer:** register pairs, but **native single-op 64-bit add/sub exists** (splice-proven: `u64_sub`
  is one `0x1f`; `0x1f→0x9f` gives a 64-bit add with **hardware carry-out**). Compiler may also emit an explicit
  carry chain (`0x32` carry-generate). 32×32→64 mul = one 12 B `0x9f`; 64×64 = 3 mul(-add)s; register shift/
  compare = multi-instr.
- *(EXP-0033 also corrected DB length-rule bugs for the `0xa7 b1∈{04,05}` 8B, `0x27 b1=01` 12B rotate, and the
  `0x10` half group — staged in `experiments/EXP-0033-int-bitfield/new_descriptors.json` for the consolidation.)*

### ✅ Texture variants (EXP-0034, closes backlog #14)
The 14-byte sample bundle generalizes to every variant via **op+2** (variant/dim/LOD/compare/offset),
**op+6** (mode), **companion+3** (result descriptor), and register operands from preceding ALU:
- **sample_compare (shadow/PCF):** **op+2 bit5 (`0x20`) = depth-compare** (`sample_compare(level)`=`0x29`),
  scalar result (companion+3=`0xa0`); the **compare-reference is a register operand**; the sampler
  descriptor's `compareFunction` (EXP-0015 sense bit39 + test[40:42]) evaluates `ref CMP sampledDepth`. All 8
  compare funcs HW-validated; **linear filter yields fractional PCF** ⇒ **native 2×2 hardware PCF**.
- **gather:** op+6 `0x00` + result-desc in companion+3 (`0xa4/ac/b4/bc`: bit2=gather, bits[3:5]=component
  R/G/B/A, HW-validated). **gather_compare** = gather + op+2 `0x20`. **Constant offset packs into op+5**
  (`(1,0)→0x08`, `(1,1)→0x88`, HW-validated).
- **sample_lod/bias/grad:** op+2 `0x09`/`0x07`/`0x04`; value in a preceding-ALU register; **op+7 bit2** =
  explicit-LOD/bias present.
- **LOD query** (`calculate_*_lod`) = a real texture op (op+6 `0x20`; clamped/unclamped in companion+3).
- **✅ Texture/image atomics are NATIVE** (supported, not rejected): `atomic_*` on `texture2d<uint,rw>` /
  `texture_buffer` lower to the **memory-family device atomic (`0x67`)** with the texel address computed
  in-shader (texture2d: byte+1 `0x11`, op-byte `|0x40`). HW-proven (256 contended adds → 256).
- **array/cube/3D/MSAA:** `read` dim in op+2 (`0x17` 2D / `0x79` 3D / `0x97` 2D-array bit7 / `0x80` MSAA);
  `sample` encodes cube `0x13` / 3D `0x39` / cube-array `0x53` in op+2; extra index (slice/face/z/sample/ref)
  = an added coord register selected via op+3 (⏳ byte-diff, not splice-validated).

### ✅ Function calls / pointers / dynamic libraries ABI (EXP-0035, closes backlog #13)
CALL/RETURN are in the **control-flow family** (byte0 low-nibble `0xf`), not a dedicated opcode group.
- **CALL** = `0f 05 54 1a 8f 00 56 <off40> 00` (14 B): `off40` = signed LE PC-relative, **target = call_addr
  + 4 + off40** (verified at 4 distances). Reuses the exec-mask push (`0f 05`) machinery (a masked branch
  saving the return context; disambiguated by byte+4=`0x8f`+byte+6=`0x56`). Each call preceded by a
  `43 00 00 01` **call/frame marker** and followed by a `0f 06 …` reconverge.
- **RETURN** = `8f <lm> 54 00` (4 B; `0x8f` = CF-family + link bit): **no encoded target ⇒ return address is
  a hardware link register / CF stack**. `lm` = `0x02` leaf / `0x12` non-leaf.
- **Calling convention:** args in **r10, r11, r12…**, return value in **r10**. Leaf callee = no frame;
  **non-leaf** = `6f…` prologue bracketing each nested call with `07…` link save/restore to **per-thread
  scratch** (the EXP-0020 spill stack). Recursion is lowered to a loop (tail) ⇒ statically bounded depth.
- **Function pointers (`visible_function_table`):** a **flat array of 8-byte little-endian code VAs**
  (`entry[i]` = function i's entry-point GPU VA), bound as a **Tier-2 argument-buffer slot** (same model as
  RT `intersection_function_table`, EXP-0023). Resolve: uniform index → in the constant/uniform program;
  per-lane index → device-load `entry[sel]` → **indirect call `0f 80`**. HW-validated (`sel=0→A+B, 1→A*B`).
- **Dynamic libraries (`MTLDynamicLibrary`):** serialize to a Mach-O **filetype 14 (MH_DYLIB)** with AGX code
  in `__TEXT,__text`; consumer references `<name>.MTL_VISIBLE_FN_REF`, **resolved at pipeline-build** (code
  linked in adjacent, then an ordinary direct call). The "dynamic" part is **loader resolution** — a
  kernel-interface concern (see `../kernel-interface.md`).

### ✅ Wrap-up decode: pack / carry / frame (EXP-0038, closes census compute gaps)
- **Half pack `0x18`** (4 B, `18 05 18 03`): assembles the two fp16 lanes from the native-half `0x10` ALU into a
  packed 32-bit register before store. **byte0 high nibble = dst register** ⇒ same op appears as `0x08/18/28/38`
  (dst r0–r3), which is why the census saw `0x30/0x38` in high-register vertex/frag code. HW-validated (float2→fp16
  round-trip). byte+2 = source reg.
- **u64 carry-generate `0x32`** (6 B, `32 01 35 03 22 81`; in the integer-compare family, byte+2=`0x35`, byte+4=`0x22`):
  the `ulong a+b` chain is `9f` lo-add → **`0x32` carry-gen** → `0x05` psel (carry→0/1) → `9f` hi-add → `9f` +carry.
  HW-validated + splice-proven load-bearing (neutralizing `0x32` drops the carry). Siblings `0x12`/`0x22`.
- **Non-leaf function frame** (EXP-0035 completed): `0x6f` prologue (6 B, `6f 03 04 00 00 20`, in the helper region,
  absent in leaf); each nested call bracketed by an 8-byte `0x07` **link save/restore** (`07 00 54 …`, gated by
  byte+1=`0x00`); return `8f 12 54 00` (leaf `8f 02`). HW-validated (3-level deep).
- **`0x54↔0x56` cache bit** = byte+2 **bit 1 (instr bit 17)** = a **source cache / last-use hint** (NOT an op change):
  a standalone `simd_reduce` emits `0x56`; the same op as a second consumer of a shared source emits `0x54`. The DB
  gated on `0x56` only (the census gap); fix relaxes the gate to bit-17-don't-care for `0xbf/0x3f/0xb7` reduce +
  `0x17` unpack (keeping the `0x37` derivative-vs-quad-reduce split). *(descriptors staged in
  `experiments/EXP-0038-pack-carry-frame/new_descriptors.json` for merge.)*

## Confirmed: this is a wholly different ISA from G13/G14
The public dougallj/applegpu (G13) decoder produces `<disassembly failed>` or nonsense on G17P
bytes. applegpu is therefore a **structural template + ISA-agnostic testbed**, not a decoder to
extend. The A18 instruction database is built from scratch (Phase 1).

Source: `experiments/EXP-0001-shader-byte-extraction/`.
