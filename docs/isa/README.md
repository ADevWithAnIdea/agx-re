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

## Emittability status — what an implementer can actually *generate* (measured)

> **Read this before using any encoding table in this file.** *Decoding* and *emitting* are
> different claims. `tools/agx-isa/db.json` round-trips the corpus **302/302**, which proves the
> tables can tokenize and re-serialize observed bytes; it does **not** prove that an emitter can
> put an arbitrary legal value in a field and get the documented behaviour. The per-field
> labelling standard that separates the two is [`../evidence-classification.md`](../evidence-classification.md)
> (row `DOC-02`), and the live measured state is the `coverage` block of
> `tools/agx-isa/validation.json` (`generated: 2026-08-28`, `db_sha256 eaca7256…`).

**Measured state — `target: G16G` (Apple M4).** Every field label below was established by an
experiment that ran on the **local M4 / G16G**. It is **not** relabelled G17P and does not
transfer: see "Target status" at the end of this section.

| | |
|---|---|
| Instructions in the database | **171** |
| Instructions **EMITTABLE** | **38** |
| Instructions **decodable, not yet emittable** | **133** |
| Fields total | **1036** |
| Fields at **emitter grade** (`hardware-run` 349 + `isolated-byte-diff` 94) | **443 = 42.8 %** |

Per-label field counts, strongest first, with what each one licenses a compiler back-end to do:

| label | fields | % | what an emitter may do with it | CODEX ladder |
|---|---|---|---|---|
| `hardware-run` | 349 | 33.7 % | Emit **arbitrary values inside the field's recorded `range`**. The field was given values the compiler would never choose — boundaries, holes, out-of-range — spliced into a real program and executed. | `HW-VALIDATED` |
| `isolated-byte-diff` | 94 | 9.1 % | Emit **only at the tested points**. An isolated byte change in code compiled from our own MSL ran with the predicted effect, but the range was not swept. | `HW-VALIDATED` (point) |
| `corpus-correlation` | 182 | 17.6 % | **Do not synthesize.** Meaning inferred from co-variation across our own compiled shaders; nothing was executed. Reproduce the observed value. | `STRUCTURAL` |
| `tokenization-only` | 203 | 19.6 % | **Do not synthesize.** The field exists so length/framing round-trips; its semantics are unknown. | `STRUCTURAL` |
| `single-template-inference` | 13 | 1.3 % | **Do not synthesize.** Read out of exactly one example — could be a constant, a don't-care, or load-bearing. | `INFERRED` |
| `api-accept-reject` | 0 | 0 % | A statement about what Metal/the compiler service accepts, **not** about the hardware field. | `INFERRED` |
| `host-private` | 0 | 0 % | Not a field userspace fills. | *(out of scope)* |
| `untested` | 195 | 18.8 % | A **gap**. It is listed so you can see it, not so you can fill it by guessing. This is the default for any field with no explicit label. | `UNKNOWN` |

**The 38 emittable mnemonics** (every emitter-filled field at `hardware-run` or
`isolated-byte-diff`; `tools/agx-isa/validation.json` → `coverage.emittable_mnemonics`):

`copysign` · `cvt_f2h` · `cvt_f2i` · `cvt_i2f` · `cvt_i2f_src` · `device_load` · `device_store` ·
`falu2` · `frame_prologue` · `get_sr` · `half_alu` · `half_alu_ext8` · `ibitcount` · `if_push` ·
`iunary` · `link_save_restore` · `matrix_mac` · `mov_imm` · `n3_sample_read` · `pack_convert` ·
`pixel_order` · `psel` · `reg_move_c0` · `reg_move_c1` · `reg_move_c2var` · `reg_move_c9` ·
`reg_move_cb` · `sel` · `spill_frame_marker` · `stop` · `tex_addr_setup` ·
`threadgroup_barrier` · `tile_read` · `tile_read_mrt` · `uniform_mov` · `unpack_convert` ·
`vtx_coord_xform` · `vtx_out_pos`

> ⚠️ **Read "emittable" strictly.** It means *every emitter-filled field of that descriptor is
> `hardware-run` or `isolated-byte-diff`*. It does **not** mean the instruction covers every
> semantic role a compiler might want from it. The clearest example is the `reg_move_*` /
> `uniform_mov` cluster: it is emittable for its **immediate** and **uniform-register** source
> classes, while a general **GPR→GPR move from a register a preceding computation wrote** remains
> an open hard negative ([`register-move-and-liveness.md`](register-move-and-liveness.md) §1.0).

**Everything else in this file is "decodable, not yet emittable".** Per `DOC-02`'s verbatim
rule — *"do not use 'emittable' for a family whose arbitrary operands have not executed"* — a
✅ in a section heading below means the *claim in that section* was hardware-validated. It does
**not** mean every field of that instruction can be freely synthesized. Check
`validation.json` per field before emitting.

**Why the distinction bites harder here than on most ISAs.** On Apple9 a wrong operand-field
value overwhelmingly produces a **silent zero, not a fault**. Measured instances from the
2026-08-28 emitter wave, all `target: G16G`:

- `device_load` destination register `R ≥ 64` — silently zeroes, no fault (EXP-0141).
- `tile_read` byte+6 bit 0 clear, or a wrong `rt_index` — silent zero, i.e. a **black tile**
  in a BG/EOT program rather than a failed command buffer (EXP-0147).
- `matrix_mac.dst_desc` outside `bit6=1, bit7=0` — 128 of 256 values silently zero (EXP-0147).
- `get_sr.dp_width` / `.dp_marker`, `psel.mode` / `.flag`, `ret.linkmode` — each accepts only a
  masked subset; outside it the usual outcome is a **silent wrong value** (EXP-0140).
- `falu2.mod_lo` bit 2 — reads `0.0` at the very index where the neighbouring class reads a
  live operand (EXP-0138).

A driver that fills an unvalidated field with a plausible-looking value therefore fails
quietly and far from the cause. That is the reason this whole labelling standard exists.

**Target status (current rule).** All sixteen P0/P1 closure rows are now measured against
**full G17P**, and all live testing has moved to the A18 Pro / G17P (`CODEX.md` "Target
discipline", user directive 2026-08-28). Every field label counted above was, however,
measured on **M4 / G16G**. Those results remain **valid on their own target** and are not
retracted; they are **not** promoted to G17P. G17P revalidation is under way (`EXP-0153`), and
cross-target promotion requires a recorded validation or an explicit `INFERRED` label —
never a silent relabel.

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
> [!IMPORTANT]
> **EXP-0148 correction (2026-08-28) — the length rule was reading the NEXT instruction's opcode.**
> The rule chooses 6/8/10/12 from **`byte+4`**, but for the **compact** forms `byte+4` *is the
> following instruction's leader* — and AGX leaders overwhelmingly end in low nibble `7`/`f`
> (`&3 == 3` → 12) or `1`/`5`/`9`/`d` (`&3 == 1` → 8). A 4-byte op therefore read its successor's
> opcode and swallowed it. **The form must be selected from the leading parcel before the
> `byte+4` extension is consulted.** Four corrections applied:
>
> | id | rule |
> |---|---|
> | **L1** | byte0 low nibble `9`, op-select (`byte+2` bits[2:0]) ∈ {0,1} → **length 4** (the compact float accumulate/move class) |
> | **L2** | byte0 low nibble `9`, `byte+2` ∈ {`0x26`,`0x2e`} → the **uniform** `6 + 2*(byte+4 & 3)`, replacing `8 if (byte+4 & 2) else 6` plus two hand-patches |
> | **L3** | byte0 `0x10` (native fp16) with `byte+2` in the compact set → **length 4** |
> | **L4** | byte0 low nibble `b` → **length 10** when `(byte+2 & 0x06) == 0x06`, excluding `byte+2` ∈ {`0xd7`,`0xe7`} |
>
> **`falu2_ext8b` was deleted — it was never an instruction.** Its match is exactly the
> op-select-{0,1} space L1 now lengths to 4, which is why 193 of its 250 corpus instances embedded
> a real op leader. `tg_atomic_prep` is replaced by a corrected 10-byte `tg_atomic_prep10`; new
> descriptors `half_compact4` and `b_alu10_lo6` were added.
>
> Corpus effect: files tokenizing end-to-end **803 → 832**, strict leftover bytes
> **395,390 → 389,368**, round-trip **302/302 unchanged**. One file regressed, and its alignment
> chains off `op04_len8` — the one over-consumer still **OPEN**, where six candidate rules all
> measured *worse* than the status quo.
>
> This also closes `length_rule_gaps.b_alu10`: the 10-byte XOR example EXP-0099 §6.1 found
> decodable under *no* family now decodes as `b_alu10_lo6`.
>
> **Two cautions for implementers.** The broad form of L3 was tested and **refuted** (it broke 7
> files — byte0 `0x10` is overloaded and is also a legal two-byte operand/pad word), so do not
> widen it. And `_r9_succ_safe` makes some lengths depend on the *following* bytes failing to
> decode, which makes round-trip a **non-local** test: a change here can break a file whose own
> instructions you never touched.

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

### ✅ `falu2` operand SOURCE-CLASS model + an inline float immediate (EXP-0138) — `target: G16G`

`falu2` is the most-used instruction in the ISA and it is now **EMITTABLE**: its last blocking
field, `mod_lo`, is `hardware-run` dense over all 8 values, with an identical per-case outcome
map in three independent runs (98/98 cases each, 294/294 overall). Evidence label
**`HW-VALIDATED`** (splice-and-observe), `target: G16G` (local Apple M4, macOS 26.6.2/25G82).
Source: `experiments/EXP-0138-m4-emit-falu/RESULTS.md` §2–§3.

**`mod_lo` is not a spare modifier — it is an operand-source-class field.**

| bits | selects | values |
|---|---|---|
| **bit 0** | `srcA`'s source class | `0` = GPR at `srcA_reg`. `1` = a second class that **returned `0.0` at every index tested** (`srcA_reg` ∈ {0, 6}). It is **NOT** the uniform file: at `srcA_reg = 6`, where the uniform file holds `101.0`, `mod_lo = 1` still produced `0.0`. |
| **bits[2:1]** | `srcB`'s source class | `0` = GPR at `srcB_reg`; `1` = the **non-GPR operand file** addressed by `srcB_reg` (below); `2` and `3` both read **`0.0`**, and **bit 2 dominates bit 1** — `mod_lo = 6` reads `0.0` at the very index where `mod_lo = 2` reads `101.0`. |

The pre-registered hypothesis (bit 0 = "srcA reads the uniform file"; bit 2 behaves like bit 1)
was **REFUTED in both halves** and replaced by the rule above, which was then scored against
every case. The pre-registered refuter fired as designed: `mod_lo = 2` with `srcB_reg = 2` (an
unbound uniform index) returned `5.0`, not the GPR answer `8.0`.

**In source class 1, `srcB_reg` 64..127 is an inline 8-bit minifloat immediate.** `srcB_reg`
**bit 6 is live in this class**, which is why it was invisible in GPR mode, where EXP-0099 /
EXP-0112 correctly found bit 6 inert (`r(R mod 64)` aliasing).

| `srcB_reg` range | meaning |
|---|---|
| `0..63` | uniform-register file index. The bound `constant float4& = {101,202,303,404}` appeared at indices **6..9**. |
| `64..127` | **inline 8-bit minifloat immediate**, `k = srcB_reg − 64`, `e = k >> 3`, `m = k & 7`: `value = m · 2^-5` when `e == 0`, else `value = (8 + m) · 2^(e−6)`. |

**Ten HW-confirmed points** (`k` → value): `0`→0, `2`→0.0625, `3`→0.09375, `31`→1.875,
`32`→2.0, `48`→8.0, `56`→16.0, `61`→26.0, `62`→28.0, `63`→30.0.

- **Safety consequence:** indices **126/127 do NOT fault in this mode** — they are the
  immediates 28.0 and 30.0 — unlike GPR mode, where EXP-0112 recorded a fault. **The register
  model does not transfer across `mod_lo` classes.**
- *Editorial cross-reference (arithmetic identity of two already-documented formulas, not a new
  measurement):* this value table produces the same magnitude set `{0, 1/32 … 30.0}` as the
  bit-39 packed immediate documented under "Packed float immediate = 8-bit minifloat" below —
  substituting `e = exp − 8`, `m = mant` turns one formula into the other. They are two
  *routes* to the same minifloat table, reached by different encoding fields.
- **Carrier-specific, stated as such:** uniform index `10` read back ≈1.0 in this carrier. That
  is `kernels/carrier_uni.metal`'s own literal, not a hardware fact; the experiment's
  `analysis/model_check.py` marks it `CARRIER_SPECIFIC`.

**Three further float-ALU instructions became emittable in the same wave** (`target: G16G`):

- **`copysign` (4 B): `operands` (byte+3) is INERT** — all 256 values return the same result.
  That is a hardware fact, not a dead path: the pre-registered falsifier arm on byte+1 fired
  hard (240/256 values silently zero, 8 return −5.0, 8 return +5.0). `db.json` models byte+1 and
  byte+2 as fixed match constants; **byte+1 is a live operand field and byte+2 is a 256/256
  don't-care.**
- **`half_alu`: byte+1 is the FIRST SOURCE DESCRIPTOR, not the destination** (`dst`/`opflags`
  both dense `hardware-run`). Descriptor **bit 7 is confirmed inert** (`0x82` ≡ `0x02`,
  `0x84` ≡ `0x04`) — an independent reproduction of EXP-0099's inert-top-bit finding on a
  different family. `opflags` 0..7 behave as the anchor; 8..29 change the result
  (release-source semantics, cf. EXP-0086/0099); 10..31 silently zero.
- **`half_alu_ext8`:** `dst`, `opflags`, `b7_lo`, `b7_mid` all dense `hardware-run`;
  `b7_lo`/`b7_mid` inert across their whole range.

**Negative and safety results (first-class, `target: G16G`):**

- ⛔ **`fspecial`'s OPERANDS ARE SWAPPED in older documentation — read this before emitting one.**
  `db.json` used to say `dst` = byte+1's high nibble, `src` = byte+3, `src_ext` = byte+5. The
  hardware says otherwise, and the failure is silent:

  | byte | what it actually is | rule | evidence (G17P) |
  |---|---|---|---|
  | byte+1 high nibble | **inert** | — | 16/16 both runs |
  | **byte+3** | **destination** register | `reg = v >> 1`, requires `(v & 0xFE) == 0` | 28/28 fit, 0 misfits |
  | **byte+5** | **source** register | `reg = v >> 2`, requires `(v & 0xFC) == 0` | 60/60 fit, 0 misfits |

  Both mask rules are the **unique** separators over an exhaustive search of all 256 candidate
  masks. **An emitter following the old layout puts the destination in a byte that does nothing
  and the source in the byte that redirects the destination — the program runs, faults nothing,
  and silently writes the wrong register.** Established three ways, including **20/20 generated
  `r_i = rsqrt(r_j)` encodings that Apple's compiler never emitted** (the old model scored 10 fail
  + 10 unpredictable on the same bytes). `EXP-0161` (DEF-0161-1), re-derived independently from
  raw and confirmed by `EXP-0165`.

- ⛔ **`fspecial` destination register ≥ 96 faults or hangs the GPU.** `reg = byte+3 >> 1` maps
  values 0..191 onto **r0..r95 — exactly the 96-entry GPR file** — so the safe rule is
  *register < 96*, not the earlier "byte+3 bit 7 clear". Measured: 45 of 64 values in 192..255
  give a genuine `ErrorHang`, 19 were swamped by neighbouring contexts' resets and never cleanly
  observed, and **0 ever worked**. Earlier isolated-host runs saw 192/193/194 each hang three
  times in a row under a 12 s watchdog. The same ≥96 boundary appears independently across seven
  unrelated instructions (`iter.dst`, `iter_at.dst`, `frag_color_pack.dst`,
  `simd_{ballot,reduce,shuffle}.dst`, `imageblock_store.src`), where `(v & 0xC0) == 0xC0` faults
  and the same plus bit 1 **hangs** — so it is a property of the register file, not of `fspecial`.

- ⛔ **`imad` has NO first operand in older documentation.** `db.json` modelled no `srcA` at all;
  the byte it called `srcC_lo` (byte+6) is the **first multiplicand's register selector**,
  `reg = (byte+6) >> 3`, reproduced in both seed sets and solved from scratch with both
  multiplicands free (132 two-dimensional points, 0 unsolved). **An implementer following the old
  descriptor cannot choose the first operand of an integer multiply.** Related: `imad.srcC_desc`
  is not one field — bits 0,1 are a mode (`11` → reproducible fault), bit 2 is inert, and bits
  3..7 select an addend **that is not in the instruction** (the recovered addends are the 16-bit
  halves of the *carrier's own* float constants). `byte+5`'s role is unresolved and was never
  swept — do not assume `(reg << 1) | size` there. `EXP-0160` (DEF-0160-6), confirmed by `EXP-0165`.

- ⛔ **`op04_len8`'s declared 8-byte length is REFUTED on hardware — do not emit this descriptor.**
  A register-witness probe measuring consumed length directly (2,304 measurements, both controls
  passing, one proving it can detect a 6-byte length) shows all six patterns from our own G17P
  compiles consume **twelve** bytes; the `0x04` leader's length is a joint function of `byte+1`
  bit 7 and `byte+2`. The corrected rule was **not** applied to the decoder because it regresses
  the corpus gate, so the conflict is unresolved and the descriptor carries an `EMITTABLE VETO`.
  Emitting 8 bytes would desynchronise every instruction after it. `EXP-0157`.
- **`falu_srcmod12b.srcB_neg` and `.mod_lo` are inert** at the operands tested, although the
  *same-named* fields on `falu2` are live. **Do not assume one operand model across the
  float-ALU families** — the same lesson EXP-0139 recorded for `iadd2.dst`.
- `falu_srcmod12b` and `half_alu_fma12` remain **`emit_unsafe` regardless of their field
  labels** (`falu_srcmod12b` `opsel == 4` corrupts an unrelated, independently seeded register —
  EXP-0119).
- **`falu3`/`falu3_ext` field NAMES in `db.json` are misleading** (confirmed): byte0's high
  nibble is the **destination** (`dst_lo`), byte+1 (`dst`) is the FIRST SOURCE, byte+3 (`srcA`)
  the SECOND, byte+5 (`srcC`) the THIRD, and byte+4 (`srcB`) is a CONTROL byte whose low 2 bits
  are the 0x09-group length selector. An emitter following the names would put the destination
  in a source slot.
- **Scope limit:** 7-bit register fields were swept `0..15` dense plus 17 boundary values,
  **not** `0..127` dense. Wide `ext`/`ext_srcmod` tails are `isolated-byte-diff` only — each
  constituent byte was swept 0..255, the full 16/32/48-bit space is **not** claimed.

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

### ✅ MOV / select / uniform-move families — emitter rules (EXP-0140) — `target: G16G`

Evidence label **`HW-VALIDATED`** (dense splice sweeps, two gated captures), `target: G16G`
(local Apple M4). Source: `experiments/EXP-0140-m4-emit-mov-cf/RESULTS.md`.
**11 of 23 dispatched instructions moved from "decodable" to EMITTABLE** (3 → 14 of 23):
`get_sr`, `mov_imm`, `psel`, `sel`, `uniform_mov`, `reg_move_c0/c1/c2var/c9/cb`, `if_push`.

**`uniform_mov.usrc` (byte+1) is a two-region field — and its upper half is a second way to
materialise a constant.**

| `usrc` | behaviour |
|---|---|
| `≥ 0x80` | **materialises the immediate `usrc & 0x7F`** into the destination GPR — a 7-bit immediate move, *not* a uniform read. **128/128** immediate-region values matched a host-computed oracle exactly. |
| `< 0x80` | selects a uniform register, **pair-quantised**: `usrc` and `usrc ^ 1` read the same 32-bit word, and consecutive uniforms step by 4. **8/8** of the indices holding our four bound magic constants returned them exactly (`0x18/0x19`→u0, `0x1C/0x1D`→u1, `0x20/0x21`→u2, `0x24/0x25`→u3). Buffer base addresses were observed at `usrc` `0x00/0x01` and `0x04/0x05`; **unallocated uniform indices return a silent zero.** |

So an emitter now has **two independent ways to materialise a small constant**: `mov_imm`
(7-bit, r0..r15) and the `0x?B` family with `usrc ≥ 0x80` (7-bit, r0..r15). The latter was
previously documented as a uniform-register read only.

> ⚠️ **"Emittable" here does NOT mean a general GPR→GPR move exists.** Under `DOC-02` a family is
> emittable when every emitter-filled field is `hardware-run` or `isolated-byte-diff` — which this
> family now satisfies for its **immediate** and **uniform-register** source classes. It says
> nothing about moving from a GPR written by a preceding computation, which remains the open hard
> negative documented in [`register-move-and-liveness.md`](register-move-and-liveness.md) §1.0
> (EXP-0090's scope correction: EXP-0087's validated cases were **entirely
> uniform-register-sourced**). Do not read this section as closing `nir_op_mov`.

The rest of that cluster: **`dst`** (byte0 high nibble) — all 16 values write r_D and nothing
else. **byte+2** moves a value exactly when `(v & 0xCB) == 0x01` (8 of 256 values).
**byte+3** moves a value exactly when `(v & 0x0E) == 0x08` (32 of 256 values).

> **`db.json` defect (recorded, not patched here):** `reg_move_c0` / `c1` / `c2var` / `c9` /
> `cb` / `uniform_mov` are **ONE instruction, not six** — a single 256-value sweep of byte+2 in
> one carrier shows the five "descriptors" are five values of one 8-bit form field. `db.json`'s
> split of byte+1 into `src_reg` + `src_flag` also does not match hardware: **bit 7 is the
> immediate-vs-uniform-file selector**, not a register-file half flag.

**⚠️ RETRACTION — `mov_imm`'s "silent zero" was a zero-initialised buffer (EXP-0140 corrects
EXP-0128).** EXP-0128 reported that `mov_imm` immediates 128..255 "silently zero" the
destination. That reading was taken against a **zero-initialised read-back buffer**. Against a
**poisoned** buffer the paired control settles it:

- with `imm_top = 1` the instruction **does not write the destination register at all** — the
  destination keeps its previous value (7, not 0) when 4 bytes of inert padding follow it;
- **unpadded, it consumes the following 2-byte instruction**, so the read-back store addresses
  the wrong word.

**Bit 7 selects a different, longer instruction. It neither extends the immediate nor zeroes.**
EXP-0128's *conclusion* — treat the immediate as **7 bits** — stands; its *mechanism* does not.
`mov_imm.dst` is `hardware-run` 16/16: every value 0..15 wrote only r_D, confirmed by four
independent 12-register aliasing scans.

> **Decoder defect, not a hardware claim:** `mov_imm` with `imm7 == 12` does not tokenize under
> the current length rule (byte+1 = `0x0C` makes the 2-byte pair look like the 4-byte `0x?c`
> preamble group). It is the only immediate in 0..127 with this property, checked exhaustively
> over all 16 `dst` values. Whether the hardware agrees was **not tested**; every immediate
> EXP-0140 emitted avoids 12.

**`get_sr` — the two "opaque" bytes are not don't-cares.** Oracle: grid=8/tg=8, a working
`thread_position_in_grid.x` read makes each lane store its own index.

| field | reads the SR correctly iff | notes |
|---|---|---|
| `form` | 0 or 1 | **both inert** |
| `dp_width` | `(v & 0xD3) == 0x10` | bits 0,1,6,7 clear, bit 4 set; bits 2,3,5 don't-care. **Faults on 32 of 256 values**; silently returns the wrong vector on 216. |
| `dp_marker` | `(v & 0xE6) == 0x06` | bits 1,2 set, bits 5,6,7 clear; bits 0,3,4 don't-care. Wrong vector on the other 24. |

**`sel.body` is three located byte-fields, not one opaque 24-bit `raw`.**

- **byte+3 = the predicate-FALSE operand.** With bit 7 set it is an **8-bit immediate whose
  value is the byte itself** (128..255) — matched a host-computed oracle on **510 of 512** cases
  (the other 2 were environmental faults). With bit 7 clear it selects an operand that read 0 in
  this carrier. Independently confirmed statically against five authored `?:` variants:
  `(a>5)?130:250` compiles to `16 c2 a0 fa` (0xFA = 250) and `(a>5)?100:200` to `16 c2 a0 c8`.
- **byte+2** splits into four 64-value classes: 128 inert, 128 wrong value, 128 silent zero,
  **127 fault**.
- **byte+1** is the predicate/operand source selector: only 4 values (194, 198, 202, 206) are
  inert; 248 silently zero and 256 return a different value.

**`psel`** has the same structure: `sel` (byte+3) **512/512 matched the oracle** with the
identical immediate model; `mode` (byte+2) inert exactly when `(v & 0xC0) == 0x00` (64 values,
127 values **fault**); `flag` (byte+1) inert exactly when `(v & 0x12) == 0x02`.

**Control-flow bytes an emitter may fill freely, measured inert across all 256 values** in a
program whose oracle proves the branch and the mask stack executed: `if_push.scope`,
`if_push_pred.scope`, `jump.link`, `jump.branch_ctrl`, `pop_reconverge.scope`. Load-bearing in
the same family: `if_push.scope_kind` (64 values inert, 178 wrong value, 1 hang);
`pop_reconverge.scope_kind = 0` is the single fatal value; `ret.linkmode` runs **only when
`(v & 7) == 4`** — the other 224 values fault.

**What EXP-0140 does NOT establish (`UNKNOWN`, deliberately):**

- **`jump_cond`'s three fields stay `untested`.** Every structured offset — including targets
  that are not instruction starts and targets *outside the program* — reproduced the baseline,
  and so did all 256 values of `cf_scope` and `reserved`. The carrier is structurally powerless:
  `jump_cond` is the loop-entry guard and the only lane whose guard is true has trip count 0, so
  both paths compute the same value. **EXP-0115's branch reach was measured on `jump` and does
  not transfer to `jump_cond`.**
- `mask_op`, `ret_luse`, `call`, `call_indirect` were **not swept at all**.
- `ret.scoreboard` and `if_push_pred.level` were stopped by the two-hang budget.
- **Methodological caution:** *lengthening a control-flow carrier is not semantically neutral*,
  even when the documented `base_slot` trap is avoided — adding arithmetic on an accumulator
  alone (no new buffer reference) moved the constant the reused skeleton's select compares
  against, so every lane took the TRUE arm, while every `base_slot` value stayed identical.

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

### ✅ Memory-family operand rules an emitter must follow (EXP-0141) — `target: G16G`

Evidence label **`HW-VALIDATED`** (exhaustive splice sweeps, ~71,000 GPU measurements, 4 gated
runs), `target: G16G` (local Apple M4). Source:
`experiments/EXP-0141-m4-emit-mem/RESULTS.md`. This is what took `device_load`, `device_store`
and `threadgroup_barrier` from "decodable" to **emittable** (emitter-grade fields 246 → 288;
emittable instructions 7 → 10 of 171 at that point in the wave). The full normative statement,
with ranges and fallbacks, is [`memory-model.md` §2A](memory-model.md); the register-lifetime
context is [`register-move-and-liveness.md`](register-move-and-liveness.md).

- **Destination register rule (supersedes the EXP-M4-13 formula that EXP-0101 retracted).**
  `dst_lo`/`dst_ext9` carry **no register information**. To land a load in register `R`:
  `extmode = 2·R` (**bit 0 is a don't-care**), `dst_lo = 1` **exactly**, `dst_ext9` **bit 0 = 1**
  — three constrained bits of the nine those fields span. **`extmode` 0..127 all match and
  128..255 all fail**, so `R` is reachable only for **`R = 0..63`; `R ≥ 64` silently zeroes**
  through this field. Identical at r3/r7/r20/r33 and under all 21 working `ld_format` codes.
- **The atomic RMW operand register is ENCODED, not implicit.** `db.json` said "implicit
  (supplied by the preceding op / amode)" and `DOC-02` ranked it MISSING. It is carried in
  **byte+5 bit 7 plus byte+6 bits 0..5**:
  `index = (byte+5 >> 7) | ((byte+6 & 0x3F) << 1)`. Proven at all four constructible indices with
  the redirected register **released** (a later reader gets 0 — the same contract EXP-0086/0089/
  0099 document), on a **uniform-address** carrier that the old per-lane `index_reg` reading
  cannot explain. The **address** role of byte+5/+6 is not excluded for the per-lane form; the
  **data** role is proven for the uniform form.
- **`device_store` byte+2 bit 1 is a DATA-SOURCE SELECTOR.** It is **inert when the data is
  ALU-computed** (256/256 pass — which is exactly the configuration EXP-0119 measured and
  reported as inert) but **required when the source is a forwarded load**.
- **Five `rsv*` bytes in `atomic_mem`/`atomic_tg` are live and heavily constrained, not
  padding** — only a handful of the 256 values work in each. An emitter must not write arbitrary
  values there.

**Not moved, with reasons (`untested`, honestly scoped):** `mem_fence` ×3 and
`dev_scoreboard_fence.scope_flag` — the carriers have **no ordering observable**, so a pass
proves nothing; `mem_fence8` ×2 — no dispatchable carrier; `atomic_tg.op_desc` — hang budget.

> **⚠️ A18↔M4 divergence, reported not resolved.** `tg_addr_compute`'s emittable veto **stands
> on new grounds**: on M4 only byte0 `0x1c` works, and EXP-M4-14's A18 `0xfc` does **not**
> reproduce. This is a fresh G17P↔G16G divergence and must not be papered over by assuming
> family equality.

> **Testbed hazards discovered here, relevant to anyone reproducing this work.** (1) A third
> contamination mode exists: **`STATUS OK` with nothing executed**, whose output is
> zero-initialised — which on this ISA is *also* the expected signature of a wrong field value.
> It corrupted EXP-0141's own baseline during smoke and was mitigated with an integrity sentinel
> written through a path independent of the instruction under test. (2) Reusing one splice-archive
> path across persistent-runner requests produces **~8 % phantom `CMDBUF_ERROR`** (28/360 vs
> 0/360 with unique paths).

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

#### ✅ The matrix unit also computes `A·B − C` — a mode Metal never emits (EXP-0147) — `target: G16G`

Evidence label **`HW-VALIDATED`** (dense full-range sweeps, 2 gated runs, 100 % cross-run
agreement, zero unstable cases), `target: G16G` (local Apple M4). Source:
`experiments/EXP-0147-m4-emit-pipeline-misc/RESULTS.md` §2.1. **`matrix_mac` is now EMITTABLE**
— both remaining blocking fields resolved, so all 12 of its fields are `hardware-run` or
`isolated-byte-diff`.

**`b11hi` (byte+11 bits 1..7, 7 bits, all 128 values, twice) — the two low bits are accumulator
sign controls, not padding.** Correct `a·b + c` requires **`(b11hi & 3) == 0`** (32 of 128
values); bits 2..6 are don't-care. The other three settings are real, resolved per tile row:

| `b11hi & 3` | rows 0–3 | rows 4–7 | operation |
|---|---|---|---|
| `0` | `+C` | `+C` | `A·B + C` (the only mode `simdgroup_multiply_accumulate` emits) |
| `1` (bit 0) | `−C` | `+C` | **half-tile multiply-subtract** |
| `2` (bit 1) | `−C` | `−C` | **`A·B − C`** (full-tile multiply-subtract) |
| `3` (both) | `+C` | `−C` | **half-tile multiply-subtract, opposite half** |

So the matrix unit performs **matrix multiply-subtract and a half-tile variant**, neither of
which Metal's `simdgroup_multiply_accumulate` ever emits. Found by perturbing a field the
database modelled as opaque `raw` — the extrapolate-and-test method — with the negative-space
value map recorded alongside.

**`dst_desc` (byte+9, all 256 values, twice):** correct `A·B + C` **iff bit 6 = 1 and bit 7 = 0**
(64/64); bits 0–5 are don't-care. `0x00–0x3F` and `0x80–0xBF` (128 values) **silently zero**;
`0xC0–0xFF` (64 values) return a wrong value. Verified as a set identity against the raw
records, not by eyeballing ranges.

> Compare the M5/G17g result `H-M5-1` in [`../hypotheses.md`](../hypotheses.md), where a
> *different* bit (byte+13 bit 6) negates the **A·B product** on Apple10. The two are separate
> findings on separate targets; neither transfers to the other.

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
  programmable blend (EXP-0019). **Now EMITTABLE with a per-field legal-value set — and its
  failure mode is a silent zero (a black tile), not a fault: see the `tile_read` section below
  (EXP-0147, `target: G16G`).**
- **Pixel ordering (raster-order-groups) — `pixel_order`** (byte0 `0x07` fence family, same as the compute
  `threadgroup_barrier`): `07 14 54 50 06 00` (acquire) + `07 04 54 d0 06 00` (release).
  ~~⏳ byte-diff inferred.~~ **SUPERSEDED — now HW-VALIDATED with the full accepted value set per
  field, and `pixel_order` is EMITTABLE: see the `pixel_order` section below (EXP-0147,
  `target: G16G`).**

### ⚠️ Barycentric interpolation is BROKEN when the fragment shader reads `[[position]]` (EXP-0137) — `target: G16G`

Evidence label **`HW-VALIDATED`** (own-MSL compile + disassembly + hardware readback, two gated
runs), `target: G16G` (local Apple M4). Source:
`experiments/EXP-0137-m4-bary-split-abi/RESULTS.md`. This is the single most surprising
fragment-stage fact in the P0.8 work and a driver must know it before it lowers
`gl_BaryCoord` / `SPV_KHR_fragment_shader_barycentric`.

**The trigger is the fragment shader reading `[[position]]`.** Not output count, not an extra
varying, not the harness — each of those was controlled for.

| variant class | measured `barycentric_coord` at the sample point |
|---|---|
| non-position (`base`, `count3_const`, `count3_vary`, `attach3ctrl`) | `(0.243489, 0.134766, 0.621745)` — **correct** |
| position-touching (`pos3`, `pos2`, `posread_noout`) | `(0.486979, 0.269532, 0.243489)` — **broken** |

`posread_noout` only **stores** position to a `device` buffer and never emits it, and it is still
broken. The ratio between the two is **exactly 2.0**: the broken values are **unnormalized
perspective numerators**, with the third component derived as `1 − b0 − b1` and the
normalize-by-sum step simply **absent**.

**What the disassembly of our own compiled shaders shows:** the broken form has **2 `iter` ops
and ZERO `fspecial`**. The discriminating control is `count3_vary` — `iter = 6`, `fspecial = 1`,
i.e. a reciprocal **is** present and the result is still correct — so *"an rcp exists"* is not
the condition. The condition is the `[[position]]` read.

**⛔ NEGATIVE, and it removes the obvious workaround: MSL's
`[[barycentric_coord, center_perspective]]` / `[[..., center_no_perspective]]` qualifier
compiles but is a COMPLETE NO-OP.** Both qualified forms produce **identical disassembly** to
the unqualified form (`iter = 2`, `fspecial = 0`) and identical results. **There is no
MSL-level escape hatch.** A driver that needs correct perspective barycentrics in a shader that
also reads `[[position]]` must normalize the numerators itself.

**Convention (needed to match Vulkan/GL semantics):** `barycentric_coord.x/y/z` follow **vertex
emission order** (`vid % 3 = 0, 1, 2`); perspective-correct is the intended semantic.

**Related P0.8 result — there is no native prolog/epilog split contract, and inlining is not
`noinline`-controllable.** Refining EXP-0109: a **memory-touching vertex helper** and a
**2-call-site compute helper** *are* kept out-of-line, as named Mach-O local symbols reached by
a real `call` / `frame_marker` / `pop_reconverge` sequence — but a **single-call-site fragment
epilog inlines despite `noinline`**. An implementer cannot rely on the compiler's out-of-lining
to define a stage ABI boundary.

### ✅ `tile_read` / `tile_read_mrt` are EMITTABLE — and their failure mode is a black tile (EXP-0147) — `target: G16G`

Evidence label **`HW-VALIDATED`** (all 256 values per byte, twice; liveness proven by a
clear-colour control and a litmus-power probe that collapses the read to zero), `target: G16G`.
Source: `experiments/EXP-0147-m4-emit-pipeline-misc/RESULTS.md` §2.2. All 7 `tile_read` fields
and all 6 `tile_read_mrt` fields promoted. This advances **P0.4**: a BG/EOT program's tilebuffer
read is now a specified encoding with a stated legal-value set per field, not a copied template.

| field | rule, measured over all 256 values, twice |
|---|---|
| `b2` | **fully inert** — all 256 values give the byte-exact correct pixel |
| `b4` | **fully inert** — all 256 correct |
| **`b6`** | **bit 0 is a READ-ENABLE.** All 128 **odd** values are correct; all 128 **even** values return a **SILENT ZERO**. Bits 1–7 don't-care. Identical on `tile_read_mrt`. |
| `rt_index` | correct only at `0x00, 0x01, 0x80, 0x81` (baseline `0x00`) — bit 0 and bit 7 don't-care; **every other index silently returns zero** with one attachment bound |
| `dst` | correct only at `0x00, 0x01, 0xC0, 0xC1`; `0x02–0x07` wrong; the bulk silently zero; `0xF6–0xFF` fault or collateral |
| `b7` | correct only at `0xAE, 0xAF, 0xEE, 0xEF` (baseline `0xAE`); **85 of 256 values are nondeterministic** across replicates |
| `tail` | bytes 1 and 3 almost entirely **silent zero** off their baseline; byte 0 is nondeterminism-heavy |

`tile_read_mrt` reproduces the same shape shifted by its baseline (`dst` OK at
`0x08, 0x09, 0xC8, 0xC9`; `rt_index` OK at `0x08, 0x09, 0x88, 0x89`) and additionally resolves
**`fmt`**: correct only at `0x2E, 0x2F, 0x6E, 0x6F, 0xAE, 0xAF, 0xEE, 0xEF` — **bits 0, 6 and 7
are don't-care and bits 1–5 are the format selector**.

> **The single most useful driver fact here:** an emitter that gets `rt_index`, `dst`, `b6` or
> `fmt` wrong **does not get a fault — it gets a silent zero**, which in a BG/EOT program means
> a tile that reads as **black** rather than a program that fails loudly. Self-enforce these
> value sets; the hardware will not.

### ✅ `pixel_order` (raster-order groups) — the full accepted value sets, and a `db.json` defect (EXP-0147) — `target: G16G`

The ⏳ "byte-diff inferred" status above is superseded for this pair. Detection strength first:
with the **acquire** member's byte+4 corrupted, the read-back texel falls from `8·src` to
`1·src` — **7 of 8 serialised read-modify-writes are lost** — and the accumulated pixel falls
from `clear + 36·src` to `clear + 8·src`, byte-identical in both gated runs. So an "inert"
verdict from this litmus is a measurement, not a blind spot. **The acquire/release asymmetry is
itself a result:** the same corruption on the **release** member loses **no** updates at all.

| field | acquire member (`07 14 54 50 06 00`) | release member (`07 04 54 d0 06 00`) |
|---|---|---|
| `scope` (byte+3) | correct iff **bit4 = 1 and bit6 XOR bit7 = 1** (64/256) | correct iff **bit4 = 1 and bit7 = 1** (64/256) |
| `flags` (byte+4) | correct iff **bit0 = 0 and `(v & 0x0E) != 0`** (112/256) | correct iff **`(v & 0x0F) >= 2`** (224/256) |
| `b5` (byte+5) | **fully inert**, all 256 | **fully inert**, all 256 |

> **`db.json` defect (recorded, not patched here):** `pixel_order` declares a field `flags` at
> bits[32:40] **and** a match constant `[32,8,6]` pinning the same bits to `0x06`. The hardware
> accepts 112 (acquire) / 224 (release) distinct values there with the program still byte-exactly
> correct, so byte+4 is a **genuine field, not a constant** — and as modelled, every legal
> encoding with byte+4 ≠ `0x06` is neither decodable nor emittable.

### ✅ `vtx_out_pos`, `vtx_coord_xform`, `n3_sample_read` (EXP-0147) — `target: G16G`

- **`vtx_out_pos`:** `dst` (16 values) and `slot` (256 values) are **fully inert** in this
  carrier — every value leaves the interpolated pixel byte-exact — and the arm's litmus-power
  probe (corrupting the op-select constant) *does* move the pixel, so this is measured inertness,
  not a blind spot. **Scope limit:** the carrier has a **single output slot**, so this says
  nothing about `slot` in a program with several varyings.
- **`vtx_coord_xform.mode`:** correct exactly when `(mode & 0xF3) ∈ {0x22, 0xE2}` (8/256);
  **240 of 256 values suppress the draw entirely**, 8 give a wrong pixel. `sel`: 91 correct,
  143 no-draw, **19 genuine `Caused GPU Hang Error` faults**. `operand`: bytes 0 and 4 fully
  inert (256/256 each), **byte 3 is fault-prone**.
- **`n3_sample_read`:** `b1` and `b3` fully inert (256/256 each); 5 of the 6 `tail` bytes fully
  inert; only `tail` byte 0 matters, where **53 values fault**.

### ⛔ Fences: a bounded negative with the litmus power to mean something (EXP-0147) — `target: G16G`

`scoreboard_fence` (`07 42 02 00`, in a device-atomic carrier): **all 256 `kind`, all 128
`scope`, all 256 `mask` values leave the result bit-exact — and so does corrupting byte 0, the
opcode itself.** `compute_fence_scoped` (`87 00 80 04`; threadgroup store → barrier → +137
far-neighbour load, so every lane reads a slot written by a different simdgroup): `kind` and
`scope` fully inert; **`mask` breaks the result at exactly 10 of 256 values**
(`0x00, 0x08, 0x0C, 0x10, 0x18, 0x80, 0x88, 0x8C, 0x90, 0x98`), reproducibly.

The carriers are not powerless — neutering the neighbouring `threadgroup_barrier` breaks each
program outright — but that demonstrates *general* detection sensitivity, **not
ordering-specific** sensitivity, and the pre-registered sensitivity control (corrupt the fence's
own byte 0) **passed when it was registered to fail**. Under the frozen rule all six fence
fields are therefore reported **`untested`**, with the live `compute_fence_scoped.mask` signal
recorded as the highest-value follow-up.

### ✅ Special-register enum + shader ABI (EXP-0031, closes G-5)
**`get_sr` SR number = byte1** (splice-proven: splicing byte1 makes the output become that SR's value):

| SR | code (byte1) | SR | code |
|---|---|---|---|
| thread_position_in_grid .x/.y/.z | `0xa0/a1/a2` | threadgroup_position_in_grid | `0x9c/9d/9e` |
| thread_position_in_threadgroup | `0xa4/a5/a6` | threads_per_threadgroup | `0x98/99/9a` |
| thread_index_in_threadgroup | `0xa7` | threadgroups_per_grid | `0xa8/a9/aa` |
| simd_lane_id | `0x82` | simd_group_id | `0x85` |
| vertex_id | `0xdd` | instance_id | `0xd8` |
| base_vertex / base_instance | `0x88` / `0x8a` (**HW-VALIDATED**, EXP-0092: 9 indexed+instanced draws incl. negative/boundary params; `base_vertex==baseVertex`, `base_instance==baseInstance` exactly, both runs byte-identical) | `[[position]]`.xy (FS) | `0xa0/0xa1` |
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
  is one `0x1f`; `0x1f→0x9f` gives a 64-bit add with **hardware carry-out**). **Re-validated
  against an independently recomputed oracle on M4/G16G — exact bytes, boundary rows and the
  stated limitation are in the EXP-0146 section below.** Compiler may also emit an explicit
  carry chain (`0x32` carry-generate). 32×32→64 mul = one 12 B `0x9f`; 64×64 = 3 mul(-add)s; register shift/
  compare = multi-instr.
- *(EXP-0033 also corrected DB length-rule bugs for the `0xa7 b1∈{04,05}` 8B, `0x27 b1=01` 12B rotate, and the
  `0x10` half group — defined in `experiments/EXP-0033-int-bitfield/new_descriptors.json`, now merged into db.json.)*

### ✅ Integer-ALU emitter-grade rules (EXP-0139) — `target: G16G`

Evidence label **`HW-VALIDATED`** (dense splice sweeps plus host oracles), `target: G16G`
(local Apple M4). Source: `experiments/EXP-0139-m4-emit-ialu/RESULTS.md`. **39 fields reached
`hardware-run` and 34 `isolated-byte-diff`** of 137 blocking; **`ibitcount` (8/8) and `iunary`
(3/3) became EMITTABLE.**

**`ibfe`'s `offset` and `width` use OPPOSITE out-of-range rules.** This is the highest-value
single fact in the section for a NIR back-end:

| field | rule | evidence |
|---|---|---|
| `offset` | **LITERAL.** 0..31 shift normally; **32..63 shift the field out**. The literal model scores **64/64**; a mod-32 model scores 32/64. **The hardware does NOT implement NIR's `offset`-mod-32 masking** — a back-end that assumes it must mask in software. | dense sweep, 2 gated runs |
| `width` | **mod-32.** The mod-32 model scores **64/64**; a literal-clamp model scores 37/64. Therefore **`width = 32` ≡ `width = 0`**. | dense sweep, 2 gated runs |

The `width` result **refutes EXP-0139's own pre-registration**, scored competitively on the same
data — recorded here rather than quietly dropped.

Other results from the same sweep, all `target: G16G`:

- **`ibitcount.tail`:** dense 0..255 on a **fully synthesized** popcount shows **only bit 2 is
  load-bearing**.
- **`iunary.operand` was never one field** — it is **five one-byte sub-fields** carrying
  `ibitcount`'s meanings (defect `DEF-0139-1`, applied to `db.json`).
- **⚠️ EXP-0112's `r(R mod 64)` register aliasing does NOT transfer to `iadd2.dst`.** At
  `dst = 140/141` (register 70) the sum **never appeared in r6**. The fault boundary is
  `reg ≥ 96`, at 60 dense values, 5/5. **Do not carry an operand model across instruction
  families** — the same caution EXP-0138 records for `falu_srcmod12b` vs `falu2`.
- **`isel_reg8` has no corpus anchor, but constructing it works**: `isel8` byte+2
  `0x0f` → `0x25` executes on hardware. (Synthesis, not tokenization.)
- **`iminmax`: EXP-0113's reported nondeterminism did NOT reproduce** — 858 cases, 4× each, all
  agreed. `fmax`/`fmin` diverge from IEEE **only on NaN and denormals** (flush-to-zero plus NaN
  suppression).

> **Concurrency caution — this changes how you must read any sweep on this hardware.** Across
> **129,839 dispatches**, **44 % of gated-run faults did not reproduce** and 1,552 attempts
> carried `…ErrorInnocentVictim`. Without `experiments/FIELD-SWEEP-PROTOCOL.md` §7,
> **692 legal field values would have been labelled `fault`.** Only **3 of 29,685** cases are
> genuinely nondeterministic. A "fault" verdict from a single observation on a contended host is
> not evidence.

### ✅ Native single-instruction 64-bit integer ADD, re-validated with an oracle (EXP-0146) — `target: G16G`

Evidence label **`HW-VALIDATED`** (splice + independently recomputed oracle, two gated runs),
`target: G16G` (local Apple M4). Source: `experiments/EXP-0146-m4-emit-int-misc/RESULTS.md`.
This confirms and sharpens the "native single-op 64-bit add/sub exists" bullet above, which came
from EXP-0033 on A18/G17P.

`out[gid] = a - b` on `ulong` compiles to **six instructions with exactly ONE arithmetic op** —
an `iadd2`, bytes `1f 01 56 00 02 08 00 50 17 05`, with loads/store using element code 4
(8 bytes). **Flipping only byte0 bit 7 (`0x1f` → `0x9f`, the add/sub selector HW-validated in
RT-1a-FIX) yields an exact 64-bit ADD with carry across the 32-bit word boundary.** Because the
kernel holds one arithmetic instruction, **the carry is produced inside it.**

Verified against an independently recomputed oracle on all 8 boundary rows of a second input
set — `0x8000…0 + 0x8000…0 = 0`; `0x7FFF…F + 1 = 0x8000…0`;
`0xFFFFFFFF00000000 + 0x00000000FFFFFFFF = 0xFFFF…F`; `0xFFFF…E + 3 = 1` — 5/5 serial
repetitions, zero fault classes, both gated runs.

**Apple's compiler emits a 5-instruction chain instead**, so this is a capability Metal never
reaches. **LIMITATION, stated:** it was validated by flipping one bit in the compiler's *own*
64-bit subtract, **not synthesized from scratch**; the operand-widening byte was **located**
(byte+7 `0x50` vs `0xA8`) but **not isolated**.

Also established in the same experiment, `target: G16G`:

- **`ilogic` reaches ALL 16 boolean functions** via a collision-free
  `(op_base, lut_a & 3, lut_b & 0x0F)` selector. This **refines EXP-0102's "10 of 16"**, which
  described what MSL *source* can express, not what the encoding can reach.
- **`carry_gen` is a two-operand compare**: `p[dst] = r[byte+1] <u r[byte+3]`.
- **`iadd2` `dst ≥ 96` faults** (consistent with the 96-GPR hard boundary above).
- ⛔ **NEGATIVE, honestly scoped:** `int_alu_ehi` **0/7** — a second, independently authored
  std140 matrix copy again emitted `imad`, reproducing EXP-M4-13. `sr_read_wide` **0/6** — the
  ray-query kernel emits it, but the testbed cannot bind an `MTLAccelerationStructure`, so it
  runs returning zeros and the field is not live. **That is a testbed gap, not a hardware fact.**

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

### ✅ Pack / unpack / convert — `db.json`'s operand model was wrong; the real one is emittable (EXP-0144) — `target: G16G`

Evidence label **`HW-VALIDATED`** (dense 0..255 per byte, majority-of-3 escalating to 5),
`target: G16G` (local Apple M4). Source: `experiments/EXP-0144-m4-emit-pack/RESULTS.md`.
**`pack_convert` and `unpack_convert` are now EMITTABLE.**

> **⚠️ SELF-WITHDRAWAL, preserved.** An earlier version of EXP-0144's own results claimed
> **44 of 51** blocking fields at emitter grade. **That figure is withdrawn.** It rested on
> captures taken while a GPU test had destabilised WindowServer and taken `MTLCompilerService`
> down machine-wide. Re-measuring every case with a majority vote, and refusing to carry any
> label forward from those runs, gives **33** (31 `hardware-run`, 2 `isolated-byte-diff`);
> 18 fields return to `untested`. The 11-field difference is almost entirely **coverage**, not
> contradiction — two instruments (`cvt_bf16`, `packed_half2_hi`) and most of a third
> (`cvt_f2h_dst`) were never re-measured. Of the measurements that *were* repeated, only
> **92 of 13,783 (0.67 %)** were overturned.

**`pack_convert` — `db.json` models several live operand bytes as one opaque raw descriptor
(`fmt_word`). Measured (6,540 cases, 65/65 baseline checks, 0 indeterminate):**

| byte | `db.json` name | what it actually is | emission rule |
|---|---|---|---|
| +1 | `src_desc` | operand descriptor | `v & 0x05 == 0x04`; bits 1,3,4,5,6,7 **don't-care** |
| +2 | `fmt_class` | **1-bit enable** | reproduces the result **iff bit 1 is set**; bits 0, 2–7 inert |
| +3 | `src` | **DESTINATION register** | `reg << 1`, bit 0 don't-care — result redirected into **6 distinct** observed registers |
| +4 | `mode` | 1-bit enable | iff bit 1 set; all other bits inert |
| +5 | *(fmt_word)* | **lane-0 SOURCE register** | `reg << 2`, bits 0–1 don't-care |
| +6 | *(fmt_word)* | **lane-1 SOURCE register** | `reg << 3`, bits 1–2 don't-care, bit 0 must be 0 |
| +7 | *(fmt_word)* | descriptor | `v & 0xFB == 0x50`; bit 2 don't-care |
| +8 | *(fmt_word)* | conversion enable | **bits 2 and 6 both set** (exact over 256) |
| +9 | *(fmt_word)* | **FORMAT SELECTOR** | see table below |

**Format code table (byte+9)** — a code is listed only if ONE host model explains **all 8**
independent semantic vectors, NaN and out-of-range inputs included:

| byte+9 | format produced |
|---|---|
| `0x42 0x46 0x4A 0x4E` | **snorm2x16** (scale 32767) |
| `0x82 0x86 0x8A 0x8E` | **unorm2x16** (scale 65535) |
| `0xC2 0xC6 0xCA 0xCE` | **unorm 8-bit lanes** (scale 255) into bits [7:0] and [15:8], bits 31:16 zero — consistent with the low half of a `unorm4x8` pack, since this carrier supplies only two lanes |

Bits 2 and 3 are don't-care (hence four codes per format); bits 6:7 select the format. **The
8-bit form is a third pack format reachable from the same instruction** that our corpus never
showed, because the compiler emitted only the two 16-bit forms here. Spot-checks: `0x42`,
`(0.25, 0.75)` → `0x5FFF2000` = snorm `(8192, 24575)`, and `−1` clamps to `0x8001 = −32767`
(the symmetric scale of EXP-0079); `0x82`, same input → `0xBFFF4000` = unorm `(16384, 49151)`;
`0xC2`, same input → `0x0000BF40` = `(64, 191)` = `round(0.25·255), round(0.75·255)`.

**`unpack_convert` byte+2 — the exact rule, and it reconciles two earlier results.**

> **`unpack_convert` byte+2 reproduces the conversion iff `(byte & 0x03) != 0`.** Bits 2–7 are
> completely inert. Exact over all 256 values.

EXP-0089 found `0x56 → 0x54` breaks the instruction (`0x54 & 3 == 0`, so it does). EXP-0119's
7-bit re-sweep flipped single bits of `0x56` and found all seven inert (every such flip except
bit 1 leaves `(byte & 3) != 0`, so it is). **Neither observation was wrong — both are the same
two-bit OR-enable seen through a one-bit window.** `db.json`'s relaxed match (bit 1 only) is
still not the hardware rule.

| byte | `db.json` name | what it actually is | emission rule |
|---|---|---|---|
| +1 | `src_class` | descriptor | `bits 0,2 == 0,1` (exact over 256) |
| +2 | `cache` | **2-bit OR enable** | `(v & 0x03) != 0`; bits 2–7 inert |
| +3 | *(convert_desc)* | **DESTINATION register** | redirected into 3 distinct observed registers |
| +4 | *(convert_desc)* | **completely INERT** | all 256 values reproduce the result |
| +5 | *(convert_desc)* | **SOURCE register** | `reg << 3`, bits 0–2 don't-care |
| +6 | *(convert_desc)* | opcode/descriptor | `bits 0,2 == 0,1` (exact over 256) |
| +7 | `size` + `reg_sel` | **FORMAT + a source-register bit** | below |

**`reg_sel` is not a register selector.** `db.json` calls byte+7's high nibble "most likely the
unpack RESULT destination (role INFERRED)". Measured: `0x0A 0x8A` → **unorm8** unpack of the low
byte; `0x2A 0xAA` → **snorm16**; `0x4A 0xCA` → **unorm16** (the anchor's format); `0x6A 0xEA` →
**unorm8**. So **bits 6:5 select the format and bit 7 is don't-care**, while **bit 3 changes
which register is read**. This also explains why our own compiler emits `…1cca` for unorm2x16
and `…1caa` for snorm2x16 — a **format** difference `db.json` attributes to a register.

**The `cvt_*` cluster shares one operand layout.** `cvt_i2f`, `cvt_i2f_src` and `cvt_f2i` share
a byte layout confirmed byte for byte; **`cvt_f2h` and `cvt_f2h_dst` are the same encoding.**

| byte | `cvt_i2f` | `cvt_i2f_src` | `cvt_f2i` |
|---|---|---|---|
| +1 | bits 1,2 set | bits 1,2 set | bits 0,1,2 set |
| +2 (`mode`) | `(v & 3) != 0` | **INERT, all 256** | `(v & 3) != 0` |
| +3 (`dst`) | **`reg << 1`**, 6 registers observed | same | same |
| +4 (`src_class`) | bit 1 | bit 1 | bit 1 |
| +5 (`src`) | **`reg << 2`** | **`reg << 4`** | **`reg << 2`** |
| +6 (`cvtop`) | `bits 0,2,7 == 0,1,1` | same | bits 1,2,6 don't-care |
| +7 (`signflag`) | bit 5 | bit 5 | `bits 3,5 == 1,0` |
| +8 (`dst_class`) | — | — | bit 1 |
| +9 (`b9`) | — | — | **INERT, all 256** |

Sweeping byte+3 moves the conversion result into **six different output slots** at predictable
field values (`slot6←{0,1}`, `slot5←{6,7}`, `slot4←{10,11}`, `slot3←{14,15}`, `slot2←{18,19}`,
`slot1←{22,23}`, anchor `slot0←{24,25}`), i.e. **`field = register << 1` with bit 0 free**.
`pack_convert` byte+3 produces the **identical** map — which is why it is reclassified above
from `src` to `dst`.

**⚠️ Rounding: the ALU pack path and the PBE store path round DIFFERENTLY. Do not reuse one
rule for the other.**

- **`pack_float_to_unorm2x16` ties round to NEAREST-EVEN** (revalidated). All 16 pack semantic
  vectors matched an RTE oracle exactly, including three exact ties built with `Fraction`
  arithmetic. The competing pre-registered model — ties round **down**, as EXP-0133 measured for
  the `unorm16` **storage** path (see [`../descriptors/format-table.md`](../descriptors/format-table.md)
  §2e) — is **REFUTED for this instruction**.
- **fp16 narrowing matched IEEE round-to-nearest-even throughout**, including the `65520.0`
  overflow tie that must carry to `+inf`, subnormals, and NaN/Inf.
- ⛔ **`cvt_bf16` rounding: NOT ESTABLISHED, claim withdrawn.** The contaminated run showed every
  bfloat vector (including three exact bf16 ties) matching an RNE oracle and refuting a
  truncate-toward-zero model; that capture is inadmissible and the revalidation shard **never
  ran**. Reported as an open question with a strong prior, **not** a result.
- ⛔ **`packed_half2_hi`: NOT ESTABLISHED, claim withdrawn.** It could not be provoked from any
  MSL shape tried and is reachable only by an encoding assembled from `db.json`. All five of its
  fields are **`untested`**.

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

## ✅ NIR back-end option contract — what a portable NIR→Apple9 backend must assume (EXP-0121) — `target: G16G`

Evidence label **`HW-PROBE` + `OWN-SHADER`**, `target: G16G` (local Apple M4; A18 deferred).
Source: `experiments/EXP-0121-m4-nir-contract/RESULTS.md`, commit `1143ec55`. These are the
compiler-facing option answers, measured on hardware rather than assumed. `OPT-02` and `OPT-09`
are answered elsewhere in the gaps document.

| item | verdict | what the back-end must do |
|---|---|---|
| **OPT-01** — does preserving `fdiv` let legalization pick two distinct sequences? | **YES** | Relaxed and precise division compile to **structurally distinct** sequences — **66 vs 300 bytes**; a single `fspecial` SFU estimate versus `fspecial` **plus** a multi-instruction integer-domain refinement block. Confirms **`.lower_fdiv = false`**. Note the selector is the `fast::`/precise **namespace**, not the global compile flag alone. |
| **OPT-03** — does `pow` need a fixup beyond `exp2(y·log2(x))`? | **YES** | The naive composition returns **NaN for 22 of 53 directed edge cases** (negative base, zero base, zero exponent) that `pow` gets IEEE/C99-correct, and `pow`'s compiled body is **~27× larger (2102 vs 76 bytes)**. Confirms **`.lower_fpow = false`**: a target `pow` pseudo (or equivalent multi-instruction special-case lowering) is **required** — a bare `exp2(mul(log2))` glue is wrong. |
| **OPT-04** — is dynamic-exponent `ldexp(x,n)` one executable instruction? | **PARTIAL / NO** as a single instruction; **YES** numerically | The dedicated `fldexp` opcode in `db.json` was **never observed** across 4 fresh compile variants with runtime `n`; the compiler emits a **~200-byte integer-bit-manipulation composition** instead. That composition is numerically correct — **451/452 exact** against a DAZ+FTZ-adjusted oracle, the sole residual being a boundary-rounding edge at the exact min-normal/max-subnormal threshold. **Do not set `.has_ldexp = true`** on this evidence; assume a multi-instruction legalization. |
| **OPT-05** — can one instruction choose between two arbitrary register values? | **YES** | All **18** (type × condition) cases compile to exactly **one** fused instruction — `isel8`, in a 7-instruction 86-byte kernel — whose `selTrue`/`cmpA`/`cmpB` are **independent register operands carrying arbitrary, far-apart non-Boolean sentinels**. Enables **`.has_fused_comp_and_csel = true`**. |
| **OPT-06** — does that fused form cover every NIR condition and type? | **YES** | The same `isel8` serviced **FP32, signed I32 and unsigned I32** for all six of `eq/ne/lt/le/gt/ge`, including signed/unsigned-distinguishing bit-pattern pairs — **825/825 corpus rows** match the host oracle. **Caveat:** `cc`'s `db.json` enum lists only 7 of the values actually observed, and the `cmp_mode` field's bit-level semantics are `INTERPRETED`, not measured. |
| **OPT-07** — can a varying be read at a dynamically indexed slot? | **NO** (bounded structural negative), functionally correct via ALU-select | `iter`/`iter_flat`'s slot field is a **compile-time immediate in every observed instance** (0, 6, 8, 10, 12, 14, 16 — small constants, **never a register**). Dynamic 8-way indexing — extending EXP-0111 FS-10's 4-way test — reads **every** candidate through its own fixed-slot interpolation and selects with ALU, **8/8 exact**. Lower `support_indirect_inputs` as "materialize every candidate statically, select via ALU". No register-sourced slot path exists even at 8 candidates. |
| **OPT-08** — can a fragment output be written at a dynamically indexed slot? | **UNKNOWN / PARTIAL mechanism**, positive-leaning structure | A genuinely per-fragment-divergent 2-way **and** 3-way `[[color(n)]]` output each compile to exactly **ONE** `frag_color_store` with `rt_index = 0` (immediate) — **not** scaling 1:1 with target count, which is what the pre-registered falsifier needed for a clean negative — yet hardware readback proves correct, independent routing to 2 and 3 distinct render targets. **But MSL offers no syntax to request a dynamic-output store** (array-typed fragment-output structs are rejected, EXP-0111). **A back-end must still lower a portable dynamically-indexed fragment output as a branch/select chain over static `[[color(n)]]` outputs.** Flagged for a dedicated follow-up; this does not license a NIR-level dynamic-output primitive. |
| **OPT-10** — does a plain aligned load satisfy atomic-load ordering under fences? | **NO** | An ordinary aligned load does **not** reliably observe a cross-thread write **even surrounded by `atomic_thread_fence(mem_device, seq_cst, thread_scope_device)`**. Every combination with a plain consumer load showed massive producer/consumer timeouts at every `PAIRS ≥ 1` in both runs (e.g. `AP_fenced` at `PAIRS = 1`: **300/300 iterations never completed**, both runs), while the identical protocol with an **atomic** consumer load is fast and 100 % clean at every scale. **A compiler must NOT lower an atomic load to a plain load, fenced or not.** |
| **OPT-11** — does a plain aligned store satisfy atomic-store ordering under fences? | **YES** | A plain store observed by a **trusted atomic** load is **0 mismatches / 100 % completion** at every `PAIRS ∈ {1,4,8,16}`, both runs, and its unfenced control **breaks at `PAIRS ≥ 4`** exactly as required. A plain store **is** an acceptable substitute for an atomic store when paired with the documented device-scope fence. |

> **The joint gate fails, asymmetrically. `has_atomic_load_store` must be `false`** — it needs
> **both** OPT-10 and OPT-11 to be YES and OPT-10 is NO. This is not a wash: **`has_atomic_store`
> alone would be supportable** if the NIR/driver split ever exposes that granularity; a blanket
> atomic-load/store substitution is not.

**Explicit limitations (do not read past them):** OPT-04 tested only the exact
`ldexp(x[gid], n[gid])` idiom plus a uniform-`n` variant; OPT-06's `cmp_mode` bit-level semantics
are `INTERPRETED` from a field-interaction pattern, not measured; OPT-07/08 did **not** test
vertex-stage output-slot indexing (writing a varying *from* the vertex stage at a dynamic slot).
Everything here is **M4/G16G**; A18/G17P is deferred.


### 2026-08-30 second wave (EXP-0199…0208) — READ THE BOUND FIRST

> **Every fact here is `target: G17P`. Gate E status is now MIXED — read this before quoting any
> line.** Gates A, B and C passed across the wave (actual-byte ledgers, pre-registered
> detection-power controls, independent semantic predictors), but nine experiments ran
> concurrently, so no confirmation run had a quiet machine, and per Gate E **a contaminated run
> cannot confirm at all**.
>
> `EXP-0210` then re-ran the confirmations **serialized on an idle device**, with zero foreign GPU
> dispatch runners in every sample against the fan-out's median of 9 and peak of 17:
>
> - **Gate E MET (17 fields), and 8 instructions have since been promoted** on the strength of it —
>   `half_pack`, `irotate`, `ibitcount`, `falu3`, `falu3_ext`, `falu3_srcmod12`, `simd_reduce`,
>   `simd_shuffle`. Ledgers identical, agreement **100.0000%**. `simd_reduce.dtype` improved on the
>   quiet pair (847 moved / 1 disagree / 1 fault → **848 / 0 / 0**).
> - **Gate E NOT MET:** `ibitcount.cache` (19/20 = 95.0%, order/state-dependent, not contamination);
>   the four `tex_*` fields (captures stopped early by their own cascade guard); and four
>   `EXP-0206` control-flow arms (measured unaffordable — see the next paragraph).
>
> **⚠ A QUIET GPU FAILS HARDER, and it qualifies every hazard line below.** Same encodings, same
> ok/not-ok partition, **escalated severity**: silent-no-write → fault (**18 → 355**, identical in
> both orders); `if_push.scope` fault → **HANG** at the same values; `tex_deriv` 7 and 11 hangs →
> **48 and 48**. One experiment is the counterexample with byte-identical hard outcomes, so this is
> not an instrument artefact. **Every fault and hang label recorded in this wave was taken on a busy
> machine. The ok/not-ok PARTITION is trustworthy; the SEVERITY LABEL is not.** A busy machine was
> also *masking* contained faults as OK-but-wrote-nothing: `(v&7)==7` is 32/32 `not_written` busy
> and **32/32 fault quiet**, with the other 224 values byte-identical.
>
> Rows still marked below without a Gate E note are recorded as *liveness and geometry*, not as
> promotions.

**The structural one — read this before trusting any sweep site in this document:**

- **`isadb.decode_one` answers "do these bytes match a descriptor". It NEVER answers "does an
  instruction start here."** A stop-ruler scan (write a `stop` at every offset on a 2-byte grid;
  a halt proves a boundary the hardware honours) found **0 of 7 signature-derived occurrences were
  boundaries**. `n4_rt_word` `04 <dst> 20 80` is byte **+6 of a 10-byte instruction** (3/3 sites);
  `rtq_pred` `06 c2 00 00` likewise; `n4_cf_word` `04 01 00 00` is byte **+2 of the 6-byte
  `pop_reconverge`** (3/4). This mechanically explains DEF-0172-4 — that experiment's 256-value
  `b3` sweep was sweeping byte +5 of a `pop_reconverge`. Same shape as `cubearray_coord_const`
  being **shadowed by `pad_operand`** at an interior boundary (EXP-0204), found the same day by a
  different method. Now a protocol precondition (`FIELD-SWEEP-PROTOCOL.md` §3z). (EXP-0200)

**Documented rules that are WRONG:**

- **`tex_sample.mode` is a BITFIELD, not the documented enum, and `0x10` ("filtered sample") is
  INERT** — splicing `0x10`↔`0x00` leaves the observation bit-identical on all five representative
  arms in both runs. Exact live rule, zero exceptions on the six 100%-agreement arms:
  `(mode & 0x2C) != 0`. Bit 3 live everywhere; **bit 2 live exactly where a filter is used; bit 5
  live exactly where the LOD is implicit** (inert under explicit `level()`). The pre-registered
  enum model was refuted 1/30. *Derived after the sweep → hypothesis, not a result.* (EXP-0204)
- **`ret`/`ret_luse.linkmode`'s accepted set is `v & 3 == 2` (64/256), NOT `v & 7 == 4`** — and
  **`0x04`/`0x05`, which `db.json` calls `cf_merge`, FAULT**. Within the accepted set **bit 4 =
  restore-link**: at a non-leaf return 32 values are correct (bit 4 set) and 32 give one identical
  *coherent wrong* payload; at both leaf returns all 64 are correct. (EXP-0206)
- **`falu3.op` low-3 class 5 is `0.0 * b`, NOT a constant zero** — the result's sign follows srcB
  and an infinite srcB yields NaN. Classes 4 (`-b`), 6 (`a*b+c`), 7 (no output) confirmed
  bit-exactly; classes 0/1/2 refuted on a 3-source carrier. **`falu3_ext.op` accepts exactly
  `(v & 0xC7) == 0x06` — the two `op` fields DO NOT share an operation map**, though `db.json`
  carries one identical note on both. (EXP-0201)
- **`vary_slot`'s declared semantics are refuted** — `slot` produced **zero relocations** across
  256 values × 2 captures, while the positive control `vary_store.out_slot` matched `index<<5` on
  26/32 with six exact predicted relocations on the same observable. (EXP-0199)
- **`pop_reconverge.reserved` is not reserved** — its **low byte must be zero** (9 zero-low-byte
  values correct; 43 non-zero all give one identical wrong payload); high byte inert over 9
  values. **Gate E MET for this row** (quiet pair). (EXP-0206)
- **`tex_write.rsv10` is the write's mip LEVEL, not reserved.** (EXP-0204)
- **`frame_marker_compact` is 4 bytes, not 2**, in the tested envelope: `60 XX` is correct at 0/7
  insertion boundaries and 0/254 byte+1 values; `60 XX 00 00` is correct at 7/7. Control
  `00 00 00 00` is correct at only 2/7, so a 4-byte insertion is not automatically benign.
  *Bounded: straight-line COMPUTE carriers only.* (EXP-0199)
- **`sfu_marker` accepts 8 of the 32 values `db.json` declares** — exactly `(b0 & 0x1f) == 0x06`.
  `0x0e` satisfies the declared match but is `stop`. (EXP-0199)
- **`frag_depth_store`'s byte+2 declared match `0x54` is NOT ENFORCED AT ALL** (256/256 ok, both
  carriers), and byte+1's declared full-byte match `0x14` needs only 2 bits. (EXP-0199)
- **`get_sr.dst_hi` does NOT extend the destination register on G17P.** The register-dump carrier
  proves a relocated write *is* visible — `dst`→10 clobbers codeword slot 9, `dp_width`→0x50
  clobbers slot 8 — while `dst_hi` across 8/8 clobbers nothing. **`dp_width` is itself a bitfield,
  not the documented 4-value enum.** (EXP-0207)
- **`simd_reduce.op` decodes only bits [2:0]**; bits [7:3] are inert-within-field on all four
  carriers and the observation repeats with period 8 across the full 256-value sweep. **`op` and
  `dtype` are NOT independent** — the `{0,1,2,3} → {ior,isum,smax,umax}` map holds at `opcls=1,
  dtype=3`, but at `dtype=7` op 0 and 3 return exclusive-scan shapes. (EXP-0205)

**New emitter-usable rules:**

- **`irotate`: `byte+6 = 4 * (32 - K)` gives rotate-LEFT-by-K.** Independently of the model,
  searching all 32 amounts recovers a single amount at exactly the 33 modelled values — **32
  distinct amounts, zero formula disagreements** over 3212 (arm,value) pairs. The prior `UNSTABLE`
  refusal does not reproduce (0/3212 disagree). (EXP-0202)
- **`cvt_f2i` SATURATES**: `int(2^31 + 2^8)` returns `0x7FFFFFFF`. byte+7 is a width + sign +
  **saturation-bound** descriptor (7-way map), refining the older "bit 6 = signed vs unsigned".
  (EXP-0202)
- **`half_pack` writes the destination's HIGH 16 bits and preserves the LOW 16**, and **zeroes
  both named source half-lanes** — a side effect none of the seven pre-registered candidate models
  predicted. Its `dstlo`/`b3` are **SOURCE half-register descriptors**, and because `db.json` pins
  all eight bits of byte0, **every db-expressible encoding writes `r1`**. (EXP-0203)
- **`half_alu_fma12.ext` hides a third fp16 source at bits 40..47** (`srcC`, 256/256 oracle match
  on 3 arms, bit 7 a measured don't-care); bits 32..33 are the length selector and 34..39
  modifiers. Nothing is declared inert — byte+10 reads dead on one carrier and moves on two others
  *in the same runs*. (EXP-0203)
- **`get_sr.form` is a read-enable CONDITIONAL ON `dp_width`** — inert at `dp_width` 0x10 on 6/6
  arms, live at 0x14 on 5/5 non-vertex arms, and the effect follows the field into carriers whose
  compiler chose 0x10. At 0x14, `form=1` makes the read contribute exactly zero:
  `out(form=1) == out(form=0) - lane*65536` for all 64 lanes. (EXP-0207)
- **A mid-program `stop` terminates, and the final `stop` IS executed** — byte 0 → `0x0f`/`0x8f`
  faults reproducibly on 3 carriers in 2 runs while 6 other values are harmless. This bounds the
  older claim that corrupting any of it is a no-op. (EXP-0206)
- **Denormals are flushed to zero by the `falu3` FMA** (operand and/or result). (EXP-0201)

**Hazard walls (capability-map facts, first-class per §6):**

- **The `0xC0` destination wall is ISA-WIDE, not a `frag_color_pack` quirk.** The same `v >= 0xC0`
  wall appears independently on `ibitcount.dst`, `irotate.operands`, `ibfe.b2_bit0` and
  `ibfe.sign_ext` across three experiments — **`dst[7:6] == 0b11` is likely illegal generally**,
  encodable range 192. Confirmed on hardware for `ibitcount.dst`: 64 contiguous values fault,
  mapped with no abort path and no hangs. M4's hole at 242 does **not** reproduce on G17P.
  (EXP-0208, EXP-0202)
- **`n4_rt_word.dst` faults exactly on `{v : (v & 0b110) == 0b100}`** — 6/6 carrier-runs, 384
  fault + 1152 clean, zero exceptions, extended to a carrier the original experiment never
  measured. *But V=1 per carrier: every accepted value returns the same answer, so the movement is
  entirely the wall, and the swept byte is +7 of a 10-byte instruction.* (EXP-0200)
- **`tex_deriv.dstsrc`'s hazard family:** `0x03FFFF, 0x07FFFF, 0x0FFFFF, 0x1FFFFF, 0x3FFFFF,
  0x7FFFFF, 0xFFFFFE, 0xFFFFFF` plus `0xFBEEE7`. Mapped and excluded, the cross-run partition is
  exactly reproducible. A per-field hang budget of 2 could never attribute this. (EXP-0204)
- **Inserting the 2-byte word `01 00` at a `k_line` boundary hung the GPU 5/5 times.** Device
  recovered every time. (EXP-0199)

**Fields that are `carrier-undecidable` — NOT inert:**

- **`shift_amt_move.src_flag`** — nine carriers spanning seven operand-producer classes, 768
  byte-identical comparisons. The deciding instrument was the sibling `b_alu10_lo7.src_flag`: same
  bit, same enum, same family, and one the compiler emits at **both** values — also inert, while
  its own `src_reg` control moves at 19/20. The harness has not been shown able to see a
  source-class change at all. (EXP-0202)
- **`mesh_out_src.sel`** — dispatched for the first time ever (a mesh-pipeline sweep runner had to
  be written), but its frame can only be **destroyed**, never moved to a different valid payload.
  (EXP-0207)
- **`dev_scoreboard_fence.scope_flag`**, **`n1_word`/`n2_compact2`/`n3_word`**. (EXP-0207, EXP-0200)

**And one inert result that survived a real litmus:** `simd_ballot.cache` stayed inert through a
multi-invocation ordering litmus (4 threadgroups × 2 simdgroups, cross-simdgroup exchange, a
cross-threadgroup atomic checked against a host total) with its in-dimension control firing —
recorded as *inert in the exact tested envelope; global role unknown*, with two unexercised
dimensions named. Its sibling **`simd_shuffle.cache` is LIVE and contextual**: clearing byte+2
bit 1 where the compiler set it returns **foreign data** or a silent zero with a wrong atomic
total, isolated by a matched pair differing only in **operand provenance**. (EXP-0205)


### 2026-08-30 descriptor identity — corrections an emitter MUST have (EXP-0216/0217)

> These are **descriptor-geometry and semantics** facts derived from committed bytes and
> already-controlled oracles. No evidence label changed. Where a question is undecidable it says so
> rather than guessing.

- **`imad` has NO `srcA` field, and BOTH its operand bytes are multiplicands.**
  `dest = SEED[b5>>2] * SEED[b6>>3] + 1` fits **64/64 and 68/128**, while **both addend models fit
  0**. So an earlier repair moved the wrong *name* (`srcC_lo`, byte 6 → byte 5) instead of removing
  it. **Which multiplicand is A and which is B is UNDECIDABLE** — multiplication commutes and no
  observation separates them. **The addend is still unaccounted for.** Byte+5 is a multiplicand
  selector with `reg = v>>2` (oracle 64/64); the descriptor's own note previously read "ROLE
  UNRESOLVED — never swept", which its own sidecar contradicted with "byte+5: 0..255 dense, 512
  records".
- **`fspecial`'s operand rotation is real and correct.** Byte 3 relocates the **destination**
  (`index = v>>1`, 26/26); byte 5 selects the **source** (`index = v>>2`, 56/56, checked
  arithmetically with `rsqrt(9) = 1/3` and `rsqrt(0.25) = 2`). The `(12,4)` field is inert.
- **`falu3` is `A*B+C` reading bytes 1/3/5, with `reg = byte>>1`** — not the frozen model, which
  put srcB on byte 4 whose baseline `0x81` is register 64. **EXP-0203's own committed oracle scores
  47,030 for bytes 1/3/5 against 0 for bytes 3/4/5.** The same shape holds for `iminmax`,
  `half_alu` and `half_alu_fma12`.
- **`mov_zext16`: byte0 = `0xN3` writes `zext16(r[N])` into `r[N]`** — the same register is source
  and destination, verified against the committed pre-dump for N = 0..10; N >= 11 writes nothing.
- **Two descriptor `match` constraints are OVER-FIT and will reject encodings the hardware runs.**
  `cvt_f2h` spends 8 bits on byte 0 when only the **low nibble** (the opcode group) holds — it
  fails **6,550 of 6,555** committed encodings, and the low nibble holds on **6,515** of them; the
  high nibble is a `dst` register in every dst-parameterised sibling. `bf_alu` is worse:
  **0 of 13,144** committed encodings satisfy it (`byte1 == 0x00` on all 13,144 where the match
  wants `0x02`). **Neither match was widened**, because every candidate widening either broke
  round-trip or let one descriptor swallow another's firings — see below.
- **`bf_alu`, `bf_add_dst` and `bf_mul_dst` assign IDENTICAL spans per swept byte** (byte 3 =
  `srcA (24,8)`, byte 4 = `srcB`, bytes 5–7 = `tail (40,24)`). An apparent sibling-mnemonic
  conflict was an artefact of aggregating field counts across bytes 3–7.

**Why the over-fit matches were NOT fixed — this is a fact about the ISA, not only about us.**
All three candidate widenings leave the corpus decode *bit-identical* in clean files, leftover
bytes, instructions and resync gap. What refuses them is finer: widening `cvt_f2h` breaks
round-trip once and adds a field with no evidence; widening `bf_alu` breaks it twice and, tying
`bf_alu8_var` at four match bits, **wins on list order and swallows all 135 of that descriptor's
firings**; and the bfloat byte+2 masking recovers 112 records while **0 of the 37 corpus tokens it
re-claims carry `byte+1 == 0x00`**, the only byte+1 the hardware alias sweep held.

**And the underlying reason is context-dependence.** `0x14` is in the eight-value bfloat alias set
**and** is the byte+2 of the hardware-validated convert anchor `01 01 14 81 04 02`. The same byte+2
value means different things in different groups, so a mask that is correct for one group is wrong
for the other. An emitter must not treat these bits as a free-standing enum.


### `imad`'s addend — TWO modes, selected by byte+9 bit 3 (EXP-0218, `target: G16G`+`G17P`)

**An emitter must choose the mode explicitly; there is no single "addend field".**

```
K      = (b7 >> 3) & 0x1F          hi3 = b8 & 7
IMM8   = K | (hi3 << 5)            -- 8 bits, 0..255
sel    = (b9 >> 3) & 1             -- 0 : addend = IMM8      (value IS in the instruction)
                                   -- 1 : addend = FILE[K]   (external scalar file; NOT in it)
width  = b9 & 1                    -- FETCH MODE ONLY: 0 = 16-bit half, 1 = 32-bit word
                                   -- 32-bit fetch = FILE[K] | (FILE[K+1] << 16)
```

**This reconciles two claims in this repository that flatly contradicted each other, and retracts
neither.** EXP-M4-13 R6 recorded "the immediate is in the instruction"; DEF-0160-3 recorded "the
addend is not in the instruction". **Both are correct — each in its own mode.** Both were merely
stated as general. The two anchors the corpus was built on differ in **exactly two bytes**, byte+7
and byte+9, and byte+9 differs by **exactly bit 3**:

| anchor | bytes | mode |
|---|---|---|
| M4 | `9f 00 56 00 02 08 00 38 d0 `**`26`**` 0a 00` | immediate |
| G17P | `9f 00 56 00 02 08 00 60 d0 `**`2e`**` 0a 00` | fetch |

**Evidence.** The model was frozen before fitting and scores **381/382 on G16G** and
**1832/1832 HELD OUT on G17P**. Every immediate-only alternative — including `db.json`'s own
`(b8 & 0xF) << 5 | K` — scores **42/1832**; fetch-only scores **0/10** on the M4 population; the
best of 45 register models scores **167/4126**. The mode switch is **156/156 vs 0/128** on G16G
and 10/10 on G17P. The 32-bit form was predicted **out-of-sample** from the 16-bit table: **6/6**
and **2/2**. It is not a register by four independent tests — 384/384 encodings give an identical
addend under both G17P seed sets, one scalar addend explains all 8 M4 lanes, and 2360/2361 are
launch-stable.

**Bounds an emitter must respect — these are not resolved:**

- **On G17P, byte+9 bit 1 and bit 3 are NOT separable.** Both are 0 in all five literal-mode values
  and 1 in all six fetch-mode values ever dispatched there. *"The selector is bit 3"* is
  **G16G-direct** (64/64 flip pairs for bit 3, 0/64 for bit 1); *"there is a selector in byte+9"*
  is direct on both targets. Emit the whole byte pattern from a known-good anchor rather than
  assuming bit 3 alone on G17P.
- **Whether the fetch index is 5 bits or 8 is undecidable here** — 0 of 4086 scored cases separate
  them, because this carrier's file reads 0 above half-index 31, making "index >= 32" and "addend
  suppressed" the same observation.
- **32-bit fetch as pairs `(K, K+1)` versus word `K>>1` is undecidable** — identical at even K, and
  all 8 observed 32-bit fetches are at K = 12.
- **The (byte+7 x byte+9) cross product was never dispatched.** Immediate mode across all 32 K is
  **G16G-only**; on G17P it rests on 10 cases at K = 12.

Related, from the same analysis: **`db.json`'s `mulsel[0:3]` is one bit too wide** — byte+8's
immediate high bits are 60/60 and bit 3 is not among them (8/8 flip pairs identical).

## Confirmed: this is a wholly different ISA from G13/G14
The public dougallj/applegpu (G13) decoder produces `<disassembly failed>` or nonsense on G17P
bytes. applegpu is therefore a **structural template + ISA-agnostic testbed**, not a decoder to
extend. The A18 instruction database is built from scratch (Phase 1).

Source: `experiments/EXP-0001-shader-byte-extraction/`.


---

## 2026-08-30 G17P wave — facts added from the emit/closure experiments

> Drafted by EXP-0186, which audited which results had reached this deliverable and found
> **20 of 22 emitter-facing facts missing or refuted-but-still-stated**. Every block below is
> traced to a committed experiment artifact, carries its evidence label and the **target it was
> measured on**, and keeps the bounds the measuring experiment stated. Where a result is
> deliberately bounded it says so; a doc that drops the bound is worse than no doc.

Added by the 2026-08-30 G17P wave — these are `target: G17P`, and the last one changes how the
list must be read:

- **The half-ALU family's destination is byte0's high nibble, and `db.json` models it as a
  source** — an emitter following the descriptor writes **`r1`** every time, with no fault
  (EXP-0180, DEF-0180-1).
- **`n3_mov`'s source-register field is one bit off in `db.json`** — write the register number
  where the descriptor says and the hardware reads register `S >> 1` at half `S & 1`: **the wrong
  register *and* the wrong half**, silently (EXP-0174, DEF-0174-1).
- **A `device_store` through an unbound binding slot is silently dropped** — 254 of 256
  `base_slot` values store nothing at all, with **0 faults and 0 hangs**, no stray write and no
  diagnostic. Binding validity must be guaranteed by construction in userspace (EXP-0169 §14).
- **`vary_store.hint6` bit 4 makes the entire fragment output read `0.0`** — the whole varying
  block is lost, not just the component being stored (EXP-0163 §4).
- **`tex_sample.coord` pointed at a register the program does not keep live** returns the
  previous result unchanged, never a fault — and the fragment-stage register index **aliases with
  period 16**, so a "safe-looking" high register is not safe (EXP-0172 §2.1).
- ⚠️ **`instance_id` is not base-inclusive while `vertex_id` is** — a back end that treats them
  alike gets instanced draws with a non-zero `baseInstance` silently wrong (EXP-0178 §3.5).

> **And the premise sharpened: absence of a fault is not evidence the operation happened.**
> Across **256 `rt_index` values on four `tile_read`/`tile_read_mrt` carriers in two gated runs
> there is not a single fault** (EXP-0178 §5), and the `device_store` unbound-slot sweep produced
> **0 faults and 0 hangs over its full 256-value range** (EXP-0169 §14) — a hazard its own
> pre-registration had warned was the likeliest thing left to wedge the device. **A status code
> can never be the oracle on this hardware; the read-back must be poisoned before the run and
> checked after it.** Two instruction families, two experiments, same conclusion.

- ⛔ **The half-ALU family's DESTINATION is byte0's high nibble, and `db.json` models it as a
  source — an emitter following the descriptor can only ever write `r1`.** `target: G17P`.
  For the `0x10`/`0x11` leaders (`half_alu`, `half_alu_ext8`, `half_alu_fma12`):

  | field | what it actually is |
  |---|---|
  | **byte0 high nibble** | **destination register `n`.** `byte0 = n<<4` writes **`r[n]`'s LOW 16 bits** and **preserves `r[n]`'s HIGH 16 bits** |
  | `db.json`'s `dst` (bits 8..15) | appears in the arithmetic as a **SOURCE** |
  | byte+4 | does **not** appear in the arithmetic at all — it is the **length selector** (see the length rule below) |

  `db.json` pins all eight bits of byte0 in `match`, so a descriptor-driven emitter has no way
  to name a destination and every half-ALU result lands in `r1`. There is no fault: the program
  runs and writes the wrong register. Confirmed **three independent ways** on G17P — a dense
  destination-nibble sweep (`n = 0..15`, 16/16, two carriers, both gated runs, 100.0000%
  agreement); structurally (the seed program's 14 low-half writes land in `r_j` in **every one of
  33,470 gated cases**); and arithmetically (`r1.lo = 0x470f = 1.625 × 2.59375 + 2.84375` =
  byte+3 × byte+1 + byte+5). Two nibbles are excluded with cause and are harness artefacts, not
  exceptions: `n=15` is the store index register the harness re-seeds, and on the low carrier
  `n=13` is the second-consumer destination. This is the same defect class already documented one
  family over for `mov_zext16`, `n3_mov`, `cvt_f2h_dst` and `falu3`. `EXP-0180` (DEF-0180-1).

- ⛔ **Three exact, contiguous illegal-encoding regions found by sweeps that deliberately ran
  without a hang budget.** `target: G17P`. Each was mapped over the *full* 256-value range with
  zero counterexamples; a per-field budget of 2 would have reported "two bad values" for all
  three (see `experiments/FIELD-SWEEP-PROTOCOL.md` §3(c)).

  | field | rule | region | class |
  |---|---|---|---|
  | `frag_color_pack.dst` | `dst[7:6] == 0b11` | `0xC0`–`0xFF`, **64 values** | **HANG** — `0x00`–`0xBF` are all clean, so the real encodable range is **192, not 256** |
  | `device_store.index_reg` | `(v & 0x60) == 0x60` | `0x60`–`0x7F` and `0xE0`–`0xFF`, **64 values** | fault (bit 7 is a don't-care — the `0x00`–`0x7F` map repeats exactly in `0x80`–`0xFF`) |
  | `device_store.extmode` | `v >= 0xFC` | `0xFC`–`0xFF`, **4 values** | fault |
  | `half_alu*.opflags` | `(byte+2 >> 3) >= 16 ∧ (byte+2 & 7) ∈ {4,5}` | opflags bit 4 set with `opsel` = hadd or hmul | fault, 128 cases, zero counterexamples |

  The three fault walls are **faults, not hangs** — per-command-buffer errors, fault-contained,
  no reset and no wedge, with the sweeps running through them at full speed. The
  `frag_color_pack.dst` wall **is** hangs: 64 of them, and the device survived all 64 with no
  reset. `EXP-0168` §8.1, `EXP-0169` §15, `EXP-0180` §4.

- ⛔ **In a VERTEX shader every `sr_sel` with bit 7 clear FAULTS the command buffer** — all 128
  values `0x00`–`0x7F`, contiguous, zero counterexamples, both gated runs. Nothing at or above
  `0x80` faults in any stage. **A back end must never emit a bit-7-clear selector**, and must
  know that the failure mode is stage-dependent: **loud in vertex, near-silent in compute**,
  where the same encoding does not fault at all and instead writes **one lane of 64**, leaving
  the other 63 untouched. The single-lane effect is the *whole program* retiring one invocation,
  not the SR datapath: an integrity sentinel written by a separate `device_store` carrying no
  SR value lands on that same single lane. `HW-VALIDATED`, `target: G17P`, `EXP-0178` §3.1–§3.3
  (256 values × 3 stage carriers × 2 gated runs, 100.00% cross-run agreement, zero
  disagreements).

  > **This REFINES `EXP-0092`; it does not refute it.** That exhaustive M4 sweep found no
  > `sr_sel` value raising `STATUS != OK` — and it ran on a **compute** carrier, which
  > `EXP-0178`'s compute arm reproduces exactly (0 faults in 256 values, both runs). **The
  > divergence is STAGE, not target.** The M4 record is correct about what it measured. An
  > experiment can be exhaustive over the whole encodable range, densely swept and cross-run
  > agreed **and still be blind**, because one carrier cannot see a dimension it does not vary.

- ⚠ **`vertex_id` is base-inclusive in hardware; `instance_id` is NOT.** `0xdd` returns
  `index + baseVertex`; `0xd8` returns the **raw instance ordinal**, and `baseInstance` is added
  **in software**. A back end that assumes the two behave alike gets instanced draws with a
  non-zero `baseInstance` **silently wrong**. `HW-VALIDATED`, `target: G17P`, `EXP-0178` §3.5 —
  and the compiler-inserted constant was **measured, not assumed**: seven selectors with no
  vertex-stage meaning (`0x9c`, `0x9d`, `0x9e`, `0xa0`, `0xa1`, `0xa4`, `0xc5`) all read exactly
  `5`, seven independent zero-expectations agreeing on `K = baseInstance = 5`. Subtracting `K`,
  `0xdd` ramps `9, 10, 11` across three vertices (`baseVertex = 9`) and `0xd8` reads flat `2`.

  **Bounded, and the bound matters.** *In a vertex program that does not declare
  `[[base_vertex]]`/`[[base_instance]]`, selectors `0x88` and `0x8a` read 0 on G17P.* The
  alternative — that the driver only arms them when the shader declares the builtin — is **not
  excluded**, so this is deliberately **not** recorded as refuting the enum entry (unlike
  `0xa8`, where the shader asks for nothing and the register still contradicts its documented
  meaning). `EXP-0178`'s vertex arm is reported **differentially** for the same reason: its
  harness scored `0x8a` as correct because oracle and observation both said 5, which is a right
  answer for the wrong reason, and its two passes are not cited as validations of anything.

- **CALL is EMITTABLE — every byte generated, none copied.** `target: G17P`, `HW-VALIDATED`.
  192 distinct generated calls × 2 gated runs = **384/384 correct, zero faults, zero hangs, zero
  disagreements**; each `call`, callee and `ret` was produced from the descriptor's declared bit
  positions with nothing lifted from a compiled shader (`EXP-0179` §2–§3).

> **Confirmed on the documentation target, and the hazard is sharper than "no fault".**
> `EXP-0178` §5 re-measured every value set above on **G17P**, over **four** carriers (two per
> instruction, differing in attachment count, spatial extent, the arithmetic consuming the read,
> and the presence of a colour store that reads no tilebuffer at all) and two gated runs —
> 9,428 cases per run, zero measurement failures, zero innocent victims. The M4 sets were frozen
> into the analysis **before** the runs as the hypothesis under test, and **every one transfers
> unchanged**: `read_en` = byte+6 bit 0, `rt_index` correct only at `0x00/0x01/0x80/0x81`
> (`_mrt`: `0x08/0x09/0x88/0x89`), the `dst` fault wall **exactly `0xf6`–`0xff`, contiguous,
> byte-identical on all four carriers**, and `_mrt.fmt`'s eight legal encodings with **104 of
> 256 values silently zeroing**.
>
> **The sharpening: across all 256 `rt_index` values on four carriers in two runs there is NOT A
> SINGLE FAULT.** Absence of a fault proves nothing about whether the read landed. A poisoned
> read-back, never the status code, must be the oracle — the same lesson the `device_store`
> unbound-slot result teaches in a second instruction family.
>
> **Still not emittable, and why.** `tile_read` remains blocked by `b2`, `b4`, `b6_hi`, `b7`,
> `tail`; `tile_read_mrt` by `b4`, `b6_hi`, `tail`. `b2`/`b4`/`b6_hi` never moved on either
> carrier over their full ranges in both runs, but they stay `untested` **as a limit of the
> carriers, not as "the field is inert"** — the dimension a `raw`-typed byte controls is
> unknown. `b7` *moves* (229 of 256) but does **not reproduce** (91.0% cross-run agreement, 23
> disagreeing values), and that instability reproduces `EXP-0164`'s M4 instability, making it a
> property of the field rather than of one machine's weather.

### ✅ `nir_op_mov` IS CLOSED — `n3_mov` moves one GPR to a DIFFERENT GPR (EXP-0174/EXP-0175) — `target: G17P`

Evidence label **`HW-VALIDATED`, generated with zero copied bytes.** This closes the gap
`docs/isa/register-move-and-liveness.md` records an external compiler engineer hitting head-on.

`n3_mov` is a **16-bit half-register move** with independent source-half and destination-half
selection:

- **`iter_at.loc` is bit 1 ALONE — two classes of exactly 128 values.** `bit1 = 0` → **centroid**,
  `bit1 = 1` → **per-sample**; **bit 0 and bits 2..7 are don't-care** (`0x81` behaves exactly as
  `0x01`, `0x83` exactly as `0x03`). This **refines** the enum `{1: centroid, 3: sample}`: the
  enum lists two legal values, the hardware has one selector bit and seven free bits, which is
  strictly more useful to an emitter — it now knows what it may leave alone. `HW-VALIDATED`,
  `target: G17P`, `EXP-0163` §2. Read back at probe pixel (8,8) of a 4-sample resolved target,
  a `centroid_perspective` varying is `3249.99976` for `loc & 2 == 0` and `3312.49976` for
  `loc & 2 != 0`, other channels untouched.

  > **The field has NO EFFECT below 2 samples, and that is why it read inert for a whole wave.**
  > `0 / 256` values move at `rasterSampleCount == 1`; `128 / 256` move at 4. At one sample the
  > centroid, the sample point and the pixel centre are the same point, so no location selector
  > can move anything: the field was structurally unreachable, not inert. **Two carriers
  > identical in the dimension a field controls are one carrier.**
  >
  > *Method bound, corrected by the experiment against its own earlier draft:* the two builds are
  > **not** byte-identical. The vertex stage is (166 B, same sha256); the fragment stage is 174 B
  > at one sample and 482 B at four. This is a controlled comparison of the same source under one
  > changed pipeline parameter, **not** a byte-for-byte splice pair, and a reviewer should read it
  > that way. What is held constant is what the claim rests on: both `loc` values the compiler
  > itself chooses are present on both sides.

- ⛔ **`vary_store.hint6` bit 4 makes the ENTIRE fragment output read 0.0.** Bit 4 alone, two
  classes of 128, measured on **7 arms across 5 carriers** with "exactly the values with bit 4
  set" moving on every one and both runs agreeing. Setting it loses **all four fragment output
  channels — the whole varying block, not just this component.** The compiler's own values
  `0x48`–`0x4d` all have it clear. `HW-VALIDATED`, `target: G17P`, `EXP-0163` §4.

- **`tex_sample.coord` is an operand byte of the form `(reg << 1) | is32`** — the same source-byte
  convention `db.json` already documents for `falu2`, where bit 0 selects the 32-bit operand and
  the upper 7 bits are a register index. `HW-VALIDATED`, `target: G17P`, `EXP-0172` §2.1: 256
  values on each of four arms over two gated runs at **100% per-value cross-run agreement**
  (`EXP-0155` got 73–93% and reported the field unstable; the instability was a rule, not noise).

  > **On the fragment stage the register index ALIASES WITH PERIOD 16** — the live registers recur
  > at `reg`, `reg+16`, … `reg+112`. That is a **smaller period than the mod-64 ALU aliasing**
  > `EXP-0112` HW-validated, and it is why 32 of 256 values move rather than 4. The moving set is
  > reproduced with zero exceptions in both runs by
  > `moved ⟺ (v & 1) == 1 ∧ ((v >> 1) mod 16) ∈ {6, 8, 10, 14}`.
  >
  > **A coordinate pointed at a register the program does not keep live produces a silent
  > unchanged result, never a fault** — the Apple9 silent-failure signature again.
  >
  > *Scope:* filtered, implicit-LOD sampling was **deliberately excluded**. That its
  > derivative/LOD dependence caused `EXP-0155`'s instability is **supported** (the derivative-free
  > carriers are 100% reproducible) but **not demonstrated on a filtered arm**. One arm of four
  > has detection power; the other three move at zero of 256.

- **Four bytes `db.json` declares inert or reserved are LIVE, and none of the effects is small**
  (`HW-VALIDATED`, `target: G17P`, `EXP-0163` §4). Each rule is **form-specific** and must be read
  with its form:
  - **`tex_coord_setup.b6` bits 2, 3, 4, 5 must ALL be clear** — exactly the 16 values with
    `(v & 0x3c) == 0` reproduce the baseline; any of those bits set and the addressed varying
    reads `0.0`.
  - **`tex_coord_setup.idx` bit 7** (on the byte+4 == `0x42` form): clear it and that one varying
    reads `0.0` while the other three are untouched — the byte really is that store's destination
    selector, as `db.json`'s own `dst<<2` note implies. **Inert over all 256 values on the
    byte+4 == `0x00` form.**
  - **`tex_coord_setup.b8` bit 3** (plus bit 4 on two arms): same signature, zeroing exactly the
    one varying the occurrence addresses. Live only on the `0x42` form.
  - **`tex_coord_setup.b5`** bits 0, 1, 2, 4 (+3 on the `0x42` form): bit 0 set → the varying reads
    `0.0`; bit 3 with `b6` clear shifts the varying's **value** slightly (6.08333 → 6.0918 /
    6.10946) — an address/offset perturbation rather than a kill.

- **`simd_shuffle.rsv9` is NOT reserved.** On the `mode == 0x06` rotate / shuffle-and-fill form,
  bits 6 and 7 change the fill **result value** (31 → 116 → 256 across the combinations, bit 2
  giving a further distinct value) and bit 1 suppresses the stores that follow; 240–248 of 256
  values move. **Inert on the `0x00` / `0x04` / `0x05` forms.** `HW-VALIDATED`, `target: G17P`,
  `EXP-0163` §4.
