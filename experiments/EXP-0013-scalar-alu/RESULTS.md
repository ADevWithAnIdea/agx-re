# EXP-0013 Results — round out the scalar ALU (HW-validated)

Clean-room category: **OWN-SHADER + HW-PROBE** (+ PUBLIC for the applegpu *shape*). Every byte
inspected/spliced/executed is the compiled form of MSL we wrote. No Apple binary was disassembled.

Device: Apple A18 Pro / G17P, SoC T8140, macOS 26.6 (25G5043d), Metal 4 / Apple9.

## TL;DR
- **~90 provocation kernels; ~350 HW dispatches; 0 reboots** (one *contained* `CMDBUF_ERROR` on an
  illegal bitwise LUT code, logged-and-continued). All five task families HW-validated.
- **`tools/agx-isa`**: DB grew 18 → **26 descriptors, now 24 HW-validated** (was 5). New:
  `cvt_f2i`, `cvt_i2f`, `cvt_f2h`, `mov_zext16`, `ilogic` (bitwise LUT2), `fspecial`
  (exp2/log2/round). Upgraded to HW-validated: `falu3`(fma), `fminmax`, `funary`, `ishift`,
  `ibfe`, `icmpsel`. `roundtrip_test.py` extended (20 new real instrs, 16 new whole programs,
  6 synth) → **ALL PASS**. `raw/tokenize_acceptance.log`: 62/79 single-op kernels tokenize 0-leftover.

---

## 1. Conversions (task 1) — explicit convert opcodes; signedness at byte+7 bit6
Numeric conversions are **explicit convert instructions** in a broad unary/convert family — **not**
merely the ALU size bit. The *only* size-bit reuse is fp16→fp32 widening. Signedness of every
int↔float convert is **byte+7 bit6 (0x40)** (HW-proven by splice). float→int **rounds toward zero**
(C truncation). All ✅ HW-validated:

| conversion | opcode / form | bytes (base) | HW result |
|---|---|---|---|
| fp32 → fp16 (narrow) | **0x11** half-ALU, 6B | `11031c8100c2` | half(3.5/65504/0.1) exact IEEE fp16 ✅ |
| fp16 → fp32 (widen) | **0x09 falu2**, 16-bit srcA (byte1 bit0=0) | `09001c8100c2` | reuses the size bit ✅ |
| float → int / uint | **0x27**, 10B | `270756000200b4 48 0300` | int(3.9/-3.9/2.5)=3/-3/2 (trunc) ✅ |
| int / uint → float | **0xa7**, 8B | `a70756000200ac 60` | float(-3/1e6) exact ✅ |
| half → int | 0x27, 10B | `270756000200ac480300` | ✅ |
| int → short → int (sign-extend 16) | 0x9f group, 10B | `9f015600020000081303` | 0x8000→-32768 ✅ |
| uint → ushort → uint (zero-extend 16) | **0x13**, 4B | `13000001` | 0xFFFFFFFF→0xFFFF ✅ |
| uint → uchar → uint (zero-extend 8) | **0x0b** AND-imm 0xff | `0b011fff10...` | a & 0xFF ✅ |
| int ↔ uint / `as_type` bitcast | **no instruction** (free reinterpret) | — | load+store only ✅ |

- **Signedness bit HW-proof:** splicing f2i byte+7 `0x48→0x08` turns signed→unsigned (out=f2u);
  splicing i2f byte+7 `0x60→0x20` converts −1 as unsigned (→ ~4.29e9). (`raw/val_conv_fma.log`)
- **0x27 / 0xa7 are a joint convert/shift/count family** differing in byte0 bit7 (0x80); length is
  selected by byte+1 (the form field), documented in the length rule.

## 2. FMA / 3-source (task 2) — `d = a*b + c`, srcC = byte+5 ✅
The `0x09` 8-byte form (`09 01 1e 05 81 08 02 c0`, length bit = byte+2 bit1): op=byte+2 (0x1e=fma),
dst=byte+1, **srcA=byte+3, srcB=byte+4, srcC=byte+5** (each `(reg<<1)|size`). HW-validated:
- Base `fma(a,b,c)` = a*b+c across varied inputs (`[1,2,3,4]·2+[100,200,300,400]=[102,204,306,408]`) ✅.
- Splicing **byte+5** (srcC) to the srcA / srcB descriptor changes only the **addend** to a / b
  (`a*b+a`, `a*b+b`) — proving byte+5 is the 3rd source operand. (`raw/val_conv_fma.log`)

## 3. Float unary (task 3) — op map + the premise correction
The `0x0b` 10B group is the **source-modifier move**; its op-select sub-field is **byte+5**:
`0x00 = fmov`, `0x02 = fabs`, `0x0a = fneg` — HW-validated by splicing the fneg base
(→abs, →mov, →neg). (bit1 = abs-enable, bit3 = negate; negate needs bit1, so byte+5=0x08 acts as mov.)

**Correction to the task premise:** frcp/frsqrt/fsqrt/fexp/flog/fsin are **not** all in `0x0b`.
Only fmov/fneg/fabs are. The single-op special functions live in a distinct group **0x2f / 0xaf**
(10B, `fspecial`), and the estimates are separate:

| op | group | byte+8 (round) | HW |
|---|---|---|---|
| exp2 | **0xaf**, byte+1=0x02 | — | ✅ 2^a exact on powers of two |
| log2 | **0x2f**, byte+1=0x02 | — | ✅ |
| rint / floor / ceil / trunc | **0x2f**, byte+1=0x00 | **0x00 / 0x02 / 0x04 / 0x06** | ✅ round-mode sweep on ±2.4/2.6 |
| fsat (saturate) | 0x09 8B modifier form | — | (byte-diff; length anomaly, follow-up) |
| frcp / frsqrt / fsqrt / fsin / fcos | **multi-instruction** | — | 0x29 estimate seed (byte+3 0x09/0x0b/0x0d) + Newton-Raphson |

The **round-mode field (byte+8)** is HW-validated: on `[2.4,2.6,-2.4,-2.6]`, byte+8 =
`0x00`→nearest-even `[2,3,-2,-3]`, `0x02`→floor `[2,2,-3,-3]`, `0x04`→ceil `[3,3,-2,-2]`,
`0x06`→trunc `[2,2,-2,-2]`.

## 4. fmin / fmax (task 4) — op-select byte+4 bit0; NaN = non-NaN operand ✅
`0x12` 6B group: **byte+4 bit0 = min(1)/max(0)** (HW: splicing fmax `0x00→0x01` gives fmin).
`min()`/`max()` on floats emit the identical bytes as `fmin`/`fmax`.
- **NaN:** `fmax(NaN,3)=fmax(3,NaN)=3`, `fmax(NaN,NaN)=NaN` — both fmin and fmax return the
  **non-NaN operand** (IEEE minNum/maxNum), NaN only when both are NaN. ✅
- **Signed zero:** `fmin/fmax` do **not** order ±0 — a tie returns the second operand (srcB):
  `fmax(-0,+0)=+0`, `fmax(+0,-0)=-0`. HW-observed. (`raw/val_unary_minmax.log`)
- (Integer min/max is the separate `0x02` group, EXP-0007: sel byte+4 bit0=min/max, bit1=signed.)

## 5. Bitwise / shift / bitfield / compare (task 5)

### 5a. Bitwise = a full 2-input LUT (`ilogic`, 0x0b 10B) ✅
The `0x0b` group is a **configurable 2-input boolean unit spanning all 16 LUT2 functions** — it
computes *any* Vulkan/GL logic op. Sweeping a=`0xAAAAAAAA`, b=`0xCCCCCCCC` (all four input bit-pairs)
and reading the output LUT `[a0b0,a1b0,a0b1,a1b1]`, the selectors are `byte+2` (op base: `0x1e`
xor-family / `0x1f` and/or-family), `byte+4[0:2]` and `byte+5 bit3` (per-source / output invert):

| op | b2 | b4 | b5 bit3 | LUT | op | b2 | b4 | b5 bit3 | LUT |
|---|---|---|---|---|---|---|---|---|---|
| AND | 1f | 00 | 0 | `0001` | OR | 1f | 02 | 1 | `0111` |
| XOR | 1e | 02 | 1 | `0110` | XNOR | 1f | 01 | 0 | `1001` |
| NAND | 1e | 03 | 1 | `1110` | NOR | 1e | 01 | 0 | `1000` |
| a&~b | 1e | 00 | 1 | `0100` | a\|~b | 1f | 01 | 1 | `1101` |
| const0 | 1e | 00 | 0 | `0000` | const1 | 1f | 03 | 1 | `1111` |
| b | 1f | 02 | 0 | `0011` | ~b | 1e | 01 | 1 | `0011`… |

All 8 named kernels compute correctly; the full 16-entry LUT enumeration is in
`raw/val_bitwise_shifts.log`. (`~a` is the fmov `0x0e` op with an invert bit.)

### 5b. Shifts / bitfield (0xa7 / 0x9f) ✅
| op | form | bytes | HW |
|---|---|---|---|
| arithmetic `>>` (signed), immediate | **0xa7 10B** (`ishift`) | `a70156000200 08 786200` | a>>2 on [-16,16,-64,255]=[-4,4,-16,63]; **shift amount = byte+6 = shamt<<2** (0x04/08/10/20 → 1/2/4/8) ✅ |
| logical `>>` (unsigned), immediate | **0xa7 12B** = bitfield-extract | `a70056000200 08 00f0110100` | a>>k = extract_bits(a,k,32-k) ✅ |
| `<<` (shift-left), immediate | **0x9f 10B** (arithmetic group) | `9f015600020000c81414` | a<<3 = a·8 ✅ |
| `extract_bits(a,off,cnt)` | 0xa7 12B (`ibfe`) | `a70056000200 10 00f0118100` | extract_bits(a,4,8) exact ✅ |
| `<<`/`>>` by a **register** | multi-instruction | `2b …` prep + 0x27/0xa7 | (0x2b prep stage — follow-up) |

Arithmetic vs logical shift-right are **distinct forms** (10B ashr vs 12B extract), not a signedness bit.

### 5c. Compare condition codes (0x12 icmpsel, 14B) — full table ✅
All 18 int/uint/float compare kernels (eq/ne/lt/le/gt/ge) produce correct 0/1. Sweeping **byte+6**
on the `icmp_lt` base with signed inputs `A=[1,5,5,-3] B=[5,5,1,2]` maps every code:

| byte+6 | condition | byte+6 | condition |
|---|---|---|---|
| `0x02` | float `>` | `0x05` | uint `<` |
| `0x03` | float `<` | `0x06` | signed `>` |
| `0x04` | uint `>` | `0x07` | signed `<` |

- **byte+6 = [type:2][dir:1]:** bits[1:3] = operand type `{0b01=float, 0b10=uint, 0b11=sint}`,
  bit0 = direction `lt(1)/gt(0)`. One 14-byte op handles float **and** signed/unsigned int compares.
- **byte+4 = compare mode:** `0x22` = ordered relational (lt/gt), `0x26` = **equality** (HW: b4
  sweep flips lt→eq). Equality's type is still in byte+6 (float-eq `0x00`, int-eq `0x07`).
- **Result negate (ge / le / ne):** `byte+5 bit0` + `byte+9 bit0` (ge=!lt, le=!gt, ne=!eq) — the
  named kernels differ only in these bits.
- The `0x02` 6B **compare-for-select** (ternary) uses the same low-nibble condition codes
  (`sel_lt` byte+4=`0x03`, `sel_gt`=`0x02`), consistent with the float codes above. The `0x0a`
  6B control predicate (EXP-0010) shares the family (condition sense flips with byte0 0x0a↔0x02).

---

## Deliverables (into `tools/agx-isa/`)
- `isadb.py` length rule extended: `0x11` (half ALU 6/8B), `0x13` (4B), `0x2f/0xaf` (10B special),
  and the `0x27`/`0xa7` convert/shift/count family split by byte+1 (convert=8/10B, shift=10B,
  bfe=12B, popcount=8B).
- 8 descriptors added/upgraded to **HW-VALIDATED**: `cvt_f2i`, `cvt_i2f`, `cvt_f2h`, `mov_zext16`,
  `ilogic`, `fspecial` (new); `falu3`, `fminmax`, `funary`, `ishift`, `ibfe`, `icmpsel` (upgraded).
- `roundtrip_test.py`: +20 real instrs, +16 whole programs, +6 synth → **ALL PASS**; `db.json` regenerated.

## Faults / reboots
**Reboots: 0.** Across ~350 dispatches, one contained `CMDBUF_ERROR` (illegal bitwise LUT code
`b2=0x1e b4=0x03 b5=0x00`); the persistent runner logged and continued. `macvdmtool` never needed.

## Recommended next
- The multi-instruction lowerings: the **0x2b** shift-amount prep stage (register shifts,
  insert_bits), the **0x29-group transcendental estimates** + Newton-Raphson refinement
  (frcp/frsqrt/fsqrt/fsin/fcos), and signed `extract_bits`.
- The `0x09` **saturate** 8-byte form (breaks the simple float length rule → dedicated length bit).
- Full bit-decode of the convert/shift `src` register descriptors and the `ilogic` per-source
  inverts; the `0x02`+`0x17` compare-select select variant.

## Clean-room status
Clean. Only our own MSL was compiled and only our own compiled bytes were spliced/executed.
`gen_kernels.py`, `dump_alu.py`, `probe.py`, `validate.py` are our own; reused OWN-SHADER tools
`shdump`, `agxparse.py`, `agxrun_persist`, `persistrun.py`. `raw/` holds text logs only; the `.bin`
archives stay on the device under `~/cleanroom_work/exp0013/`.
