# A18 Pro (G17P) AGX Shader ISA

Clean-room documentation of the Apple G17P shader instruction set. All facts here come from
disassembling **shaders we compiled ourselves** (OWN-SHADER) + public references (PUBLIC) —
never from Apple binaries. See `../../CLAUDE.md`.

> **Status: mature — census complete.** 85 machine-readable instruction descriptors (round-trip-validated asm↔disasm); the
> broad-corpus byte0 census tokenizes **100.0%** of instruction bytes — **0 undecoded regions, 0 undecoded byte0 groups**
> (EXP-M4-12 closed the last 2.6%: all length-rule gaps / 2-byte over-reads, no unknown opcodes; round-trip whole-program
> walk leaves 0 leftover bytes). ~79% of tokens are descriptor-named; the remainder are family-labeled "length-only" tokens
> whose operand sub-fields are deliberately left undecoded where doing so would transcribe a compiler sequence (clean-room
> rule 5). Authoritative encoding tables: [`encoding-tables.md`](encoding-tables.md) · Mesa-schema render: [`agx3.xml`](agx3.xml) (drop into `src/asahi/isa/`).
>
> **RT-1a-FIX (HW-re-validated red-team corrections applied):** memory-op **index register = byte+5** (not byte+1/+6; byte+6 inert; byte+1 = address space) + an in-instruction **immediate index-offset** at byte+9 bit7/+10/+11; **iadd2 polarity** corrected (byte0 `0x9f`=ADD, `0x1f`=SUBTRACT); a proper **float uniform-register source** (`falu2_uni`, disambiguated from the minifloat immediate by byte+1's exponent range); and descriptors/lengths for the four-byte byte0 `0x60` form + the byte+2=`0x18` compact float-accumulate. The A18 splice validates the 0x60 form's length/live byte, not a universal spill role: EXP-0041 found `60 00 00 00` absent from all nine retained M4 own mains including 208–576 B scratch. See `experiments/RT-1a-FIX/` and `experiments/EXP-0041-scratch-helper-abi/`.
> ✅ = hardware-validated (run modified code, observe output); ⏳ = byte-diff-inferred, not yet HW-round-tripped.

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

### ✅ Instruction-length rule (validated)
> **Census reality (RT-1a/RT-1b → RT-ISA-FIX):** the DB tokenizes ~**87–91%** of instruction bytes on a broad corpus
> (EXP-0036 subcorpus **90.6%**); it is NOT "0 leftover" on every realistic kernel. **RT-ISA-FIX closed the biggest
> named gaps:** the **`0x0f` execution-mask family** is now fully decoded (`jump`/`jump_cond`/`if_push`/`pop_reconverge`/
> `call_indirect`/`mask_op` — 42/42 `0x0f` ops tokenize on an if/else/while/for/break/continue/nested corpus), the
> **`0x07` fence** byte+2∈{`0x00`,`0x02`} variant (`scoreboard_fence`, 4B) is decoded, and `0x32` carry-gen was already
> merged. RT-ISA-FIX also fixed two **mis-/non-decodes** of real compiled subgroup ops: `simd_ballot(pred)` (`17 17 54`,
> byte+1=`0x17`, was mis-decoded as `unpack_convert`) and `simd_shuffle` (`47/c7 04 54`, byte+2=`0x54`, was undecodable).
> Remaining residue is operand-level (the `0x2b`/`0x3b`/`0x5b` register/shift-prep family). These are naming/length gaps,
> not correctness errors in the decoded ops.
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
  00 80 0X 00`); HW-validated `a+|b|`. There is also a `0x10` native-half 2-source group.
- **✅ saturate / output-clamp is a NATIVE modifier bit (EXP-M4-10 ISA-2, HW-splice).** `saturate(x)`
  and `clamp(x,0,1)` compile to the **8-byte** extended form with a single output-clamp bit at
  **byte+7 bit1 (0x02)**: fadd `09 05 1c 01 00 c0` → `09 05 1c 01 01 00 00 82` (fp16 mirror
  `10 03 1c 02 01 00 00 82`). Splicing that bit 0x82→0x80 turns clamped 1.0 back into 1.5 — no
  min/max op is emitted, so it is **native, not lowered**. General `clamp(x,lo,hi)` (lo,hi≠0,1) IS
  lowered to explicit fmax/fmin. The **extended-form length = `6 + 2*(byte+4 & 3)`** (0→6 compact,
  1→8 saturate, 2→10 abs) and the SAME rule extends `fma` (0x81→8 / 0x82→10 saturate / 0x83→12 abs).
- **✅ per-operand abs/neg map (EXP-M4-10 ISA-3).** falu2 (6B): srcB-slot negate = **byte+5 bit3**
  (splice-proven: 5+3=8 → byte+5 0xc0→0xc8 → −2); abs → 10B form, abs-enable **byte+8** (bit0 slotB /
  bit1 slotA). fma (8B): multiplicand negate = **byte+7 bit3**, addend negate = **byte+4 bit4**,
  addend abs = **byte+4 bit3**, src-abs → 12B (byte+4=0x83).

### ✅ Machine model — registers, uniforms, Dynamic Caching (EXP-0020, supersedes EXP-0006 "64")
- **96 addressable 32-bit GPRs per thread** (r0–r95, **96 DISTINCT registers — a hard silicon boundary**).
  The compiler's register footprint grows then caps at exactly 96; a kernel with 93 (and even 96) live regs +
  zero scratch runs correctly. (EXP-0006's "64" was a tiny-shader artifact of the nibble-compacted `falu2` dst
  field.) **r96–r127 behave as out-of-file (RT-7, HW):** used as a **memory-index register** (`device_load`
  byte+5) they **hard-FAULT** (`CMDBUF_ERROR`) with a clean r95/r96 boundary; used as an **ALU source** they
  **read 0** (no fault). **Neither aliases live data** — r96+ never returns another live register's value, and
  r64 ≠ r0 (r0..r95 are 96 distinct entries, no mod-64 aliasing). The r96 memory-index fault is positive
  evidence that 96 is a *hard* boundary, not a compiler policy cap.
- **16-bit halves are independently addressable, packed 2 per GPR** (64 `half` values → 50 GPRs).
  Native-half access is via the `0x10`/`0x11` groups; the `0x09` 32-bit form's size bit reaches only the
  low half.
- **Register-field widths:** the 6-byte `falu2` dst is a 4-bit nibble (r0–r15 compaction); high float dst
  uses the 8-byte `falu3` form (`dst=byte+1`, 7-bit; r64 observed). Integer `dst=b3` and all source
  fields are 7-bit `(reg<<1)|size` (span r0–r127, covering the 96-reg file).
- **Uniform register file:** a source operand selects **GPR vs uniform**. For the **float `0x09`** ALU there
  are **TWO valid uniform-source encodings, one per operand position** — the compiler picks by which operand
  is the uniform (they are commutation variants of `a + p.k`). *Both are HW-validated; neither supersedes the
  other* (RT-7 corrects the earlier "byte+2-bit4 was wrong/superseded" claim — that framing was itself wrong):
  - **uniform as srcB** (`falu2` srcB form, e.g. `09 01 0c 0d 00 c2`): the select is **byte+2 bit4 + byte+5 bit1**
    (toggling *either* → the GPR is read instead, i.e. 0; bit39 is irrelevant here). Uniform index = byte+3.
    This is what the compiler emits for the exact `struct P{float k}; a[gid]+p.k` kernel (no-fast-math).
  - **uniform as srcA** (`falu2_uni`, e.g. `09 0d 14 01 80 c0`): the select is **bit39 = byte+4 bit7**
    (toggling → GPR read = 0; byte+2 bit4 / byte+5 bit1 are irrelevant here). Uniform index = byte+1 as
    `(ureg<<1)|size`. Emitted when the uniform is srcA (operand order `p.k+a`, or fast-math commuting `a+p.k`).
    When bit39 is set, byte+1's **exponent nibble** disambiguates this uniform source from a packed minifloat
    immediate (`falu2i`): **exp ≥ 8** (instr bit15 = 1) = minifloat immediate, **exp < 8** = uniform source.
  Both HW-read the *runtime* uniform (bind value 7→7, 55→55, 1000→1000). For the **int `0x9f`** ALU the uniform
  form is still byte-diff-inferred (uniform-srcB byte+5 bit4, uniform-srcA byte+6). `uniform_mov` (4 B,
  `Xb YY 01 08`) copies uniform→GPR. ≤128 uniform regs (7-bit index); exact count ⏳ (only *referenced*
  uniforms occupy uniform registers — on-demand / Dynamic-Caching allocation, so sweeping the index surfaces
  only the one bound uniform).
- **Footprint declaration:** the exact GPR/scratch/uniform/threadgroup footprint is in the shader
  binary's own `__GPU_METADATA` FlatBuffer (field 0 = GPR count, 14/41 = scratch bytes, 31 = uniform,
  9 = threadgroup) — this is *our own* compiled shader's metadata (OWN-SHADER). The launch-descriptor
  `+0x00` config word carries only a coarse **2-level occupancy tier** (bit 23). The tier bit is real
  (clear at low footprint, set at high), but the exact **"2-tier by PEAK register pressure (EXP-M4-09/CMD-8: f0=8 appears on both sides, lowest SET at f0=5) — the earlier "clear ≤11 / set ≥12 GPRs" threshold is
  INTERPOLATED, not measured** (RT-7): EXP-0020's config correlation only captured **f0=8 (clear)** and
  **f0=14 (set)** — the 11-vs-12 transition is an interpolation between those two points, never a directly
  observed 11→12 flip. Treat the precise threshold as unverified.
- **Dynamic Caching / spill:** above 96 GPRs the compiler spills to **per-thread scratch (stack)** memory
  (scratch size in `__GPU_METADATA`); spilled kernels (80–256 regs) compute correctly. A compiler must
  know: 96 GPRs before spill (a hard boundary — r96+ faults, above), 2 halves/GPR, scratch cost, and the
  occupancy tier bit (exact GPR threshold interpolated). ⏳ the scratch-base location is a follow-up.

### ✅ Packed float immediate = 8-bit minifloat (HARDWARE-VALIDATED, EXP-0006)
When srcB imm mode (bit 39) is set, srcB byte encodes an **8-bit minifloat** (NOT IEEE-754):
`[exp:4 (bits 7:4, bias 11)][mant:3 (bits 3:1)][flag:1 (bit 0 = 1)]`, sign at instruction bit 19.
- normal (exp ≥ 9): `value = (1 + mant/8) · 2^(exp−11)`
- subnormal (exp = 8): `value = (mant/8) · 2^−2`
- representable magnitudes: `{0, 1/32 … 30.0}`; out-of-range / non-dyadic constants fall back to a
  register-load form. Worked examples: `1.0→0xb1`, `2.0→0xc1`, `1.5→0xb9`, `3.5→0xcd`,
  `0.0625→0x85`, `30.0→0xff` (max). All 16 tested constants spliced and produced exact `a+K`.
- **Domain (RT-1a-FIX):** the minifloat is only valid for **exponent field e ≥ 8**. The `e < 8` byte range
  is NOT an immediate — it is the **uniform-register source overload** (`falu2_uni`, above). `imm_decode()`
  is now **guarded** to `e ≥ 8` (it raises rather than silently extrapolating a bogus tiny value into the
  uniform range — the old unguarded code returned `a + imm_decode(0x0d) ≈ a + 0.00085` for what is really a
  uniform read).

### ✅ Integer ALU family (EXP-0007)
Integer ops are **spread across several byte0 groups** (each its own format), mirroring the float
split — there is **no single unified integer op-select**. For `iadd`/`isub`, **byte0 bit7 is the
ADD/SUBTRACT selector** (RT-1a-FIX HW-re-validated, corrects the earlier inverted `srcA_neg`): the
compiler emits **`0x9f` for a plain ADD** and **`0x1f` for a SUBTRACT**, and splicing a real add's
byte0 `0x9f`→`0x1f` turns `10+20` into `10−20 = −10` on hardware. (The DB previously matched the
canonical iadd on `0x1f` with `srcA_neg=0` / semantics `d=srcA+srcB`, although `0x1f` subtracts —
now fixed: the descriptor field is `addsub` with enum `1`=iadd/`0`=isub.)

| byte0 | len | operation(s) | op-select | status |
|---|---|---|---|---|
| `0x9f`/`0x1f` | 10 | iadd / isub | `b0 bit7` = **add(1,`0x9f`) / sub(0,`0x1f`)** | ✅ HW (RT-1a-FIX) |
| `0x9f`/`0x1f` | 12 | imul / imad | 3-source multiply-add (imul = imad, c=0) | ✅ HW (behaviour) |
| `0x?2` (lo-nibble 2) | 6/8/10/14 | imin/imax/umin/umax, compare→select, carry, coord/madd | **byte0 hi-nibble = dst reg**; length keyed on byte+2 op-select (see below) | ✅ HW |
| `0x0b` | 10 | iand/ior/ixor | `b2[0:4]` + `b4/b5` src-invert | ⏳ toggle/byte-diff |
| `0xa7` | 10/12 | shift-right / bitfield-extract | multi-instr for reg shifts | ⏳ byte-diff |
| `0x27` | 8/10/12 | popcount / unary / convert / shift-prep / matrix-load-prep | byte+1 form (`0x02`=12B matrix prep) | ⏳ byte-diff |

- **Integer length rule:** for `0x9f`/`0x1f`/`0xa7`, the 10-vs-12-byte selector is **byte +1 bit 0**
  (contrast the float group's byte +2 bit 1). Tokenizes all 26 integer shaders with 0 leftover.
- **Operand encoding (differs from float):** **dst = `b3`** as `(reg<<1)|size` (float dst was
  `b0[4:8]`) — the wider field leaves room for **>16 registers**; srcA/srcB packed in the `b7:b8:b9`
  tail (`(reg<<1)` convention, exact widths a follow-up).
- **Integer immediate = `(K<<1)`**, a **multi-byte little-endian** field starting at `b5` (K=1→0x02,
  127→0xfe, 128→0x0100 spanning b5/b6). **CORRECTION (EXP-M4-10 ISA-4):** it stays **INLINE at least
  to 65536** (K∈{256,512,1024,65536} all keep the same instruction length) — the earlier "≥256
  materializes to a register" was wrong. Negative immediates switch the op byte0 (`0x9f`→`0x1f`
  subtract)/sign path, not a register materialization. **Not** the float minifloat encoding.
- Note: a load/store opcode-keying bug was fixed here (`0x67`/`0xe7` exact, was low-nibble `0x7`
  which collided with `0xa7`/`0x27`).

- **✅ The `0x?2` (low-nibble-2) INTEGER COMPARE / MIN-MAX / SELECT / CARRY group is ONE family
  whose byte0 HIGH nibble is the DESTINATION register (r0..r15)** — exactly like the low-nibble-9
  float ALU (EXP-M4-01, M4/A18 census). **HW-VALIDATED:** on `o=max(a,b)` (a single `02 01 1e 05 06 c0`
  iminmax writing r0, then stored), splicing byte0 `0x02→0x12` (dst r1) or `0x02→0x42` (dst r4) makes
  the result land in a different register while the store still reads r0 ⇒ output flips `10,20,…,80`→
  all-zeros, and the dispatch runs `STATUS OK` (so `0x12`/`0x42` are *valid* encodings, not faults).
  The DB previously hard-coded only dst r0..r3 (`0x02`/`0x12`/`0x22`/`0x32`) and left every
  higher-register form (`0x42,0x52,0x62,0x72,0x82,0x92,0xa2,0xb2,0xc2,0xd2,…`) UNDECODED — the single
  largest source of census resync cascades. The op and length are selected by the **byte+2 op-select**
  (every op-select is `≤ 0x3f`; a larger byte+2 is an operand tail, so it is never mis-lengthed):

  | byte+2 op-select | len | operation | evidence (anchored gap) |
  |---|---|---|---|
  | `0x1e,0x2e,0x3e, 0x26,0x36` | 6 | iminmax (min/max/median/clamp) | i_max, mm3 |
  | `0x35` | 6 | `carry_gen` (u64 add carry-out) | l_add |
  | `0x3d` | 6 | fcmp→predicate (feeds a psel) | k_int_arith `42 0d 3d` (EXP-M4-01 r2) |
  | `0x23` | 6 | SFU polynomial fma (exp/log/pow Horner step, feeds a sel) | k_transcend `42 81 23` (EXP-M4-01 r2) |
  | `0x1d,0x2d` | 14 | icmpsel (compare → 0/1 const-select) | i_cmp |
  | `0x27`/`0x2f`, byte+3`==0x80`, **byte+4 bit1 (0x02) set** | 10 | coordinate / integer-madd `dst=a*b+c`, WIDE srcC (+ trailing 16-bit operand word) | s_div, k_int64@230 |
  | `0x27`/`0x2f`, byte+3`==0x80`, **byte+4 bit1 clear** | 8 | same madd, narrow srcC | k_cf_switch@78, k_int_bitcount@72/@98 (EXP-M4-01 r2) |
  | `0x27`, byte+3`==0x81`&byte+4`==0x22` | 10 | `rt_transform_test` | (EXP-O2C) |
  | `0x27`, else | 8 | quotient / wide-select (incl. dst `0x22`) | u_div, k_cf_if |
  | lo-nibble `7`/`f` or `0x25`, byte+3 a reg-descriptor (hi-nibble 0/8, lo≠4) | 10 | register-operand cmpsel / select | i_selreg, l_cmp |
  | byte+1`==0xc2`, tail `.. 80 08` | 8 | transcendental range-reduction select | t_sin |
  | byte+2 **> 0x3f** (not a valid op-select) | — | NOT this op: greedy `→6` was gated off (EXP-M4-01 r2) so a compact op / resync landing is not mis-lengthed and does not eat the following op | k_transcend, k_tex_array_cube |

  (A predicate-producing compare that feeds a *separate* `0x05` psel keeps the 6-byte form — its
  byte+3 low-nibble is `4`, e.g. gsel4/dsel5 `02 03 07 84`.) All lengths are fixed by **anchored
  segmentation**: the gap between two high-confidence anchors (get_sr / load / store / cvt / iadd /
  imad / stop) equals the sum of the enclosed op lengths.

- **Compact 4-byte float ALU (byte0 low-nibble 9, byte+2 arith-enable bit `0x04` clear):** the
  division/sqrt refinement emits a 4-byte accumulate/move form; byte+2 ∈ `{0x18,0x38,0x19,0x21,0x31}`
  (extends the EXP-0025 `0x18/0x38` set). Confirmed by anchored `cvt..cvt` gaps (s_div@136 `79 8d 21 97`,
  t_sqrt@28 `09 05 19 01`).

- **Other length-rule fixes closing census gaps (EXP-M4-01):** `0x27` byte+1`==0x02` is a **12-byte
  matrix-load-prep** form (k_matrix; the old rule dropped it to 8B and exposed the tail as a spurious
  `0xf0` group); byte0 `0x2c`/byte+1`==0x0c` is a **4-byte compact move** (s_div); the low-nibble-3
  group with byte+2`==0x27` is a distinct **10-byte** op (`33 8a 27 bf …`, transcend/tex); byte0
  low-nibble-0/8 with byte+2`==0x24` is the **6-byte packed-half2 ALU** (k_half2_pack, distinct from the
  `0x10` scalar native-half ALU and the `0x18` half_pack). Net effect on the M4 own-shader census:
  distinct UNDECODED byte0 groups **28 → 19**, byte coverage **91.5% → 93.4%**, with **no per-kernel
  regression**; the residue is concentrated in `k_tex_atomic` (interleaved variable-length `0x0f`
  control-flow mask ops — a documented follow-up — plus texture-atomic ops) and the remaining
  transcendental range-reduction helpers.

- **✅ EXP-M4-01 (round 2) — the census residue was GENUINE instruction gaps, not `0x0f` CF.**
  Round 1 left the `0x0f` execution-mask family flagged as an unresolved variable-length follow-up.
  **That was stale:** `instr_length` already lengths every `0x0f` sub-op (`00`/`01` jump 10B, `04`
  mask_op 4B, `05` if_push 4B / direct-CALL 14B, `06` pop_reconverge 6B, `80` computed-branch 6B),
  and the whole-corpus walk decodes all 67 `0x0f` occurrences in-sequence. The real residue was a set
  of genuinely-missing ops and length-polymorphism bugs, now closed:
  - **`icmp_pred` is a dst-register family (byte0 LOW nibble `0xa`, HIGH nibble = predicate reg).**
    HW-VALIDATED by splice (`k_iso_icmp2`, a loop with `break`/`continue`): splicing a loop-guard
    compare byte0 `0x2a→0x0a` moved its predicate p2→p0 (out `4,25,110,110`→`133,25,133,133`) and
    `0x2a→0x4a` moved it p2→p4 (`→4,389,9989`), both `STATUS OK` — i.e. the high nibble selects the
    destination predicate register, exactly like the `0x?2` sibling. The old `b0==0x0a` rule left every
    `0x1a/0x2a/0x3a/0x9a/0xca` UNDECODED (the dominant `k_tex_atomic`/`k_uint_arith`/`k_int64` desync).
    6 bytes; byte+2 is the compare op-select (`0x22/23/25/2b/35/39/3a`, all `≤ 0x3f`).
  - **madd length is keyed on byte+4 bit1, for byte+2 `0x27` AND `0x2f`** (see table above): the
    srcC descriptor's bit1 (`0x02`) selects a wide srcC carrying a trailing 16-bit operand word (10B)
    vs narrow (8B). Separates every corpus occurrence cleanly and now applies to dst `0x22` too (the
    old `0x22` baseline forced 10 and ate the following op, exposing a spurious `0x54` group).
  - **`0xa7` byte+1`==0x17` is an 8-byte convert** (sibling of the `0x07` int→float; k_cvt_fi/k_cvt_half),
    not the 10-byte `ashr`; the old odd→10 rule ate the following `a7 07` cvt.
  - **Extended-source vertex fma (byte0 lo-nibble 9, byte+2 `0x26`/`0x2e`, byte+4`==0x82`, byte+6/+7
    `42 02`) is 10 bytes** with a trailing `00 <slot>` varying/output-slot word (every VS: r_basic_v/
    r_deriv_v/r_tex_v). Fixing it took **render:vertex to 100%** on the A18 corpus.
  - **Fragment derivative (`37 xx 54`, 10B) vs COMPUTE texture-gradient (`37 xx 80`, 8B)** disambiguated
    on byte+2; the 8B compute form is followed by a 12-byte `27 00 54 .. f0 13 01 00` ibfe in the
    software texture-coordinate atomic path.
  - **COMPUTE scoreboard-fence high-scope variants** `87 02 00 00` / `80 02 00 00` (4B, byte0 = `0x07`
    fence with the high bit set; gate the full form on byte+2`==0x00` so a bare `80 02`/`87 02` before a
    CF op is not mis-lengthed). Plus the compact ops `18 00`, `2b 35`/`0b 35` (texture coord/LOD
    selector before `37 xx 80`), `00 8c`, `80 04` (2B compact moves), and the `0x?b` shift/rotate
    compact `?b .. {1c,3c} <amt>` (4B).
  - **Greedy `02`/`0a` gate:** `b0==0x02`/lo-nibble-`0xa` now return 6 **only when byte+2 ≤ 0x3f** (a
    real op-select); a byte+2 > 0x3f means it is a compact op / resync landing, so the op no longer
    greedily eats the following `fspecial`/`coord_madf` (k_transcend, k_tex_array_cube).

  **Net (M4 own-shader census):** distinct UNDECODED byte0 groups **19 → 12**, byte coverage
  **93.4% → 96.4%**, cleanly-tokenized tokens **91.4% → 95.2%**, resync regions **101 → 57**, still
  **0 per-kernel regression** (all 23 previously-100% kernels stay 100%, 9 more reach 100%). A18
  cross-check (same ISA): **93.2% → 96.0%**, groups **20 → 13**, regions **112 → 70**. `roundtrip_test`
  stays **GREEN**. The remaining ≈57 regions are a *characterized* long tail — dense-code compact
  2-byte helper ops (`00 8c`-class), the `0x54` texture-address/imageblock op family (variable
  4/6/8/10-byte, byte+2`==0x03`), threadgroup-memory atomic ops (`k_atomics_tg`: `0b 00 06`, `54 .. 44`),
  cube-array coordinate math (`k_tex_array_cube`), and low-frequency SFU polynomial helpers
  (`k_transcend`) — each a named op needing per-op HW isolation, **not** a resync-cascade artifact.

### ✅ Control flow, predication & program structure (EXP-0010)
- **Preamble = get-special-register** (`get_sr`, byte0 low-nibble `0xC`, 4B): materializes special
  registers into a GPR. **(Corrected by EXP-0031: the SR number is in `byte1`; the byte0 high nibble is
  the destination GPR — not the SR-select.)** See the SR-enum + ABI section below. There is also a 2-byte
  **`mov_imm`** (byte0 low-nibble `0xC`, byte1 = imm8) sharing the nibble.
- **Simple divergence is predication, not branches.** `if/else`/ternary/early-return compile to
  **compare → per-lane execution mask → masked op / select** (no jump). Compare producers: `0x0a`
  (6B, control predicate) and `0x02` (6B, feeds a select); compare immediate at **byte+3**. Selects:
  `0x05`/`0x16` (4B). Proven: splicing the compare immediate moves the active-lane boundary; flipping
  flipping `0x0a`↔`0x02` swaps predicate-vs-select producer (RT-1b: a *naive* byte0 swap MALFORMS output — the two have different operand layouts; true condition inversion is via the **byte+4 compare-mode/negate** field).
- **Loops use a real backward jump:** `0f 00 54 <off6> 00` (10B), `off6` = **signed little-endian
  byte-relative offset**, target = `jump_addr + 4 + off6`. Zeroing the back-edge → contained infinite-loop
  hang (proves it's the taken edge). Fixed-count loops are fully **unrolled**.
- **✅ The `0x0f` execution-mask family is now fully decoded (RT-ISA-FIX, HW-validated).** `0x0f` is the
  control-flow / execution-mask group; **byte+1 selects the sub-op** — each now has a length rule + descriptor
  in `agx-isa`, so if/else/while/for/break/continue/nested-divergence shaders **tokenize cleanly** (0 of 42
  `0x0f` ops undecoded across a for/while/nested/break/continue corpus):
  | byte+1 | mnemonic | len | role |
  |---|---|---|---|
  | `0x00` | `jump` | 10 | unconditional PC-relative jump (loop back-edge / block skip) |
  | `0x01` | `jump_cond` | 10 | **conditional** PC-relative jump — the `else`-skip / `while`/`for` loop-exit guard |
  | `0x05` | `if_push` | 4 | execution-mask **push** (enter divergent region); byte+2 0x54 outer / 0x04 inner |
  | `0x06` | `pop_reconverge` | 6 | mask **pop** / **reconverge** (block/loop end); byte+3 = level |
  | `0x80` | `call_indirect` | 6 | computed-target branch (indirect call / break-to-exit) |
  | `0x04` | `mask_op` | 4 | inner mask op in deep nesting (continue-edge re-mask; ⏳ inferred, 1 occurrence) |

  Same shape, the `0x8f` sibling (byte0 = `0x80|0x0f`) is a 4-byte **CF merge/reconverge** marker
  (`8f 04/05 54 ..`) at if/else and loop joins — the same op as a function `ret` (`8f 02/12 54`) with a
  different byte+1. HW splice evidence: corrupting the `0f 00` back-edge offset → `CMDBUF_ERROR`; corrupting a
  `0f 06` reconverge (byte+1 `0x06→0x00`) → `CMDBUF_ERROR`; turning the `0f 01` guard unconditional
  (byte+1 `0x01→0x00`) makes **every lane skip the loop body → all-zero output** (proving 0f 00 = uncond,
  0f 01 = cond). See `experiments/RT-ISA-FIX/`.
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
| +1 | **space** | address-space selector: nonzero low bits (`0x01`/`0x02`) = threadgroup / uninitialized (reads 0), `0x00` = device/global/constant. **NOT the index register** (RT-1a corrected the old "higher bits = index GPR") | ✅ |
| +3 | extmode | bit1 = unsigned/zero-extend variant | ⏳ |
| +4 | **base_slot** | preloaded buffer-base uniform slot (0=buf0, 1=buf1, …) | ✅ |
| +5 | **index_reg** | **the GPR that supplies the array index `a[idx]`** — low bits = register number, bit7 (`0x80`) = a scalar/size flag. (RT-1a: this is NOT `count`; sweeping it selects which GPR feeds the index: `0x00`→r0, `0x01`→r1, …). **EXP-M4-10 (ISA-1):** splicing +5=`0xff` (r127) **hard-FAULTS** (`CMDBUF_ERROR`) — proof the high bits are real register-select bits, **not** masked mod-64. | ✅ |
| +6 | **inert** | HW-proven padding — sweeping `0x00`..`0xff` never changes the loaded value; not an address byte | ✅ |
| +8 | dst / (load-only) reg + width | **LOAD:** destination GPR + data width (`51`=32b `(reg<<1)|is32`, `41`=16b, `61`=8b, `59`=64b), splice-confirmed (EXP-M4-10 ISA-1: changing it breaks the consumer). **STORE — CORRECTION (EXP-M4-10 ISA-1):** +8 is **HW-INERT** for `device_store` (two scalar stores of distinct regs both had +8=`0x11`; splicing +8 does nothing). The stored **data GPR is byte+2/+3-region** (amode 0x54: +3 low bits = data reg), **not** +8 and **not** symmetric with the load dst; exact position is amode-dependent (byte-diff, not fully pinned). | ✅ load / ⚠️ store reg |
| +9 bit7 / +10 / +11 | **idx_off** | in-instruction additive **immediate element index-offset**: +9 bit7 = +1, +10 = +2/unit, +11 low bits = +512/unit (RT-1a) | ✅ |
| +12 | **elem_size** | address element size, bits[1:4]=k → `2^(k-1)` bytes (`42`=1,`44`=2,`46`=4,`48`=8) | ✅ |

- **Addressing model: element addressing with an optional immediate offset.** Effective byte address =
  `(index_GPR + idx_off) × element_size`, where **index_GPR = byte+5** and **idx_off** is the additive
  immediate element-offset field (byte+9 bit7 / +10 / +11; RT-1a-FIX HW-validated: idxbuf i0=40 →
  byte+9=`0x81`→a[41], byte+10=`0x01`→a[42]/`0x08`→a[56], byte+11=`0x41`→a[552]). The **compiler leaves
  idx_off = 0** and instead computes `a[i+k]` / `a[i*s]` by a **prior integer ALU op** on the index (so
  `a[gid+1/+2/+4]`, `a[gid*2/*4]` all share a byte-identical load, the offset living in the preceding
  `iadd` immediate — EXP-0012), **but the hardware offset field exists** and a driver may use it directly.
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
- **What byte address a load/store actually touches once misaligned or out-of-allocation** (per-unit
  align-down addressing, OOB zero-fill/discard, boundary-straddling behavior; M4/G16G, EXP-0076) is
  documented separately in [`memory-model.md`](memory-model.md) — a normative chapter, not covered here.

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
- **fmin/fmax** (`0x12`, 6B): byte+4 bit0 = min/max. A18 EXP-0013 and
  M4 EXP-0047 compiler-emitted source paths both return the numeric operand for
  tested one-qNaN cases. A18 tested `fmax` and M4 tested both `fmin`/`fmax`
  selecting operand B for signed-zero ties; M4 additionally shows operand-B
  selection for the tested effectively-equal subnormal and both-qNaN cases.
  The prior universal “IEEE minNum/maxNum” shorthand was too strong. The M4
  edge matrix is source-path evidence, not an
  isolated native-op semantic proof.
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
  - **texture-slot = op+4** — the **argument-buffer texture index** (Tier-2 path). ⚠ **CAVEAT (RT-5):**
    under **direct** `setTexture:atIndex:` binding, op+4's low bits are **inert** — only **bit7 (`0x80`)** is
    load-bearing, and it is a 2-way flip (reaches only a 2nd texture; a 3rd bound texture differs in
    companion+3 / op+1, not op+4). op+4 acts as a clean index only through the driver's **Tier-2
    argument-buffer** texture table (see `../cmdstream/`, `../descriptors/`); the direct-binding fast path
    folds it to the bit7 flip. Single-resource shaders always encode slot 0.
  - **sampler-slot = op+5** — HW-validated clean index (splice samp1→samp0 flipped linear→nearest; `0x00`=s0,
    `0x01`=s1, out-of-range → unbound/zeros).
  - **coord = op+1** (+ preceding ALU); result reg = sampler-op byte0 hi + companion byte+3.
  - **op+6 is NOT the filter selector (RT-5):** splicing op+6 `0x10↔0x00↔0x20` on a linear sample is a
    **no-op** — **filtering is controlled by the SAMPLER** (proven via op+5), not op+6. op+6 does carry the
    LOD-*mode* (`0x20` = `calculate_lod` query); explicit-LOD/bias *presence* is op+7 bit2, with the
    LOD/bias/grad *value* coming from a register set up by a preceding ALU op.
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
- **`simd_reduce`** (byte0 `0xbf`/`0x3f`, 8 B, byte+2=`0x54`/`0x56`): reduce & prefix-scan. Op = (byte0 bit7,
  byte+1); **byte+7 = datatype/shape: `0x03` int-reduce, `0x07` int-minmax, `0x12` float-reduce, `0x09`
  inclusive-scan, `0x0b` exclusive-scan** (byte+2 bit1 is a source cache/last-use hint, 0x54 vs 0x56, not an
  op change). **Prefix-scan is native.** *(RT-ISA-FIX re-proved these on a fresh compile: `simd_sum(int)`=496
  emits byte+7=`0x03`, inclusive-scan `0x09`, exclusive-scan `0x0b` — exactly as decoded here. RT-5's claim
  that "int-reduce=`0x01`/exclusive-scan=`0x09`" did **not** reproduce; splicing byte+7 `0x03→0x01/0x07` left
  the sum=496 unchanged, so the DB enum is correct and unchanged.)*
- **`simd_shuffle`** (byte0 `0x47`/`0xc7`, 10 B, byte+2=`0x54`/`0x56`): broadcast / shuffle(xor/up/down) /
  rotate / dynamic shuffle. byte+1 = simd/quad/rotate; byte+6 = lane/mask as `(value<<1)`. *(RT-ISA-FIX:
  real compiled broadcast/xor carry byte+2=`0x54`; the DB match was relaxed to accept both — `simd_broadcast(v,3)`=35
  and `simd_shuffle_xor(v,3)` HW-re-validated.)*
- **`simd_ballot`** (byte0 `0x17`, 10 B): ballot / active-mask / all / any / is_first. **byte+1 low nibble
  `0x7` identifies the family**; high nibble picks the form — `0x07` = active-mask/any/all, **`0x17` =
  `simd_ballot(predicate)`**. *(RT-ISA-FIX: `simd_ballot(lane<5)`=0x1F HW; the `0x17` form was previously
  mis-decoded as `unpack_convert` — now separated from `unpack_convert` on byte+1 low nibble, ballot=7 vs
  unpack=4. RT-10 confirmed: splicing byte+1 low-nibble `0x17→0x14` zeroes the ballot, proving the low nibble
  is the load-bearing family separator. The **high nibble** (ballot-predicate vs active-mask) is a correct
  naming distinction but is **not cleanly splice-convertible** — its operands co-vary — so treat it as a decode
  label, not an independently-settable field.)*
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
- **`matrix_mac` (`0xcf`, 12 B):** `d = a·b (+c)`, row-major 8×8. RT-5/RT-10 splice-proved the full operand map on
  the **fp32 datapath**: **byte+5 = A, byte+6 = B, byte+7 = C, byte+8 = dst, byte+11 bit0 = accumulate-enable**
  (swap +5/+6 → B·A; +5→B → B·B; byte+11 `01→00` drops `+c`; op-enable byte+10=`0x24`). ⚠ **The `0x24`/`0x01`
  op-enable/accum byte *values* are fp32-specific:** the **half datapath** (byte+1=`0x00`) encodes them as
  byte+10=`0x8c` / byte+11=`0x00` — the half-datapath accumulate byte is **uncharacterized** (RT-10). Inferred:
  byte+1 = dtype (`0x00` half / `0x02` float-bf16), byte+2 = mode (`0x56` standalone / `0x54` tiled).
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
  intersection primitive. **The OP itself is HW-validated dedicated & load-bearing** (RT-5: corrupting
  byte+1 `0xea→0x00` on the traverse op → GPU hang; on the result-read op → distance 3→2.984). Emitted twice
  (traverse, then result-read). ⏳ **Its operand SUB-FIELDS are INFERRED (byte-diff), NOT HW-validated** —
  RT-5 found every documented sub-field was **splice-INERT** on the single-primitive `intersection_query`
  path (identical correct hit for all splices): byte0 hi = result reg (`0xe4→0x04/0x14` no change); byte+2
  mode (`0x90` const-origin / `0x10` dynamic-origin / `0xd0` + function-table — `0x90→0x10/0xd0` no change);
  byte+3/+4 = ray/AS operand regs. **byte+4 is a real AS-type byte-diff correlate — `0x8b` = primitive AS,
  `0x6b` = instance AS** (RT-10 built BOTH AS types and corrects the retracted `0x1b` to the actual **`0x6b`**),
  **but splicing byte+4 is INERT** (`0x8b↔0x6b↔0x1b↔0x00` all give the identical correct hit; only `0xff` faults),
  so it is a passenger/correlate, not the load-bearing selector. The genuine primitive-vs-instance distinction is
  **structural**: the instance kernel emits an extra `rt_intersect` at +0x690 (byte+2=`0x10` dynamic-origin) + ~2×
  the `0xdf` ray-transform loads, and **cross-binding a kernel to the wrong AS type → a clean MISS** (RT-10). byte+2
  mode (`0x90` const-origin / `0x10` dynamic-origin / `0xd0` + function-table) and byte0-hi result reg are likewise
  inert to splice; byte+6 bit7 = intersection-function-table bound. The earlier "EXP-O2C: `0x8b→0x1b` HW-validated
  end-to-end" note is **retracted** (RT-5/RT-10) — `rt_intersect` field *values* are ⏳ byte-diff correlations, and
  the AS-type dispatch is structural (kernel shape), not a spliceable field.
- **`rt_as_load`** (byte0 `0xdf`, 14 B): dedicated acceleration-structure / ray-data node loads
  (14–37 per RT kernel). The traversal is a shader loop (a `−88`-byte back-edge whose body holds a `0xdf`
  node-load + `0x0a` loop-condition compare).
- **Acceleration structure** is referenced by an **8-byte GPU VA in the Tier-2 argument buffer**. ⚠ The
  **BVH *build* is GPU/firmware-managed** — userspace supplies vertices + a build descriptor; the GPU
  writes the BVH; the **BVH node format is NOT userspace-visible** (kernel-interface item, like the
  ZLS / depth-store control). *(Note: sample positions are **not** a kernel item — RT-4 showed they are
  userspace-emittable to a client BO @+0x40; see `kernel-interface.md` §4.2.)*
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
  now **merged** into `tools/agx-isa/db.json` (DB 82, round-trip green).)*

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
- **⚠ `threadgroups_per_grid` (`0xa8/a9/aa`) is NOT a direct SR value (RT-7):** a bare `get_sr 0xa8`
  spliced alone returns **threads_per_threadgroup** (it tracks `tg` exactly), not the grid's threadgroup
  count. The `threadgroups_per_grid` *builtin* is `get_sr 0xa8` **+ a `device_load` + a divide** (visible as
  `24 a8 10 06 … 67 10 44` in the compiler output); the builtin computes correctly (grid/tg → 256/64=4,
  192/64=3). So `0xa8` is the code the compiler uses for this builtin, but a driver emitting a bare
  `get_sr 0xa8` and expecting the threadgroup count would get threads_per_threadgroup instead. (Every other
  code in the table above IS the direct SR value, splice-proven; only `0xa8` carries this build-and-divide
  nuance — no code is mislabeled.)
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
  `0x10` half group — defined in `experiments/EXP-0033-int-bitfield/new_descriptors.json`, now merged into db.json.)*

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
- **⚠️ `0x54↔0x56` cache bit — STATUS DOWNGRADED TO `UNKNOWN` (EXP-0086, 2026-08-28). DO NOT
  TREAT AS INERT.** The former claim below ("a source cache / last-use hint, NOT an op change")
  rested solely on RT-1a-FIX, which spliced an instruction and re-checked *that same instruction's
  own result* — a test structurally incapable of detecting a register-liveness effect, whose
  failure mode is a **later** instruction's read. EXP-0086 ran the missing later-read test and
  found that **a bit in the same conceptual role, in the same float-ALU family, silently corrupts a
  later separate instruction's read when flipped on the earlier (producer) instruction** —
  deterministically, with no fault: the later read returned the source as **zero**. Polarity:
  natural encoding is earlier-reader bit 0 / later-reader bit 1; forcing the *earlier* reader's bit
  to 1 corrupts. The earlier instruction's bit alone decides the outcome. The **literal** bit 17
  could not be tested directly — in every family it could be compiled into, splicing proved bit 17
  is part of the **opcode** (`opsel`), not a free bit — so `0x54`/`0x56`/`0x18`/`0x38` are
  `UNKNOWN` pending their own later-read test, **not** confirmed inert. **Implementer guidance:
  emit these bits exactly as the pattern you copied them from; do not synthesize or "normalize"
  them, and do not assume a wrong value is harmless.** Historical claim, retained for the record:
  a standalone `simd_reduce` emits `0x56`; the same op as a second consumer of a shared source emits `0x54`. The DB
  gated on `0x56` only (the census gap); fix relaxes the gate to bit-17-don't-care for `0xbf/0x3f/0xb7` reduce +
  `0x17` unpack (keeping the `0x37` derivative-vs-quad-reduce split). *(descriptors staged in
  `experiments/EXP-0038-pack-carry-frame/new_descriptors.json` for merge.)*

### ✅ Wrap-up decode: vertex varying-store + texcoord math (EXP-0037, closes census graphics gaps)
- **Vertex varying-store `0x57`** (8 B, memory family, sibling of `0x67/0xe7/0xd7`): the VS writes `[[position]]` +
  varyings to the UVS/parameter buffer that the FS `iter` op interpolates. **byte+3 = source GPR**, **byte+4 =
  output slot (`index<<5`)** — HW-validated (redirecting a store slot moved that varying to a different FS channel).
  **Position vs varying = the slot range** (position = slots 0–3, user varyings 4+), not a distinct opcode.
- **Not stores:** `0x05` = `psel` (computes per-vertex varying *values*, already in DB); `0x06` = the `0f06`
  reconverge sub-op / resync noise next to mesh `0xe7` emit. Mesh emits via `0xe7`, not `0x57`.
- **`0xb0`/`0x90` = the 10-byte sampler op** (second half of the EXP-0016 14-byte texture bundle) — a **tokenizer
  gating fix, not a missing instruction**: the `tex_sample` companion gate required `byte+1==0x80` exactly and missed
  chained-companion forms; fix widens to `(byte+1 & 0xf0)==0x80`.
- **`0x2e`/`0x26`/`0x92` = float fused-multiply coordinate math** (also the vertex `mvp*pos` product) — a **length-rule
  fix, not a missing instruction**: op-select `0x26/0x2e` are 6/8-byte (by byte+4 bit1); the naive float length rule
  mis-lengthed them. *(fixes + `vary_store` descriptor from `experiments/EXP-0037-varying-texmath/new_descriptors.json`, now merged.)*

### ✅ RT tail + tensor completion (EXP-O2C, objective-2 O2-C/O2-F)
- **RT-from-render (HW-validated):** a fragment shader tracing rays lowers **identically to compute RT** (2×`rt_intersect`
  + `0xdf` loads + `0x5f` + the −88B traversal loop); only the bind stage differs (`setFragmentAccelerationStructure:`).
  No fragment-specific RT opcode.
- **Motion blur (end-to-end HW-validated; sub-fields ⏳ inferred):** no new opcode — a motion-AS ray with time
  produces `rt_intersect` byte+2=`0x10` (dynamic/time form) and byte+4=`0xbb`, with the time value threaded via
  byte+3 and ~5 extra `0xdf` loads for time-interpolated vertices; interpolated hit distances validated
  (z=3→5 over 5 times). ⚠ **The `0xbb`/`0x8b`/`0x1b` byte+4 AS-select and byte+2 mode are byte-diff
  correlations, NOT splice-validated** — RT-5 showed splicing them on a single-primitive path is inert (see
  the `rt_intersect` sub-field caveat above); the motion path itself is validated by the interpolated
  distances, but the *specific byte that selects it* is inferred.
- **`0x5f` = RT ray-data memory op** (14 B, byte+2=`0x54`, sibling of `0xdf`) — the `ray_data` payload path (distinct
  address space in RT scratch; count scales with payload size). Also `rt_transform_test` (`0x?2`, byte+2=`0x27`, traversal
  slab-test ALU) and `ray_move` (`0x?b`, byte+2=`0x80/81`, 4 B ray-register marshalling). Primitive tag (bbox/curve/opacity)
  does **not** change the intersect op — discrimination is in the AS + `intersection_function_table`.
- **Tensor ops all lower to `0xcf`** (no new tensor opcode); transpose/load/store are memory + 4 B moves — the MAC is the
  only dedicated silicon. **Full `0xcf` operand decode (HW-validated via splice):** byte+5 = A(left) reg, byte+6 = B(right)
  reg, byte+7 = C accumulator, byte+8 = dst, byte+3 = A sub-descriptor, byte+10 = op-enable `0x24`, byte+11 bit0 =
  accumulate-enable, byte+1 = dtype, **byte+2 = mode (SEMANTIC, not a hint** — tiled mode `0x54` sources its accumulator
  from the MPP tile context; resolves EXP-0022's open question). *(descriptors from `experiments/EXP-O2C-rt-tensor-tail/new_descriptors.json`, now merged.)*

### ✅ Compute/fragment ISA tail (EXP-O2D, objective-2 O2-D/O2-E)
- **Atomic ordering = fence *presence*, not a field on the RMW op.** MSL accepts only `memory_order_relaxed` on
  `atomic_*_explicit`; the `0x67` RMW carries no ordering field. `atomic_thread_fence` = the **`0x07` fence family**:
  device fence `07 04 54 84 0a 00` (byte+3=`0x84` device, byte+4=`0x0a`); texture fence pair `07 04 54 50/d0 06 00`
  (byte+4=`0x06`, byte+3 bit7 = acquire/release). Relaxed / thread / simdgroup / threadgroup scope → no fence emitted.
  **API-behavior qualification (EXP-0051, M4, commit `adfa33b3`):** correctly fenced and deliberately relaxed,
  `mem_none`, or wrong-memory-class authored cases all passed the bounded Metal litmus, so those weak-control
  passes do not prove a portable ordering guarantee or identify native fence necessity. Consumer-first
  unsynchronized queues exposed stale data, while explicit event/CPU ordering passed. This adds no native-byte,
  Linux UAPI, cache-domain, or A18 semantics; see
  `../../experiments/EXP-0051-m4-synchronization-litmus/analysis/{summary.json,report.txt}`.
- **⚠ 64-bit atomics are ENTIRELY absent from MSL** (all `atomic<ulong/long/uint64_t>` ops rejected) — **corrects
  EXP-0018's "min/max only".** No reachable 64-bit atomic ⇒ no width field; **Vulkan int64 atomics must be emulated.**
- **bfloat ALU = distinct group byte0 `0x11`** (opsel byte+2 `0x1c/1d/1e` add/mul/fma; scalar byte+1=`0x02`, bfloat2
  `0x04`; add/mul 8 B, fma 10 B) — NOT fp32-lowered, NOT the `0x10` fp16 group. Splice `0x1c→0x1d` flipped bf 1+2→1×2.
  Includes a **length-rule fix** (DB mis-lengths `0x11` as 6 B).
- **Subgroup tail:** float `simd_product` = `0xbf` byte+1=`0x06`, byte0 bit7=1 (HW-validated, product↔sum); integer
  product/prefix-product have **no native op** (lowered to `0x47` shuffle + `0x9f` mul tree). `simd_shuffle_and_fill_up/
  down` = `0x47/0xc7` byte+1=`0x06`; **`simd_is_helper_thread` = `get_sr` SR byte1=`0x84`**.
- **Imageblock:** write = `0xe7` store, read = `0x67` load (fragment/tile variant byte+1 ∈ {`0x06`,`0x16`,`0x0e`});
  **slice addressing byte+5 = (field byte-offset within imageblock) >> 1** (differs from MRT's `rt<<1`); byte+7 = format.
  HW-validated end-to-end (tile kernel overwrote an RGBA16F attachment).
- **Tile shaders submit mid-render** (no separate submission): draw vs draw+`dispatchThreadsPerTile` = byte-identical
  IOKit (58 calls / 37 BOs); the tile-dispatch record is appended inline to the render control stream (`0x58000`/`0x18000`).
  *(descriptors from `experiments/EXP-O2D-compute-frag-tail/new_descriptors.json`, now merged.)*

## Confirmed: this is a wholly different ISA from G13/G14
The public dougallj/applegpu (G13) decoder produces `<disassembly failed>` or nonsense on G17P
bytes. applegpu is therefore a **structural template + ISA-agnostic testbed**, not a decoder to
extend. The A18 instruction database is built from scratch (Phase 1).

Source: `experiments/EXP-0001-shader-byte-extraction/`.
