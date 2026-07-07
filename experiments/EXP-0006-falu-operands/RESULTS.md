# EXP-0006 Results — float ALU 2-source operand encoding (HW-validated)

Clean-room category: **OWN-SHADER + HW-PROBE** (+ PUBLIC for the applegpu *shape*).
Every byte inspected/spliced/executed is the compiled form of MSL we wrote. No
Apple binary was disassembled or introspected.

Device: Apple A18 Pro / G17P, SoC T8140, macOS 26.6 (25G5043d), Metal 4 / Apple9.

## TL;DR — the resolved `falu2` bit-layout (6-byte, little-endian)

`d = op(srcA, srcB)`. Bit `b` = byte `b//8`, bit `b%8`. Canonical `a+b`
(`--no-fast-math`) = `09 01 1c 05 00 c0`.

| bits | field | meaning | status |
|---|---|---|---|
| `[0:4]` | group | `0x9` = float-ALU group (low nibble of byte0) | HW (tokenizes clean) |
| `[4:8]` | **dst** | destination register number (byte0 high nibble) | **HW-VALIDATED** |
| `[8]` | **srcA size** | `1`=32-bit, `0`=16-bit (reads low half) | **HW-VALIDATED** |
| `[9:16]` | **srcA reg** | source-A register number (`idx>>1`) | **HW-VALIDATED** |
| `[16:19]` | **opsel** | `0b100`=fadd, `0b101`=fmul | HW (EXP-0005) |
| `[19:24]` | opflags | source cache/discard (last-use) hints | inferred |
| `[24]` | **srcB size** | `1`=32-bit, `0`=16-bit low half | **HW-VALIDATED** |
| `[25:32]` | **srcB reg** | source-B register number | **HW-VALIDATED** |
| `[32:39]` | ctrl | control (low 2 bits must be 0 for a valid store) | inferred |
| `[39]` | **srcB-imm mode** | `0`=srcB register, `1`=srcB packed immediate | **HW-VALIDATED** |
| `[40:43]` | mod_lo | source-mode low bits | inferred |
| `[43]` | **srcB negate** | `a + (−b)` | **HW-VALIDATED** |
| `[44:48]` | mod_hi | source-mode high bits (`0xC` base observed) | inferred |

**Source operand byte = `(reg << 1) | is32`.** bit0 selects 32-bit(1)/16-bit(0);
16-bit reads the **low** halfword. A source is a full byte (`b1`=srcA, `b3`=srcB);
dst is only byte0's high nibble.

## 1. dst / srcA / srcB — roles and register encoding

**Method.** Canonical `out=a+b` kernel (one fadd), distinct power-of-two inputs
`A=[1,2,4,8]`, `B=[16,32,64,128]`. Swept each ALU byte over 0..255, classified
the output (`raw/add_sweep_rel0x*.log`).

- **srcA = byte1 (`b1`), srcB = byte3 (`b3`)** — both sweeps yield clean *sums*;
  neither redirects storage. Splicing `b3`: `0x01`→`a+a`, `0x05`→`a+b` (orig),
  even indices→`a` (16-bit low-half of a float = 0). Splicing `b1` symmetric with
  `b`. (`add_sweep_rel0x1.log`, `add_sweep_rel0x3.log`.)
- **Register encoding `(reg<<1)|size`** — HW-confirmed across registers via
  `map5` (`raw/map5_srcB_sweep.log`): srcB `0x09`→reg4=`a`, `0x0b`→reg5=`b`,
  the even/16-bit variants read the low half (=0 for these floats). Cross-check:
  our device loads write dest-field `reg<<1`; the ALU reads `(reg<<1)|1`.
- **dst = byte0 high nibble `[4:8]`** — **HW-VALIDATED** with `dstc` (both sources
  kept live so dst is a fresh reg). Sweeping `b0[4:8]` moves the result to exactly
  reg N: `0x39`(reg3)→result in `out`, `0x29`(reg2)→result appears in `o2`,
  `0x09`(reg0)→result appears in `o3` (`raw/validate_imm_dst.log`). map5 (dst reg5)
  = `b0=0x59`, dstc (dst reg3) = `b0=0x39`, add (dst reg0) = `b0=0x09` — all consistent.

## 2. Register model (how many are addressable)

Sweeping srcB across the **full** 0–255 (`raw/map5_srcB_sweep.log`): index `0x89`
(= `0x09 | 0x80`) reads the **same** value as `0x09` (reg4=`a`), and `0x8b`≡`0x0b`.
So index **bit7 aliases mod 64** — there are **64 physical 32-bit GPRs (r0–r63)**.
The source field is `[reg:6..7 | size:1]`; the low bit is the 16/32-bit selector,
16-bit reading the low half of the 32-bit register (bit1 is a register-number bit,
**not** a half selector — `b1=0x02` read reg1, uninitialised = 0, not a's high half).

**Inferred G17P register model vs public G13:** 64 addressable 32-bit GPRs with a
per-operand size bit (16-bit = low half), i.e. 128 16-bit lanes — comparable in
size to G13's r0–r127 (16-bit) but here the operand is **32-bit-register-numbered**
(no independent high-half addressing seen in this form), and we did **not** observe
a separate uniform-register file select in the 2-source ALU (bit7 folded back to
the GPR file). No faults across all 256 srcB values.

## 3. Source modifiers (negate / abs)

- **srcB negate = bit43 (`b5` bit3, `0x08`)** — **HW-VALIDATED**: splicing plain
  `a+b` (`…c0`→`…c8`) with signed inputs `A=[10,10,−10,−10] B=[3,−3,3,−3]` turns
  `[13,7,−7,−13]` into `a−b = [7,13,−13,−7]` (`raw/validate_size_mod.log`).
- **No dedicated srcA-negate** in the 6-byte form: for `(−a)+b` the compiler
  *commutes* operands so the negated one lands in the srcB slot and reuses bit43
  (kernel `nega` = `09 05 1c 01 00 c8`: srcA/srcB swapped vs `add`, same negate bit).
- **abs is a 10-byte extended form.** `a+|b|` compiles to
  `09 01 1c 05 02 00 00 80 0X 00` (`X`=02 for srcB, 01 for srcA). HW-VALIDATED:
  `a+|b|` gives `[13,13,−7,−7]` (PASS); splicing the negate bit into it yields
  `a−|b| = [7,7,−13,−13]` (PASS). abs is *not* encodable as a bit in the 6-byte
  form — the compiler promotes to the 10-byte form. (Distinct instruction; noted.)

## 4. Packed float immediate (srcB immediate mode)

**Mode select = bit39 (`b4` bit7, `0x80`)** — **HW-VALIDATED**: forcing it on a
reg-reg add (with `b1`=imm, srcA moved to `b3`) turns `a+b` into `a+1.0`
(`raw/validate_mode.log`). In immediate mode the layout is
`09 <imm8> <op|sign> <srcA> 80 <mods>`: `b1` is the packed immediate, srcA moves to
`b3`, and the sign is `b2` bit3 (`14`=+, `1c`=−).

**Packing — an 8-bit minifloat (NOT IEEE-754):**
```
b1 = [ exp:4 (bits7..4, bias 11) | mant:3 (bits3..1) | flag:1 (bit0 = 1, 32-bit imm) ]
sign = instruction bit 19 (byte2 bit3)
value = (1 + mant/8) · 2^(exp−11)              for exp ≥ 9   (normal)
        (mant/8)     · 2^(9−11)                for exp == 8  (subnormal)
```
Representable magnitudes: `0`, `1/32 … 30.0`. Out-of-range or non-dyadic K
(e.g. `0.1`, `255`, `256`) make the compiler fall back to a register-load form.

Worked examples (all HW-confirmed `out == a+K`, `raw/validate_imm_dst.log`):

| K | b1 | sign | check |
|---|---|---|---|
| 1.0 | `0xb1` | 0 | e=11,m=0 → 2^0 = 1 |
| 2.0 | `0xc1` | 0 | e=12 → 2^1 = 2 |
| 1.5 | `0xb9` | 0 | e=11,m=4 → (1.5)·2^0 |
| 3.5 | `0xcd` | 0 | e=12,m=6 → (1.75)·2^1 |
| 0.0625 | `0x85` | 0 | subnormal e=8,m=2 → (2/8)·2^−2 |
| 30.0 | `0xff` | 0 | e=15,m=7 → (1.875)·2^4 (max) |
| −1.0 | `0xb1` | 1 | same b1, sign bit set |

**Every K in {0, ±0.0625 … 30} spliced and produced the exact runtime value** — 16/16 PASS.

## 5. ISA database + round-trip

`tools/agx-isa/`:
- `instr_length` fixed: float group keyed on **low nibble** `0x9` (byte0 high
  nibble is dst, so `59 09 1c …` is the same group as `09 01 1c …`).
- `falu2` rewritten with the HW-validated field layout; new **`falu2i`**
  immediate descriptor; module-level `imm_encode`/`imm_decode` codec.
- `roundtrip_test.py` extended: real spliced instrs (fsub/dst3/map5/faddi/fsubi),
  synth falu2/falu2i cases, and a (D) immediate-codec table vs the HW table.
- **`python3 roundtrip_test.py` → ALL PASS**; **2 HW-VALIDATED descriptors**
  (`falu2`, `falu2i`).

## 6. Faults / reboots
- **Reboots: 0.** Across ~1500 dispatches (five 256-value byte sweeps, a 256-value
  register sweep, and the validation batches) **zero GPU faults** were triggered
  (the operand fields, unlike illegal op-selects, produce well-defined or
  no-store behaviour). The persistent runner never needed a restart.

## 7. Recommended next experiment
- Resolve full **dst width** (force dst≥16; find the extra reg bits + dst size).
- Probe the **uniform-register file** select and immediate/uniform sources for the
  other ALU groups.
- Map the **10-byte extended modifier form** and the **0x10 native-half 2-source
  group** (both seen here), and the **fma/3-source** (`falu3`) field decode.
- Integer ALU family (byte0 low-nibble `0xf`, `0x9f`) length + op map.

## 8. Clean-room status
Clean. Only our own MSL was compiled and only our own compiled bytes were spliced/
executed. `shdump.m`, `agxparse.py`, `agxrun_persist.m`, `persistrun.py`, and the
EXP-0006 probes (`probe.py`, `analyze.py`, `sweep.py`, `imm.py`, `validate.py`,
`regmap.py`) are our own tools; the only third-party input is the public MIT
applegpu (design reference, read only). `raw/` holds text logs only; the `.bin`
archives stay on the device under `~/cleanroom_work/exp0006/`.
