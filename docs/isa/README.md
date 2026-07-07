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

### ✅ Register model (preliminary, EXP-0006)
Sweeping the source register field, index `0x89` aliases `0x09` (bit 7 folds mod 64) ⇒
**64 physical 32-bit GPRs (r0–r63)**, with the size bit selecting 16/32-bit (low half) —
**not** independent 16-bit-half addressing, and **no uniform-register file** was exposed in the
2-source form. This differs from the public **G13** model (r0–r127 as 16-bit halves + u0–u255
uniforms). ⏳ To confirm: full dst-register width, whether a uniform/constant file select exists
in other forms, and the Dynamic-Caching (Apple9) implications for occupancy/spill.

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
  registers (e.g. `thread_position_in_grid`) into a GPR; byte0 high nibble = SR-select.
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
- The `_agc.main.constant_program` prolog does **not** load base pointers; its `0300070002000000 6000`
  prefix (present only when the kernel does a device load) is a no-op when corrupted — advisory/prefetch,
  role ⏳ TBD.

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
- **Atomics** (noted, deferred): `atomic_fetch_add` uses a **new op byte0 `0xbf`** inside an
  execution-mask **CAS/retry loop** (`0x0a` compare + `0f 05`/`0f 06` mask ops) around a `67 01…`
  access — not the plain load/store path.

## Confirmed: this is a wholly different ISA from G13/G14
The public dougallj/applegpu (G13) decoder produces `<disassembly failed>` or nonsense on G17P
bytes. applegpu is therefore a **structural template + ISA-agnostic testbed**, not a decoder to
extend. The A18 instruction database is built from scratch (Phase 1).

Source: `experiments/EXP-0001-shader-byte-extraction/`.
