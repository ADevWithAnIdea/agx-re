# EXP-0033 Results — integer / bitfield instruction completeness

Clean-room category: **OWN-SHADER + HW-PROBE** (+ PUBLIC for the applegpu *shape*). Every
byte inspected/spliced/executed is the compiled form of MSL we wrote. No Apple binary was
disassembled or introspected.

Device: Apple A18 Pro / G17P, SoC T8140, macOS 26.6 (25G5043d), Metal 4 / Apple9.

## TL;DR
- **45 provocation kernels, all compiled** (including `min3`/`max3`/`median3` — MSL *does*
  expose them). **~30 HW dispatches + splice sweeps, 0 reboots.**
- All six task families characterised and **HW-validated by behaviour**; the highest-value
  op-selects are **splice-proven** (bit-count op-select; native 64-bit add/sub).
- Legend: ✅ HW-validated (behaviour matched on hardware) · 🔬 splice-proven (op-select/size
  bit spliced and observed) · 📐 byte-diff/structural (inferred from differential compile).

---

## 1. Bit-count / bit-scan — a single-op family + two lowerings

The bit-count/scan primitives are **one 8-byte op** in the `0x27`/`0xa7` count/convert family
(byte+2 == `0x56`). The op-select is **(byte0 bit7, byte+1)**, 🔬 splice-proven
(`raw/splice_count.log`, spliced on the popcount op with inputs `[1, 0xFF00, 0xF0F0F0F0, 0x80000000]`):

| op | bytes | byte0 | byte+1 | result on the sweep | status |
|---|---|---|---|---|---|
| **popcount** | `27 05 56 00 02 00 5c 04` | `0x27` | `0x05` | `[1, 8, 16, 1]` | ✅🔬 |
| **reverse_bits** | `a7 04 56 00 02 00 5c 04` | `0xa7` | `0x04` | `[0x80000000, 0x00FF0000, 0x0F0F0F0F, 1]` | ✅🔬 |
| **find-MSB** (bit-scan-reverse) | `a7 05 56 04 03 00 4e 04` | `0xa7` | `0x05` | `[0, 15, 31, 31]` (index of top set bit) | ✅🔬 |
| (degenerate) | `27 04 …` | `0x27` | `0x04` | `[0, 0, 0, 0]` | 🔬 |

- **`popcount`**, **`reverse_bits`** and **find-MSB** are **dedicated single ops**. find-MSB
  is the primitive Metal does not name directly (`0x80000000`→31, `0x0000FF00`→15, `1`→0).
- **`clz`** is a **multi-instruction lowering**: find-MSB (`a7 05 56 …`) → subtract (`31 − msb`,
  `0x1f`) → integer min/max clamp (`0x02`, handles `x==0` → 32). ✅ (`clz` exact over 6 inputs
  incl. 0 → 32 and `0x80000000` → 0.)
- **`ctz`** is a **multi-instruction lowering**: a `0x2b` low-bit-isolate prep + a count op
  (`27 05 54 …`) + clamp. ✅ (`ctz` exact incl. 0 → 32.)
- `popcount` on 64-bit = two `0x27` popcounts + an `iadd`. ✅

The current length rule mislengths the `0xa7` `byte+1∈{0x04,0x05}` forms (gives 12/10, actual
8). Correction in `new_descriptors.json → length_rule_additions`.

## 2. Bitfield insert / extract

| op | form | bytes (base) | status |
|---|---|---|---|
| **extract_bits (unsigned)** | single `0xa7` 12 B ibfe (`byte+1==0x00`) | `a7 00 56 00 02 00 10 00 f0 11 81 00` | ✅ |
| **extract_bits (signed)** | ibfe **+ sign-extension shift pair** (`0x22` shl + `0x9f` ashr) | multi-instr | ✅ |
| **insert_bits** (ibfi) | **mask + shift + combine** — no dedicated op | `0x0b` (clear field) + `0x2b` (shift insert) + `0x9f` (merge) | ✅ |

- **Unsigned `extract_bits`** = the single 12-byte `0xa7` ibfe op (confirms EXP-0013). The
  field offset is at byte+6 and the count near byte+9 (byte-diff; `extract_bits(a,4,8)`
  = `[241,240,103,255]` for `[0xABCDEF12,0x0000FF00,0x12345678,0xFFFFFFFF]`). ✅
- **Signedness of extract is a LOWERING, not a bit.** Signed `extract_bits((int)a,4,8)` emits
  the ibfe **plus** a shift-left/arithmetic-shift-right pair to sign-extend the extracted
  field. ✅ (`[-15,-16,103,-1]`.) So a compiler must lower signed extract itself; only the
  unsigned (zero-extending) extract is a single op.
- **`insert_bits` is NOT a dedicated op** — the compiler emits a 3-op lowering: a `0x0b`
  bitwise op to clear the target field of the base, a `0x2b` shift to position the insert
  value, and a `0x9f` combine (add/or of the disjoint fields). ✅
  (`insert_bits(base,ins,3,5)` exact.) This corroborates EXP-0007's note that ibfi is
  multi-instruction.

## 3. Rotate

- **Rotate by an IMMEDIATE amount = a single 12-byte `0x27` funnel op** (`byte+1==0x01`,
  byte+2==`0x56`): `27 01 56 00 02 00 6c 00 f0 15 09 00` for `rotate(a,5)`. The 12-byte
  (3-operand) form matches a funnel shift `(hi,lo,shift)`; for a rotate `hi==lo==a`. ✅
- **Rotate by a REGISTER (dynamic) amount = multi-instruction** (a `0x3b` shift-amount prep,
  two funnel/extract ops, a `(32−n)` subtract, and an OR). ✅ (`rotate(a,n)` exact.)
- A **hand-written `(x<<s)|(x>>(32−s))` compiles byte-identically to `rotate(a,n)`** — the
  compiler recognises the rotate idiom. 📐 (`rotl_var` and `rotl_manual` produced identical
  98-byte `_agc.main`.)
- No cross-word funnel builtin in MSL; a hand-written 2-word funnel lowers to shifts+OR.

## 4. min3 / max3 / median3 / clamp — exposed by MSL, **no dedicated silicon**

Metal **does** expose `min3`/`max3`/`median3` (all compiled). But they **lower to sequences of
the 2-input integer min/max** op (`0x02` group, EXP-0007), not a dedicated 3-input op:

| builtin | lowering (byte0 / sel byte+4) | status |
|---|---|---|
| `min3(a,b,c)` | `0x22` imin(a,b) `sel=7` → `0x02` imin(·,c) `sel=7` | ✅📐 |
| `max3(a,b,c)` | `0x22` imax `sel=6` → `0x02` imax `sel=6` | ✅📐 |
| `min3` (uint) | `0x22` umin `sel=5` → `0x02` umin `sel=5` | ✅📐 |
| `median3(a,b,c)` | 3–4 chained `0x22`/`0x02` min/max | ✅📐 |
| `clamp(x,lo,hi)` | `0x22` imax(x,lo) `sel=6` → `0x02` imin(·,hi) `sel=7` | ✅📐 |

- The first op of each pair is the **`0x22` variant** (`= 0x02 | 0x20`; the `0x20` bit marks
  the chained/first operand); the second is the ordinary `0x02` `iminmax`. The `sel` byte+4
  codes are exactly the HW-validated EXP-0007 min/max codes (umax=4, umin=5, imax=6, imin=7).
- **Implication:** min3/max3/median3 and integer clamp are all min/max sequences — a Vulkan/GL
  backend can lower them to 2-input min/max without expecting a dedicated op.

## 5. Pack / unpack / as_type / 16-bit-packed

- **`as_type<>` bitcast is FREE — no instruction.** `as_type<uint>(half2)` / `as_type<half2>(uint)`
  compile to load+store with **zero ALU ops** (the 16-bit lanes already share the register
  layout). ✅ (`astype_h2u`/`astype_u2h` have no compute op.) Extends EXP-0013's int↔uint free bitcast.
- **Native fp16 arithmetic = the `0x10` group** — the 16-bit-destination sibling of the `0x09`
  float ALU (and of the `0x11` narrow-convert group). Same op-select: byte+2 `0x1c`=hadd,
  `0x1d`=hmul; same 6-B 2-source / 8-B fma length bit (byte+2 bit1). ✅ (`half_add` exact.)
- **`half2` (packed 2×fp16) executes BOTH lanes in ONE `0x10` op** (packed 2-lane
  SIMD-within-a-register) + a `0x18` pack to assemble the 32-bit result. ✅ (`half2_add`,
  `half2_mul` — both lanes correct: `(1.0,2.0)+(0.5,0.25)=(1.5,2.25)`.)
- **int16 does NOT pack.** `short2 + short2` = **two separate 32-bit `0x9f` integer adds**
  (one per lane); scalar 16-bit int uses the 32-bit `0x9f` group with the operand size bit.
  📐 → a packed 2×fp16 ALU exists, but no packed 2×int16 ALU.
- **`pack_float_to_unorm2x16` = a single `0x97` op**; **`unpack_unorm2x16_to_float` = a single
  `0x17` op** (format-convert + pack/unpack). ✅ (round-trip exact.) `0x97` is the same
  float→normalized-format pack family as the fragment `frag_color_pack`; `0x17` collides with
  `simd_ballot` — both need byte+2 gating in the DB.

## 6. 64-bit integer — register pairs, with a **native add/sub**

64-bit `long`/`ulong` are **register pairs** (two 32-bit GPRs), loaded/stored via the 64-bit
data-width memory ops (`0x59` load width, EXP-0012).

| op | lowering | status |
|---|---|---|
| **add / sub** | **native single `0x9f`/`0x1f` op** on a register pair (HW carry) — *or* an explicit carry chain | ✅🔬 |
| **32×32 → 64 mul** (widening) | single 12-B `0x9f` mul (`byte+1==0x00`), 64-bit product | ✅ |
| **64×64 → 64 mul** | 3 mul(-add) ops (schoolbook cross terms) | ✅ |
| **shift `<<`/`>>` by register** | multi-instruction (`0x8b`/`0x5b` shift-prep + extract + combine) | ✅ |
| **compare `<`** (signed & unsigned) | multi-instruction (compare-high / compare-low / combine) | ✅ |
| **popcount** | 2× `0x27` popcount + `iadd` | ✅ |

- **The integer add/sub ALU has a NATIVE 64-bit register-pair mode.** `u64_sub` compiled to a
  **single `0x1f` op**; **splicing its byte0 `0x1f`→`0x9f` produced a correct 64-bit ADD with
  hardware carry** across the 32-bit boundary — 🔬 splice-proven (`raw/splice_u64.log`):
  `0xFFFFFFFF + 1 → 0x1_00000000`, `0xFFFF…FFFF + 1 → 0` (carry-out), `0x1234…DEF0 + …4321 →`
  correct high word. So one op does 64-bit add/sub; the 64-bit width lives in the operand
  descriptors + the `0x59` load/store data-width, not a distinct opcode.
- The compiler **also** emits an alternate **explicit carry-chain** form for add (`u64_add`:
  low `0x9f` add + a **`0x32` carry-generate** + high add + carry add). Both forms give correct
  results; why the compiler picks the chain for add but the native op for sub is an open
  follow-up.
- **32×32→64 widening multiply is a single op** — the multiplier produces a full 64-bit
  product from 32-bit inputs in one 12-byte `0x9f` mul. ✅ (`0xFFFFFFFF² = 0xFFFFFFFE00000001`.)

---

## Deliverables
- `new_descriptors.json` — **7 new/refined descriptors** (`ibitcount`, `irotate`, `half_alu`,
  `pack_convert`, `unpack_convert`, `iminmax_chain`, `iadd2_64_refine`) + **6 length-rule
  additions**, in the `tools/agx-isa/db.json` schema. HW-validated unless the `provenance`
  says inferred/byte-diff. (Orchestrator merges into `tools/agx-isa/`.)
- Harness (our own): `gen_kernels.py`, `dumpall.py`, `analyze.py`, `runval.py`,
  `splice_count.py`, `splice_u64.py`, `halfpack_val.py`, `cmp64.py`, `kernels/*.metal`.
- `raw/` — text logs only (`hex_dump.log`, `runval.log`, `splice_count.log`, `splice_u64.log`,
  `halfpack_val.log`, `cmp64.log`).

## HW-validated vs inferred (summary)
- **Splice-proven (🔬):** bit-count/scan op-select (popcount/reverse_bits/find-MSB); native
  single-op 64-bit add/sub with carry.
- **HW-validated behaviour (✅):** every one of the 45 kernels' runtime output (bit-count/scan,
  extract u/s, insert, rotate imm/var, min3/max3/median3/clamp, half/half2/pack/unpack,
  64-bit add/sub/mul/widen/shift/compare/popcount).
- **Byte-diff / structural (📐):** the multi-instruction *decompositions* (clz/ctz/signed-extract/
  insert/rotate-var/min3/median3/64-bit shift & compare), the `0x22`/`0x2b`/`0x18` helper op
  roles, and all operand-field bit-packings within the new ops.

## Recommended next
1. Bit-decode the bit-count/scan and rotate operand fields; the `0x2b/0x3b/0x5b/0x8b`
   shift-prep family (length + semantics) — the shared engine behind register shifts, ctz,
   insert_bits and 64-bit shifts.
2. The `0x32` 64-bit carry-generate op, and confirm/measure the native 64-bit add path
   (splice a `0x9f` pair op directly; find the operand "64-bit size" bit).
3. `0x97`/`0x17` pack/unpack snorm/half variants + byte+2 collision-gating vs
   frag_color_pack / simd_ballot for the merged DB.

## Clean-room status
Clean. Only our own MSL was compiled and only our own compiled bytes were inspected/spliced/
executed. Reused OWN-SHADER tools (`shdump`, `agxparse.py`, `agxrun_persist`, `persistrun.py`,
`intprobe.py`) and READ-ONLY `tools/agx-isa` for tokenizing. No `docs/`, `PROVENANCE`,
`tools/agx-isa/`, `tools/iotrace/` or `reviews/` were edited; nothing was committed.
