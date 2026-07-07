# A18 Pro (G17P) AGX — Instruction Encoding Tables

> **Generated** from `tools/agx-isa/db.json` by `tools/agx-isa/gen_encoding_tables.py` (2026-07-07). Regenerate after any DB change; do not hand-edit. This is the **authoritative, self-contained encoding table** a driver author reads to emit A18 Pro AGX instructions — 75 instruction descriptors.

**Clean-room:** every encoding here was learned from the compiled form of MSL **we wrote** (OWN-SHADER) — by byte-diffing our own shaders and by splicing bytes and running them on the real A18 Pro GPU (hardware validation). No Apple binary was disassembled. See `../../CLAUDE.md`.

## How to read this

- Bit numbering: an *N*-byte instruction is one **little-endian** integer. Bit 0 = bit 0 of byte 0; bit 16 = bit 0 of byte +2; so *byte offset +k, bit b* = bit (8·k + b).
- **Length** is a function of byte 0 (the group) plus a per-group length bit/signature — the first parcel does *not* encode length on G17P. The full length rule is the byte-0 table in the [Length rule](#length-rule-byte-0) appendix and `tools/agx-isa/isadb.py::instr_length`.
- **Match** = the constant bits that identify the instruction. **Fields** = every non-constant bit, with its bit-range, type, and enum values where known.
- Field **type**: `register` · `immediate` · `enum` · `modifier` · `opcode-select` · `raw/unmapped` (byte-diff-localized but not individually bit-decoded).

## Contents

- [Float ALU](#float-alu)
- [Integer ALU](#integer-alu)
- [Conversions / pack](#conversions--pack)
- [Bitwise / logic](#bitwise--logic)
- [Move / special register](#move--special-register)
- [Memory access](#memory-access)
- [Atomics](#atomics)
- [Texture / sampler](#texture--sampler)
- [Control flow / function ABI](#control-flow--function-abi)
- [SIMD-group / quad](#simd-group--quad)
- [Matrix](#matrix)
- [Ray tracing](#ray-tracing)
- [Barrier / ordering](#barrier--ordering)
- [Fragment stage](#fragment-stage)
- [Length rule (byte 0)](#length-rule-byte-0)

## Float ALU

### `falu2` — 2-source float ALU (fadd/fmul), reg-reg

- **Length:** 6 bytes  ·  **Match:** bits[0:4]==0x9  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `srcA_size` | [8:9] (byte+1) | enum | `0x1`=b32; `0x0`=b16 |
| `srcA_reg` | [9:16] | register |  |
| `opsel` | [16:19] (byte+2) | opcode-select | `0x4`=fadd; `0x5`=fmul |
| `opflags` | [19:24] | modifier |  |
| `srcB_size` | [24:25] (byte+3) | enum | `0x1`=b32; `0x0`=b16 |
| `srcB_reg` | [25:32] | register |  |
| `ctrl` | [32:39] (byte+4) | modifier |  |
| `srcB_imm` | [39:40] | enum | `0x0`=reg; `0x1`=immediate |
| `mod_lo` | [40:43] (byte+5) | modifier |  |
| `srcB_neg` | [43:44] | modifier |  |
| `mod_hi` | [44:48] | modifier |  |

*d = op(srcA, [-]srcB)  ; 2-source float ALU. src operand byte = (reg<<1)|is32 (bit0=size; 7-bit reg field, GPR file = up to 96 addressable 32-bit regs, EXP-0020). dst here is the compact b0[4:8] nibble (r0..r15 only); a high GPR dst uses the 8-byte falu3 form (dst=byte+1, 7-bit) -- HW seen writing r64. srcB negate = bit43. srcB-immediate mode = bit39 (see falu2i). A source may name a UNIFORM register instead of a GPR (float uniform-select ~ byte+2 bit4 / byte+5 bit1; see uniform_mov).*

### `falu2i` — 2-source float ALU, srcB packed minifloat immediate

- **Length:** 6 bytes  ·  **Match:** bits[0:4]==0x9, bits[39:40]==0x1  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `imm_flag` | [8:9] (byte+1) | modifier |  |
| `imm_mant` | [9:12] | immediate |  |
| `imm_exp` | [12:16] | immediate |  |
| `opsel` | [16:19] (byte+2) | opcode-select | `0x4`=fadd; `0x5`=fmul |
| `imm_sign` | [19:20] | modifier |  |
| `opflags` | [20:24] | modifier |  |
| `srcA_size` | [24:25] (byte+3) | enum | `0x1`=b32; `0x0`=b16 |
| `srcA_reg` | [25:32] | register |  |
| `ctrl_lo` | [32:39] (byte+4) | modifier |  |
| `mods` | [40:48] (byte+5) | modifier |  |

*d = op(srcA, K)  ; srcB is the packed non-IEEE float immediate K = imm_decode(b1, sign). exp(bits12:16,bias11) mant(bits9:12) flag(bit8) sign(bit19). Range +-{0,1/32..30}. HW-VALIDATED EXP-0006.*

### `falu3` — 3-source float ALU (fma)

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x9, bits[17:18]==0x1  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [8:16] (byte+1) | register |  |
| `op` | [16:24] (byte+2) | opcode-select | `0x1e`=fma |
| `srcA` | [24:32] (byte+3) | register |  |
| `srcB` | [32:40] (byte+4) | register |  |
| `srcC` | [40:48] (byte+5) | register |  |
| `ext` | [48:64] (byte+6) | raw/unmapped |  |

*d = a*b + c   ; three-source float ALU (fma). op=byte+2 (0x1e), dst=byte+1, srcA=byte+3, srcB=byte+4, srcC=byte+5 (each (reg<<1)|size).*

### `fminmax` — float min/max

- **Length:** 6 bytes  ·  **Match:** byte+0==0x12  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [8:16] (byte+1) | register |  |
| `op` | [16:24] (byte+2) | opcode-select | `0x1e`=fminmax |
| `srcA` | [24:32] (byte+3) | register |  |
| `sel` | [32:40] (byte+4) | enum | `0x0`=fmax; `0x1`=fmin |
| `mods` | [40:48] (byte+5) | modifier |  |

*d = fmax(a,b) (byte+4 bit0=0) or fmin(a,b) (bit0=1). NaN: returns the non-NaN operand (IEEE minNum/maxNum), NaN only if BOTH are NaN. +-0 not ordered (a tie returns srcB). (Float group byte0 0x12; the integer min/max is the separate 0x02 group, EXP-0007.)*

### `funary` — float source-modifier move (fmov/fabs/fneg)

- **Length:** 10 bytes  ·  **Match:** byte+0==0x0b, byte+2==0x0e  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | raw/unmapped |  |
| `op` | [16:24] (byte+2) | opcode-select | `0xe`=fmov |
| `srcA` | [24:32] (byte+3) | register |  |
| `srcmod` | [32:40] (byte+4) | raw/unmapped |  |
| `mod` | [40:48] (byte+5) | enum | `0x0`=mov; `0x2`=abs; `0xa`=neg |
| `ext` | [48:80] (byte+6) | raw/unmapped |  |

*d = mod(a)   ; float source-modifier move. byte+5 selects the modifier: 0x00 = mov (copy), 0x02 = fabs (|a|), 0x0a = fneg (-a). (bit1 = abs-enable, bit3 = negate; negate requires bit1 set -- byte+5=0x08 alone acts as mov.)*

### `half_alu` — native fp16 (half) ALU (hadd/hmul); half2 packs 2 lanes

- **Length:** 6 bytes  ·  **Match:** byte+0==0x10  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [8:16] (byte+1) | register |  |
| `opsel` | [16:19] (byte+2) | opcode-select | `0x4`=hadd; `0x5`=hmul |
| `opflags` | [19:24] | modifier |  |
| `srcB` | [24:32] (byte+3) | register |  |
| `tail` | [32:48] (byte+4) | raw/unmapped |  |

*d(half) = op(a, b)  ; NATIVE half-precision (fp16) float ALU. byte0 0x10 is the 16-bit-destination sibling of the 0x09 float ALU (and the 0x11 narrow-convert group); same op-select (byte+2 low-3 bits: 0b100=hadd/0x1c, 0b101=hmul/0x1d) and same 6/8-byte length bit (byte+2 bit1). A half2 (packed 2xfp16) op executes BOTH 16-bit lanes in ONE 0x10 op, then a 0x18 pack assembles the 32-bit result. (short2/2x-int16 does NOT pack: two separate 32-bit 0x9f integer adds.)*

### `falu_acc` — compact 4-byte float accumulate (reduction)

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0x9, byte+2==0x38  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `srcA` | [8:16] (byte+1) | register |  |
| `srcB` | [24:32] (byte+3) | register |  |

*d = srcA (+) srcB  ; COMPACT 4-byte float accumulate (float-ALU group low-nibble 9, byte+2 == 0x38 = opsel with the arithmetic-enable bit clear vs the 6-byte 0x3c fadd). Omits the byte+4/+5 modifier tail of the 6-byte falu2, so the compiler emits it for plain reduction accumulates. byte+3 = srcB register descriptor.*

### `cvt_f2h` — fp32 -> fp16 narrowing convert

- **Length:** 6 bytes  ·  **Match:** byte+0==0x11  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | raw/unmapped |  |
| `op` | [16:24] (byte+2) | raw/unmapped |  |
| `src` | [24:32] (byte+3) | raw/unmapped |  |
| `b4` | [32:40] (byte+4) | raw/unmapped |  |
| `tail` | [40:48] (byte+5) | raw/unmapped |  |

*d(half) = half(a)  ; fp32 -> fp16 narrowing convert. byte0 0x11 is length-polymorphic on byte+1: byte+1 == 0x03 = this 6-byte convert; byte+1 in {0x02,0x04} = the 8/10-byte NATIVE bfloat ALU (bf_alu) below. The reverse (fp16->fp32) is the ordinary falu2 with a 16-bit srcA (byte1 bit0 = 0) -- reuses the size bit.*

### `bf_alu` — native bfloat (brain-float16) general ALU (add/mul/fma)

- **Length:** 8 bytes  ·  **Match:** byte+0==0x11, byte+1==0x02  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `opsel` | [16:24] (byte+2) | opcode-select | `0x1c`=bf_add; `0x1d`=bf_mul; `0x1e`=bf_fma(10B) |
| `srcA` | [24:32] (byte+3) | register |  |
| `srcB` | [32:40] (byte+4) | register |  |
| `tail` | [40:64] (byte+5) | raw/unmapped |  |

*d(bfloat) = op(a,b)  ; NATIVE bfloat (brain-float16) general ALU. byte0 0x11 is a DISTINCT group -- the bfloat sibling of the 0x10 native-fp16 ALU group and the 0x11 fp32->fp16 convert group -- reusing the SAME opsel byte+2 (0x1c add / 0x1d mul / 0x1e fma, the 10-byte form) as the 0x10/0x09 float groups. NOT lowered to fp32 (a single 0x11 op does the add; no widen-add-narrow sequence) and NOT the 0x10 fp16 group (byte0 differs). byte+1 = 0x02 scalar bfloat, 0x04 bfloat2 (each packed lane a separate 0x11 op). bfloat carries fp32 range (bf16 = top 16 bits of fp32), so bfloat->float is a free 0x03 widen and float->bfloat is a 0x11 byte+1==0x03 rounding convert. This descriptor names the 8-byte scalar (byte+1==0x02) add/mul; the bfloat2-packed (byte+1==0x04) and 10-byte fma (opsel 0x1e) forms tokenize by the length rule but are not separately named.*

### `fspecial` — special-function unit: rcp/rsqrt/exp2/round/sqrt/log2

- **Length:** 10 bytes  ·  **Match:** bits[0:7]==0x2f  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `fn_hi` | [7:8] | enum | `0x0`=0x2f(round/sqrt/log2); `0x1`=0xaf(rcp/rsqrt/exp2) |
| `fnclass` | [8:16] (byte+1) | enum | `0x0`=rcp|round; `0x1`=rsqrt|sqrt; `0x2`=exp2|log2 |
| `b2` | [16:24] (byte+2) | raw/unmapped |  |
| `src` | [24:40] (byte+3) | raw/unmapped |  |
| `b5` | [40:48] (byte+5) | raw/unmapped |  |
| `b6` | [48:56] (byte+6) | raw/unmapped |  |
| `b7` | [56:64] (byte+7) | raw/unmapped |  |
| `roundmode` | [64:72] (byte+8) | enum | `0x0`=nearest; `0x2`=floor; `0x4`=ceil; `0x6`=trunc |
| `b9` | [72:80] (byte+9) | raw/unmapped |  |

*d = SFU(a). Function = (byte0 bit7 fn_hi, byte+1 fnclass): (0x2f,0x00)=round[floor/ceil/trunc/rint via byte+8], (0x2f,0x01)=sqrt, (0x2f,0x02)=log2, (0xaf,0x00)=rcp(1/x), (0xaf,0x01)=rsqrt(1/sqrt x), (0xaf,0x02)=exp2(2^x). byte+6/+7 = secondary fn code. One hardware special-function op; fast-math emits it directly (~1 ULP). exp/exp10 = exp2(x*k); log/log10 = log2(x)*k; pow = exp2(b*log2(a)); a/b = a*rcp(b).*

### `fspecial_est` — transcendental estimate seed (rcp/rsqrt/sqrt NR seed)

- **Length:** 6 bytes  ·  **Match:** bits[0:4]==0x9, byte+2==0x25  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `srcA` | [8:16] (byte+1) | raw/unmapped |  |
| `subop` | [24:32] (byte+3) | opcode-select | `0x9`=rcp_estimate; `0xb`=rsqrt_estimate; `0xd`=sqrt_estimate |
| `b4` | [32:40] (byte+4) | raw/unmapped |  |
| `b5` | [40:48] (byte+5) | raw/unmapped |  |

*d = estimate(a) ; low-precision (~7.5-8 mantissa bit) hardware seed for the Newton-Raphson lowering of the correctly-rounded 1/x (subop 0x09), rsqrt (0x0b) and sqrt (0x0d). byte0 0x29, 6 bytes, byte+2==0x25 discriminator, byte+3 = function. Appears ONLY in the precise (non-fast-math) reciprocal/root lowerings; fast-math uses the single-op SFU (fspecial 0xaf/0x2f) instead.*

## Integer ALU

### `iadd2` — integer 2-source add/sub

- **Length:** 10 bytes  ·  **Match:** bits[0:7]==0x1f  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `srcA_neg` | [7:8] | modifier |  |
| `lenbit` | [8:9] (byte+1) | modifier |  |
| `b1hi` | [9:16] | raw/unmapped |  |
| `b2lo` | [16:17] (byte+2) | raw/unmapped |  |
| `arith_en` | [17:18] | modifier |  |
| `b2hi` | [18:24] | raw/unmapped |  |
| `dst` | [24:32] (byte+3) | register |  |
| `opmode` | [32:40] (byte+4) | modifier |  |
| `srcB_imm` | [40:48] (byte+5) | immediate |  |
| `b6` | [48:56] (byte+6) | raw/unmapped |  |
| `tail` | [56:80] (byte+7) | raw/unmapped |  |

*d = (srcA_neg?-srcA:srcA) + srcB   ; integer 2-source add/sub. dst=b3 (reg<<1)|size, a full 8-bit byte -> 7-bit reg (r0..r127), so unlike the 6-byte falu2's 4-bit dst nibble the integer dst reaches the whole GPR file (up to 96 regs, EXP-0020). subtract = srcA-negate (b0 bit7) + operand commute. srcB may be an 8-bit inline immediate K in [0,255] encoded as (K<<1) at b5:b6bit0 (NOT a minifloat -- EXP-0007). A source may name a UNIFORM register: uniform srcB sets byte+5 bit4 (0x10), uniform srcA sets byte+6 (0x30) -- HW byte-diff EXP-0020.*

### `imad` — integer multiply-add (imul = c=0)

- **Length:** 12 bytes  ·  **Match:** bits[0:7]==0x1f  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `srcA_neg` | [7:8] | modifier |  |
| `lenbit` | [8:9] (byte+1) | modifier |  |
| `b1hi` | [9:16] | raw/unmapped |  |
| `b2` | [16:24] (byte+2) | raw/unmapped |  |
| `dst` | [24:32] (byte+3) | register |  |
| `opmode` | [32:40] (byte+4) | modifier |  |
| `srcB` | [40:48] (byte+5) | raw/unmapped |  |
| `srcC_body` | [48:96] (byte+6) | raw/unmapped |  |

*d = srcA*srcB (+ srcC)  ; integer multiply-add (imul is this with c=0). unsigned/signed imul byte-identical (low 32 bits are sign-agnostic).*

### `iminmax` — integer min/max (signed/unsigned)

- **Length:** 6 bytes  ·  **Match:** byte+0==0x02  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | raw/unmapped |  |
| `op` | [16:24] (byte+2) | opcode-select | `0x1e`=iminmax |
| `srcA` | [24:32] (byte+3) | register |  |
| `sel` | [32:35] (byte+4) | enum | `0x4`=umax; `0x5`=umin; `0x6`=imax; `0x7`=imin |
| `selhi` | [35:40] | modifier |  |
| `srcB` | [40:48] (byte+5) | register |  |

*d = {min,max}(srcA, srcB)  ; sel bit0=min/max, bit1=signed/unsigned, bit2=1 integer (bit2=0 => float fmin/fmax, byte0 0x12).*

### `iminmax_chain` — chained min/max (min3/max3/clamp first op)

- **Length:** 6 bytes  ·  **Match:** byte+0==0x22  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | raw/unmapped |  |
| `op` | [16:24] (byte+2) | raw/unmapped |  |
| `srcA` | [24:32] (byte+3) | register |  |
| `sel` | [32:35] (byte+4) | enum | `0x4`=umax; `0x5`=umin; `0x6`=imax; `0x7`=imin |
| `selhi` | [35:40] | modifier |  |
| `srcB` | [40:48] (byte+5) | register |  |

*integer min/max, chained-operand variant (byte0 0x22 = 0x02|0x20; the 0x20 bit marks the FIRST op of a min3/max3/clamp pair whose result feeds the following 0x02 min/max). sel byte+4 = the same iminmax codes as the 0x02 group (umax=4,umin=5,imax=6,imin=7). min3(a,b,c) = 0x22 min(a,b) then 0x02 min(.,c); clamp(x,lo,hi) = 0x22 imax(x,lo) then 0x02 imin(.,hi). There is NO dedicated 3-input min3/max3/median3 op -- MSL lowers them to sequences of 2-input min/max.*

### `iunary` — integer unary (popcount / reduce)

- **Length:** 8 bytes  ·  **Match:** byte+0==0x27  ·  **Provenance:** inferred

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `body` | [8:64] (byte+1) | raw/unmapped |  |

*d = unary_int(srcA)  ; popcount observed (also clz/ctz/reduce cousins)*

### `ibitcount` — bit-count / bit-scan (popcount/reverse_bits/find-MSB)

- **Length:** 8 bytes  ·  **Match:** bits[0:7]==0x27, byte+2==0x56  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `fn_hi` | [7:8] | opcode-select | `0x0`=popcount(b1=0x05); `0x1`=reverse_bits(b1=0x04)|find_msb(b1=0x05) |
| `form` | [8:16] (byte+1) | opcode-select | `0x5`=count/scan; `0x4`=reverse |
| `b2` | [16:24] (byte+2) | raw/unmapped |  |
| `operands` | [24:64] (byte+3) | raw/unmapped |  |

*single-op bit-count / bit-scan (byte+2==0x56, 8 bytes). Operation = (byte0 bit7 fn_hi, byte+1 form): (0x27,0x05)=popcount; (0xa7,0x04)=reverse_bits; (0xa7,0x05)=find-MSB / bit-scan-reverse (index of the most-significant set bit; 0x80000000->31, 0xFF00->15). clz/ctz are NOT single ops (find_msb + 31-x + clamp; ctz adds a 0x2b low-bit-isolate). Shares byte0 low-7-bits with the 0x27/0xa7 convert family; distinguished by byte+1 form and length 8.*

### `carry_gen` — u64 carry-generate (unsigned-overflow compare for 64-bit add)

- **Length:** 6 bytes  ·  **Match:** byte+0==0x32, byte+2==0x35  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `subop` | [8:16] (byte+1) | raw/unmapped |  |
| `marker` | [16:24] (byte+2) | raw/unmapped |  |
| `srcA` | [24:32] (byte+3) | register |  |
| `cmpmode` | [32:40] (byte+4) | enum | `0x22`=ordered |
| `b5` | [40:48] (byte+5) | raw/unmapped |  |

*u64 CARRY-GENERATE. `32 01 35 03 22 81` (6 bytes). An unsigned-overflow compare in the integer compare / min-max family (byte0 0x32 = 0x02|0x30; byte+2==0x35 marker; byte+4==0x22 ordered-compare mode) detecting the carry-OUT of the immediately-preceding low-word 32-bit add (sum_lo < operand, unsigned). Its per-lane predicate feeds a following 0x05 psel that materializes the carry as {0,1}, added into the HIGH-word add. The compiler emits this explicit chain for 64-bit ADD; 64-bit SUB uses the single native 0x1f op. Siblings byte0 0x12 (a+const) and 0x22 (intermediate carry of a 3-operand add) share the byte+2==0x35 signature. Operand register bit-packing inferred (byte-diff).*

### `irotate` — rotate-by-immediate funnel shift

- **Length:** 12 bytes  ·  **Match:** byte+0==0x27, byte+1==0x01, byte+2==0x56  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | raw/unmapped |  |
| `b2` | [16:24] (byte+2) | raw/unmapped |  |
| `operands` | [24:64] (byte+3) | raw/unmapped |  |
| `tail` | [64:96] (byte+8) | raw/unmapped |  |

*d = rotate_left(a, k)  ; bit-rotate / funnel-shift by an IMMEDIATE amount. Single 12-byte op in the 0x27 family (byte+1==0x01, byte+2==0x56): the 3-operand form fits a funnel shift (hi,lo,shift); for a plain rotate hi==lo==a. Rotate by a REGISTER amount is a multi-instr lowering (0x3b shift-prep + funnel + (32-n) subtract + OR).*

### `ishift` — arithmetic shift-right immediate

- **Length:** 10 bytes  ·  **Match:** byte+0==0xa7, bits[8:9]==0x1  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | raw/unmapped |  |
| `b2` | [16:24] (byte+2) | raw/unmapped |  |
| `srcdst` | [24:40] (byte+3) | raw/unmapped |  |
| `shamt` | [48:56] (byte+6) | immediate |  |
| `tail` | [56:80] (byte+7) | raw/unmapped |  |

*d = a >> shamt  ; ARITHMETIC (sign-preserving) shift-right by an immediate. Shift amount at byte+6 encoded as (shamt<<2): 0x04->1, 0x08->2, 0x10->4, 0x20->8. (Logical >> by immediate uses the 12-byte bitfield-extract form below; register-operand shifts are multi-instr with a 0x2b prep stage.)*

### `ibfe` — bitfield-extract / logical shift-right

- **Length:** 12 bytes  ·  **Match:** byte+0==0xa7, bits[8:9]==0x0  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `body` | [8:96] (byte+1) | raw/unmapped |  |

*bitfield-extract extract_bits(a, off, cnt) (3-operand 12-byte form). Also the lowering for LOGICAL (unsigned) shift-right by an immediate: a>>k = extract_bits(a, k, 32-k).*

### `icmpsel` — compare -> select 0/1 (full condition codes)

- **Length:** 14 bytes  ·  **Match:** byte+0==0x12  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | raw/unmapped |  |
| `op` | [16:24] (byte+2) | opcode-select | `0x1d`=icmpsel |
| `srcA` | [24:32] (byte+3) | register |  |
| `cmpmode` | [32:40] (byte+4) | enum | `0x22`=ordered(lt/gt); `0x26`=equal |
| `neg_lo` | [40:48] (byte+5) | modifier |  |
| `cond` | [48:56] (byte+6) | enum | `0x2`=f_gt; `0x3`=f_lt; `0x4`=u_gt; `0x5`=u_lt; `0x6`=s_gt; `0x7`=s_lt; `0x0`=f_eq |
| `body` | [56:112] (byte+7) | raw/unmapped |  |

*d = (srcA <cond> srcB) ? 1 : 0  ; fused compare-and-select. cmpmode (byte+4): 0x22 ordered relational, 0x26 equality. cond (byte+6) = [type:float/uint/sint][dir:lt/gt]. Result negate (ge/le/ne) = byte+5 bit0 + byte+9 bit0. One op covers float & signed/unsigned int compares.*

## Conversions / pack

### `cvt_f2i` — float/half -> int/uint convert (round to zero)

- **Length:** 10 bytes  ·  **Match:** byte+0==0x27, byte+1==0x07  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b2` | [16:24] (byte+2) | raw/unmapped |  |
| `src` | [24:40] (byte+3) | raw/unmapped |  |
| `b5` | [40:48] (byte+5) | raw/unmapped |  |
| `cvtop` | [48:56] (byte+6) | opcode-select | `0xb4`=f2int |
| `signflag` | [56:64] (byte+7) | modifier |  |
| `tail` | [64:80] (byte+8) | raw/unmapped |  |

*d = (int|uint)(a)  ; float/half -> integer convert, round toward zero (truncation). byte+7 bit6 (0x40) = signed (int) vs unsigned (uint).*

### `cvt_i2f` — int/uint -> float/half convert

- **Length:** 8 bytes  ·  **Match:** byte+0==0xa7, byte+1==0x07  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b2` | [16:24] (byte+2) | raw/unmapped |  |
| `src` | [24:40] (byte+3) | raw/unmapped |  |
| `b5` | [40:48] (byte+5) | raw/unmapped |  |
| `cvtop` | [48:56] (byte+6) | opcode-select | `0xac`=int2f |
| `signflag` | [56:64] (byte+7) | modifier |  |

*d = float(a)  ; integer/uint -> float convert (round to nearest even). byte+7 bit6 (0x40) = signed source (i2f) vs unsigned (u2f).*

### `mov_zext16` — 16-bit zero-extend / narrow move

- **Length:** 4 bytes  ·  **Match:** byte+0==0x13  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `body` | [8:32] (byte+1) | raw/unmapped |  |

*d = a & 0xFFFF  ; 16-bit zero-extend / narrow move (uint -> ushort -> uint keeps the low halfword).*

### `pack_convert` — pack_float_to_unorm/snorm2x16 (compute)

- **Length:** 10 bytes  ·  **Match:** byte+0==0x97, byte+2==0x56  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | raw/unmapped |  |
| `b2` | [16:24] (byte+2) | raw/unmapped |  |
| `src` | [24:32] (byte+3) | register |  |
| `body` | [32:80] (byte+4) | raw/unmapped |  |

*packed format-conversion pack: pack_float_to_unorm2x16 / snorm / half -> a 32-bit packed word. byte0 0x97 (COMPUTE, gated by byte+2==0x56). Same op family as the fragment frag_color_pack (float colour -> attachment normalized format) -- 0x97 is the general float->normalized-format pack/convert, in both compute and fragment; disambiguated by byte+2 (compute pack 0x56 vs fragment 0x54).*

### `unpack_convert` — unpack_unorm/snorm2x16_to_float (compute)

- **Length:** 10 bytes  ·  **Match:** byte+0==0x17, bits[16:17]==0x0, bits[18:24]==0x15  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | raw/unmapped |  |
| `b2` | [16:24] (byte+2) | raw/unmapped |  |
| `body` | [24:80] (byte+3) | raw/unmapped |  |

*packed format UNPACK/convert: unpack_unorm2x16_to_float / snorm -> a float2. byte0 0x17, 10 bytes, byte+2==0x56 (COMPUTE). Reads a 32-bit packed word and expands the two normalized 16-bit lanes to floats. byte0 0x17 collides with simd_ballot (EXP-0018, also 0x17, 10B); simd_ballot is gated on byte+1==0x07, this on byte+2==0x56.*

### `half_pack` — assemble a half2's two fp16 lanes into a packed 32-bit register

- **Length:** 4 bytes  ·  **Match:** byte+0==0x18  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dstlo` | [8:16] (byte+1) | register |  |
| `src` | [16:24] (byte+2) | register |  |
| `b3` | [24:32] (byte+3) | raw/unmapped |  |

*HALF-LANE PACK (assemble a half2 into a packed 32-bit register). `18 05 18 03` (4 bytes). Combines the two fp16 lanes produced by the native-half 0x10 ALU (EXP-0033 half_alu) into one 32-bit word for the device store (and the reverse assembly for half unpacks). Confirmed 4 bytes across half2 add (`18 05 18 03`), mul (`18 05 19 03`) and fma (`18 05 1b 07`). byte0 HIGH nibble = destination register nibble -- the SAME op appears as 0x08/0x18/0x28/0x38 for dst r0/r1/r2/r3 (this descriptor matches the 0x18 dst-r1 form). byte+2 = source register (reg<<1)|hint. A longer 6-byte high-register form (byte+2==0x24, seen as 0x30/0x38 in the broad corpus) is a documented follow-up. short2/short4 (int16) does NOT pack.*

## Bitwise / logic

### `ilogic` — 2-input bitwise LUT (all 16 boolean functions)

- **Length:** 10 bytes  ·  **Match:** byte+0==0x0b, bits[17:24]==0xf  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | raw/unmapped |  |
| `op_base` | [16:17] (byte+2) | enum | `0x0`=xor-base; `0x1`=and/or-base |
| `srcB` | [24:32] (byte+3) | raw/unmapped |  |
| `lut_a` | [32:40] (byte+4) | modifier |  |
| `lut_b` | [40:48] (byte+5) | modifier |  |
| `ext` | [48:80] (byte+6) | raw/unmapped |  |

*d = LUT2(a, b)  ; 2-input bitwise logic. op_base (byte+2 bit0) picks the xor vs and/or base; byte+4[0:2] and byte+5 bit3 are per-source/output inverts -> any of the 16 boolean functions (and/or/xor/nand/nor/xnor/andn/orn/...). ~a is the fmov(0x0e) op with an invert (byte+4 bit0).*

## Move / special register

### `get_sr` — read a special register (thread/threadgroup/simd IDs, dims, VS/FS)

- **Length:** 4 bytes  ·  **Match:** bits[0:3]==0x4  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `form` | [3:4] | modifier |  |
| `dst` | [4:8] | register |  |
| `sr_sel` | [8:16] (byte+1) | enum | `0x82`=thread_index_in_simdgroup (simd_lane_id); `0x84`=simd_is_helper_thread (FS); `0x85`=simdgroup_index_in_threadgroup (simd_group_id); `0x88`=base_vertex (VS); `0x8a`=base_instance (VS); `0x98`=threads_per_threadgroup.x; `0x99`=threads_per_threadgroup.y; `0x9a`=threads_per_threadgroup.z; `0x9c`=threadgroup_position_in_grid.x; `0x9d`=threadgroup_position_in_grid.y; `0x9e`=threadgroup_position_in_grid.z; `0xa0`=thread_position_in_grid.x (FS: pixel x); `0xa1`=thread_position_in_grid.y (FS: pixel y); `0xa2`=thread_position_in_grid.z; `0xa4`=thread_position_in_threadgroup.x; `0xa5`=thread_position_in_threadgroup.y; `0xa6`=thread_position_in_threadgroup.z; `0xa7`=thread_index_in_threadgroup; `0xa8`=threadgroups_per_grid.x; `0xa9`=threadgroups_per_grid.y; `0xaa`=threadgroups_per_grid.z; `0xc5`=front_facing (FS); `0xd8`=instance_id (VS); `0xdd`=vertex_id (VS) |
| `suffix` | [16:32] (byte+2) | raw/unmapped |  |

*d[dst] = special_register[sr_sel]  ; read a built-in/special register (thread/threadgroup/simd IDs & dimensions; VS vertex_id/instance_id/base_*; FS position/front_facing) into a GPR. sr_sel = BYTE1 is the SR number (NOT byte0-hi, which is the dst GPR). byte0 low-3-bits = 0b100; bit3 is a datapath/width modifier that does not change the SR select. IDs are read on demand -- no stage preloads them into GPRs. Constant-folded builtins (e.g. threads_per_simdgroup=32) use the 2-byte mov_imm instead.*

### `mov_imm` — 2-byte small-immediate move (constant-folded builtins)

- **Length:** 2 bytes  ·  **Match:** bits[0:4]==0xc  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `imm8` | [8:16] (byte+1) | immediate |  |

*d[dst] = imm8  ; 2-byte move of a small immediate into a GPR. The compiler uses it for constant-folded built-ins (e.g. threads_per_simdgroup = 32 = 0x20).*

### `uniform_mov` — copy a uniform register into a GPR

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0xb, byte+2==0x01, byte+3==0x08  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `usrc` | [8:16] (byte+1) | register |  |

*d(GPR) = uniform_register[usrc]  ; copy a uniform (thread-invariant) register into a GPR. byte1 encodes the uniform source register; the uniform value was preloaded/precomputed by the driver or by the uniform program in _agc.main.constant_program. Compact 4-byte form; the dst nibble reaches r0..r15 (higher GPR dst would use a wider move form).*

### `stop` — conventional program-end word

- **Length:** 4 bytes  ·  **Match:** byte+0==0x0e  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `body` | [8:32] (byte+1) | raw/unmapped |  |

*conventional program-end word (whole body of an empty kernel). NOT a strictly-enforced terminator: corrupting it is a no-op (EXP-0003/EXP-0010 E4); the true end-of-program is out-of-band (the metadata code length), not this in-band token.*

## Memory access

### `device_load` — load (device / threadgroup / constant)

- **Length:** 14 bytes  ·  **Match:** byte+0==0x67  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `space` | [8:16] (byte+1) | modifier |  |
| `amode` | [16:24] (byte+2) | raw/unmapped |  |
| `extmode` | [24:32] (byte+3) | modifier |  |
| `base_slot` | [32:40] (byte+4) | immediate |  |
| `count` | [40:48] (byte+5) | immediate |  |
| `addr_lo` | [48:56] (byte+6) | raw/unmapped |  |
| `addr_hi` | [56:64] (byte+7) | raw/unmapped |  |
| `dst_width` | [64:72] (byte+8) | register |  |
| `tail9` | [72:80] (byte+9) | raw/unmapped |  |
| `tail10` | [80:88] (byte+10) | raw/unmapped |  |
| `tail11` | [88:96] (byte+11) | raw/unmapped |  |
| `elem_size` | [96:104] (byte+12) | immediate |  |
| `tail13` | [104:112] (byte+13) | raw/unmapped |  |

*load `count` consecutive 32-bit words (vector width, +5 low3) of `elem_size` bytes each (+12 bits[1:4]: k->2^(k-1) B) from the address space selected by `space` (+1 bit1: 0=device/constant, 1=threadgroup) at index_GPR * elem_size, base = buffer[base_slot] (+4). Element addressing; NO immediate offset (a[i+k] is a prior ALU add on the index). Sub-32 signed types are sign-extended by a following ALU shift; unsigned use the zero-extend load variant (+3).*

### `device_store` — store (device / threadgroup)

- **Length:** 14 bytes  ·  **Match:** byte+0==0xe7  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `space` | [8:16] (byte+1) | modifier |  |
| `amode` | [16:24] (byte+2) | raw/unmapped |  |
| `extmode` | [24:32] (byte+3) | modifier |  |
| `base_slot` | [32:40] (byte+4) | immediate |  |
| `count` | [40:48] (byte+5) | immediate |  |
| `addr_lo` | [48:56] (byte+6) | raw/unmapped |  |
| `addr_hi` | [56:64] (byte+7) | raw/unmapped |  |
| `data_width` | [64:72] (byte+8) | register |  |
| `tail9` | [72:80] (byte+9) | raw/unmapped |  |
| `tail10` | [80:88] (byte+10) | raw/unmapped |  |
| `tail11` | [88:96] (byte+11) | raw/unmapped |  |
| `elem_size` | [96:104] (byte+12) | immediate |  |
| `tail13` | [104:112] (byte+13) | raw/unmapped |  |

*store `count` 32-bit words (vector width, +5) to the address space in `space` (+1 bit1: 1=threadgroup) at index_GPR*elem_size, base = buffer[base_slot] (+4). Same field layout & element addressing as device_load. Narrowing stores (char/short) set elem_size (+12).*

### `vary_store` — vertex varying / [[position]] store to the UVS/parameter buffer

- **Length:** 8 bytes  ·  **Match:** byte+0==0x57  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `hint1` | [8:16] (byte+1) | modifier |  |
| `hint2` | [16:24] (byte+2) | modifier |  |
| `src` | [24:32] (byte+3) | register |  |
| `out_slot` | [32:40] (byte+4) | immediate |  |
| `b5` | [40:48] (byte+5) | raw/unmapped |  |
| `hint6` | [48:56] (byte+6) | modifier |  |
| `b7` | [56:64] (byte+7) | raw/unmapped |  |

*uvs_buffer[out_slot] = reg[src]  ; VERTEX-stage store of a [[position]] component or a user varying to the UVS / vertex-parameter buffer the fragment stage interpolates from (the FS 0x2f iter op reads these coefficients, EXP-0029). Memory-family opcode (byte0 0x57, low-nibble 7, sibling of 0x67 load / 0xe7 store / 0xd7 texture-write). byte+3 = SOURCE GPR; byte+4 = DESTINATION OUTPUT SLOT (index<<5): [[position]].xyzw = slots 0-3 (byte+4 0x00/0x20/0x40/0x60), user varyings at slots 4+ (0x80/0xa0/0xc0/0xe0). ONE op per scalar component. Position-vs-varying is the SLOT RANGE, not a distinct opcode. Mesh/object stages emit via the 0xe7 device store (EXP-0030); 0x57 is the traditional-VS path.*

## Atomics

### `atomic_rmw` — device atomic RMW (elected-lane, op at byte+12)

- **Length:** 14 bytes  ·  **Match:** byte+0==0x67, byte+1==0x11  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b2` | [16:24] (byte+2) | raw/unmapped |  |
| `b3` | [24:32] (byte+3) | raw/unmapped |  |
| `base_slot` | [32:40] (byte+4) | immediate |  |
| `mid` | [40:96] (byte+5) | raw/unmapped |  |
| `op` | [96:104] (byte+12) | opcode-select | `0x20`=add; `0x36`=sub; `0x22`=and; `0x2c`=or; `0x3e`=xor; `0x28`=smax; `0x2a`=smin; `0x38`=umax; `0x3a`=umin; `0x26`=fadd |
| `b13` | [104:112] (byte+13) | raw/unmapped |  |

*atomic read-modify-write to buffer[base_slot] (byte+4, same slot model as loads). Operation at byte+12: 0x20 add 0x36 sub 0x22 and 0x2c or 0x3e xor 0x28 smax 0x2a smin 0x38 umax 0x3a umin 0x26 fadd (float add). This is the single native RMW the compiler emits AFTER a SIMD-group simd_reduce pre-combines the per-lane operands and elects one lane (simd_is_first via 0f05/0f06 mask). NOT a CAS/retry loop. Device address space (byte+1 bit1=0).*

### `atomic_mem` — standalone atomic (exchange/cmpxchg/indexed)

- **Length:** 14 bytes  ·  **Match:** byte+0==0x67, byte+1==0x01  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b2` | [16:24] (byte+2) | raw/unmapped |  |
| `b3` | [24:32] (byte+3) | raw/unmapped |  |
| `base_slot` | [32:40] (byte+4) | immediate |  |
| `mid` | [40:96] (byte+5) | raw/unmapped |  |
| `op` | [96:104] (byte+12) | opcode-select | `0x3c`=exchange; `0x24`=cmpxchg; `0x60`=add_indexed |
| `b13` | [104:112] (byte+13) | raw/unmapped |  |

*standalone atomic memory op (single native instruction, no retry loop). byte+12: 0x3c exchange (also atomic_store, which discards the result), 0x24 compare-exchange (the returned old value feeds a following icmp that computes the weak-cmpxchg bool; NO hardware retry loop), 0x60 = per-lane indexed atomic add. Device space (byte+1 bit1=0); threadgroup sets the byte+1 threadgroup bit (0x02), base_slot 0x08 -- same address-space model as EXP-0012 memory ops.*

## Texture / sampler

### `tex_sample` — sample/gather/read/compare/LOD-query bundle

- **Length:** 14 bytes  ·  **Match:** bits[0:3]==0x5, byte+1==0x80, byte+2==0x0c  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `kind` | [0:4] (byte+0) | modifier |  |
| `chain` | [4:8] | modifier |  |
| `result_desc` | [24:32] (byte+3) | modifier | `0xb8`=vec4 (full sample/read 0xb8); `0xa0`=scalar/compare/clamped-LOD (0xa0); `0xa8`=unclamped-LOD (0xa8); `0xa4`=gather comp0=r (0xa4); `0xac`=gather comp1=g (0xac); `0xb4`=gather comp2=b (0xb4); `0xbc`=gather comp3=a (0xbc) |
| `result_sel` | [32:40] (byte+4) | register |  |
| `coord` | [40:48] (byte+5) | register |  |
| `variant` | [48:56] (byte+6) | opcode-select | `0x0`=sample|gather; `0x1`=sample|gather+offset; `0x4`=sample_grad; `0x7`=sample_bias; `0x9`=sample_lod|array-sample; `0x13`=cube sample; `0x17`=read 2D; `0x1b`=sample_lod+offset; `0x20`=sample_compare|gather_compare; `0x21`=sample_compare+offset; `0x29`=sample_compare level; `0x39`=3D sample; `0x3b`=sample_compare_lod+offset; `0x53`=cube-array sample; `0x79`=read 3D; `0x80`=read MSAA; `0x97`=read 2D-array (bit7=array) |
| `extra_coord` | [56:64] (byte+7) | register |  |
| `tex_slot` | [64:72] (byte+8) | immediate |  |
| `samp_slot_offset` | [72:80] (byte+9) | immediate |  |
| `mode` | [80:88] (byte+10) | modifier | `0x10`=filtered sample; `0x0`=gather/read/sample_compare; `0x20`=LOD query |
| `lod_present` | [88:96] (byte+11) | modifier |  |
| `tail` | [96:112] (byte+12) | raw/unmapped |  |

*Texture sample/gather/read/compare/LOD-query bundle: a 4-byte companion (low-nibble 5 sample/gather/read, 0xd compute sample_compare) + a 10-byte sampler op. variant (op+2) selects operation/dimension/LOD-mode; op+2 bit5(0x20)=DEPTH-COMPARE (compareValue CMP sampledDepth; all 8 compareFuncs HW-validated; linear filter => native 2x2 hardware PCF), bit0(0x01)=const texel offset present. companion byte+3 = result descriptor: bit2(0x04)=GATHER, bits[3:5]=gather component r/g/b/a. op+6 = mode (0x10 filtered / 0x00 gather/read/compare / 0x20 LOD-query). tex_slot=op+4 (bit7=index bit), sampler slot + const offset in op+5. LOD/bias/grad and the depth-compare reference are register operands set up by preceding ALU. Same op in compute and fragment; implicit LOD needs a fragment stage.*

### `tex_write` — texture write (memory-family store)

- **Length:** 16 bytes  ·  **Match:** byte+0==0xd7  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | raw/unmapped |  |
| `b2` | [16:24] (byte+2) | raw/unmapped |  |
| `data` | [24:40] (byte+3) | register |  |
| `body` | [40:128] (byte+5) | raw/unmapped |  |

*texture[slot].write(color, coord). Memory-family store (byte0 0xd7, low-nibble 7, sibling of the 0x67/0xe7 buffer load/store). Distinct from the sampler-path read: writes go through the store path, reads through the sample op (variant 0x17). Fragment or compute.*

### `tex_deriv` — quad-difference derivative (dfdx/dfdy/fwidth)

- **Length:** 10 bytes  ·  **Match:** byte+0==0x37  ·  **Provenance:** inferred

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | raw/unmapped |  |
| `dstsrc` | [16:40] (byte+2) | raw/unmapped |  |
| `src_comp` | [40:48] (byte+5) | raw/unmapped |  |
| `axis` | [48:56] (byte+6) | enum | `0x92`=dfdx; `0x90`=dfdy |
| `tail` | [56:80] (byte+7) | raw/unmapped |  |

*d = quad-difference derivative of a source varying (dfdx/dfdy/fwidth). byte0 0x37, 10 bytes; axis at byte+6 (0x92 = dfdx / X, 0x90 = dfdy / Y). Fragment-only (needs 2x2 quad helper lanes). Co-occurs with implicit-LOD sampling, which computes LOD from these derivatives internally (an explicit 0x37 is emitted only for source-level dfdx/dfdy/fwidth). Full fine/coarse decode is a follow-up.*

### `tex_coord_setup` — texture coordinate / LOD / gather-offset setup ALU

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0xb, byte+2==0x2f  ·  **Provenance:** inferred

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b0hi` | [4:8] | raw/unmapped |  |
| `b1` | [8:16] (byte+1) | raw/unmapped |  |
| `subop` | [16:24] (byte+2) | opcode-select | `0x27`=coord/LOD; `0x2f`=coord/interp |
| `b3` | [24:32] (byte+3) | raw/unmapped |  |
| `mark` | [32:40] (byte+4) | raw/unmapped |  |
| `body` | [40:80] (byte+5) | raw/unmapped |  |

*texture COORDINATE / LOD / gather-offset SETUP ALU (byte0 low-nibble 0x0b, 10 bytes, byte+2 in {0x27,0x2f}, tail `.. 00 42 00 00 0X 00 00`). Computes the texel address / normalized cube-face-or-array coordinate / explicit-LOD or bias / const gather offset that the following tex_sample (0xb0/0x90) sampler op consumes as its coordinate/LOD register operands. Emitted 1..N per sample. (The 0x27 byte+2 form gets the same length but is not separately named here; the descriptor matches the 0x2f coord/interp form.)*

### `coord_madf` — coordinate / interpolation fused mul-add (leader form)

- **Length:** 10 bytes  ·  **Match:** byte+0==0x2e, byte+2==0x23  ·  **Provenance:** inferred

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | raw/unmapped |  |
| `op` | [16:24] (byte+2) | raw/unmapped |  |
| `srcA` | [24:32] (byte+3) | register |  |
| `mark` | [32:40] (byte+4) | raw/unmapped |  |
| `body` | [40:80] (byte+5) | raw/unmapped |  |

*coordinate / interpolation fused multiply-add ALU, byte0 LEADER form 0x2e (sibling 0x3e), 10 bytes: `2e/3e b1 23 a0 42 00 00 06 02 00`. Appears in the texture coordinate-generation path (cube/array/3D normalized-coordinate math) and, as a byte+2 OP-SELECT (0x26/0x2e) of the low-nibble-9 float group, in the vertex matrix-vector product -- a general fused mul/mul-add, not texture-specific. This descriptor covers ONLY the byte0-LEADER 0x2e form (gated on byte+2==0x23); the far more common op-select case is a 0x09 float op handled by the float-ALU op-select length rule, NOT here.*

## Control flow / function ABI

### `icmp_pred` — integer compare -> execution predicate

- **Length:** 6 bytes  ·  **Match:** byte+0==0x0a  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `sub` | [8:24] (byte+1) | raw/unmapped |  |
| `imm` | [24:32] (byte+3) | immediate |  |
| `tail` | [32:48] (byte+4) | raw/unmapped |  |

*predicate = (srcA cond imm/srcB) ; integer compare that sets the per-lane execution mask for a predicated block (early return / break / continue). Compare bound at byte+3; condition sense in byte0/byte+1 (0x0a<->0x02 inverts).*

### `sel` — conditional select (data operands)

- **Length:** 4 bytes  ·  **Match:** byte+0==0x16  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `body` | [8:32] (byte+1) | raw/unmapped |  |

*d = pred ? A : B  ; branchless conditional select (data operands).*

### `psel` — conditional select (grid/immediate variant)

- **Length:** 4 bytes  ·  **Match:** byte+0==0x05  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `body` | [8:32] (byte+1) | raw/unmapped |  |

*d = pred ? A : B  ; branchless conditional select (variant used for grid-position ternaries).*

### `jump` — PC-relative jump (loop back-edge)

- **Length:** 10 bytes  ·  **Match:** byte+0==0x0f, byte+1==0x00  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `mid` | [16:24] (byte+2) | raw/unmapped |  |
| `offset` | [24:72] (byte+3) | immediate |  |
| `tail` | [72:80] (byte+9) | raw/unmapped |  |

*PC-relative jump; offset is a signed 48-bit little-endian byte displacement (backward for loop back-edges). Taken while lanes remain active (execution-mask loop).*

### `frame_marker` — call-site / frame-setup marker (before every CALL)

- **Length:** 4 bytes  ·  **Match:** byte+0==0x43  ·  **Provenance:** inferred

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | raw/unmapped |  |
| `b2` | [16:24] (byte+2) | raw/unmapped |  |
| `b3` | [24:32] (byte+3) | raw/unmapped |  |

*call-site / frame-setup marker (byte0 0x43, 4 bytes). `43 00 00 01` is emitted immediately before every out-of-line CALL; `43 00 06 xx` is the non-leaf-frame prologue. In object/mesh stages it marks the compiler-generated helper-subroutine calls (write_childcount / write_uvb) -- NOT a mesh-emit op (set_vertex/index/primitive lower to ordinary 0xe7/0xd7 stores, EXP-0030).*

### `call` — direct out-of-line CALL

- **Length:** 14 bytes  ·  **Match:** byte+0==0x0f, byte+1==0x05, byte+2==0x54, byte+4==0x8f  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b3` | [24:32] (byte+3) | raw/unmapped |  |
| `b5` | [40:48] (byte+5) | raw/unmapped |  |
| `b6` | [48:56] (byte+6) | raw/unmapped |  |
| `offset` | [56:104] (byte+7) | immediate |  |
| `tail` | [104:112] (byte+13) | raw/unmapped |  |

*direct out-of-line CALL: `0f 05 54 1a 8f 00 56 <off40> 00` (14 B). offset = a SIGNED little-endian PC-relative byte displacement; branch target = (call_addr + 4) + offset. Reuses the execution-mask push (0f 05) machinery -- a masked branch that saves the return context -- so byte+4=0x8f and byte+6=0x56 are the CALL/link signature (also the 14-vs-8-byte disambiguator vs a plain predication push). Bracketed by the 0x43 frame marker (before) and a 0f 06 reconverge (after). Args in r10,r11,r12..; return value in r10; return via ret (0x8f).*

### `ret` — function RETURN (leaf / non-leaf)

- **Length:** 4 bytes  ·  **Match:** byte+0==0x8f, byte+2==0x54  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `linkmode` | [8:16] (byte+1) | enum | `0x2`=leaf; `0x12`=nonleaf_restore_link |
| `tail` | [24:32] (byte+3) | raw/unmapped |  |

*function RETURN: `8f <lm> 54 00` (4 B). byte0 0x8f = control-flow family (low nibble 0xf) with the link/return high bit; byte+2 0x54 = CF marker. linkmode byte+1 = 0x02 (LEAF callee: return address from the hardware link register) or 0x12 (NON-leaf: restores its own spilled return address around inner calls). NO target field -- the return address is a hardware link register / CF (reconvergence) stack.*

### `call_indirect` — indirect CALL (visible_function_table)

- **Length:** 6 bytes  ·  **Match:** byte+0==0x0f, byte+1==0x80  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b2` | [16:24] (byte+2) | raw/unmapped |  |
| `target_lo` | [24:32] (byte+3) | raw/unmapped |  |
| `b4` | [32:40] (byte+4) | raw/unmapped |  |
| `b5` | [40:48] (byte+5) | raw/unmapped |  |

*INDIRECT CALL through a function pointer (visible_function_table / intersection_function_table). Leader `0f 80 ..`: byte+1 0x80 selects the call-to-address variant of the control-flow group (vs 0x00 jump, 0x05 direct call). The target is a CODE VA loaded into a register from the function table (entry[i] = 8-byte code VA of function i's entry point); this op transfers control to it and returns via the same ret (0x8f). Per-lane (dynamic) targets are marshalled through a run of 0x4b move ops before the 0f 80.*

### `frame_prologue` — non-leaf function frame prologue (scratch frame setup)

- **Length:** 6 bytes  ·  **Match:** byte+0==0x6f  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `subop` | [8:16] (byte+1) | raw/unmapped |  |
| `marker` | [16:24] (byte+2) | raw/unmapped |  |
| `b3` | [24:32] (byte+3) | raw/unmapped |  |
| `b4` | [32:40] (byte+4) | raw/unmapped |  |
| `frame_size` | [40:48] (byte+5) | immediate |  |

*NON-LEAF FUNCTION FRAME PROLOGUE. `6f 03 04 00 00 20` (6 bytes; the broader corpus also shows `6f 03 54 00 00 10`). Emitted at the entry of a NON-leaf callee (one that itself CALLs) to establish the per-thread SCRATCH frame in which it saves/restores its return/link register around each inner call. Leaf callees have no prologue and return via `8f 02 54 00`; a non-leaf callee has this prologue, brackets each nested CALL with the 8-byte 0x07 link save/restore, and returns via `8f 12 54 00`. byte+1==0x03 = frame sub-op; byte+2 = 0x04/0x54 marker; byte+5 = candidate frame/scratch-size field (INFERRED).*

### `link_save_restore` — link-register save/restore around a nested call

- **Length:** 8 bytes  ·  **Match:** byte+0==0x07, byte+1==0x00, byte+2==0x54, byte+4==0x81  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | raw/unmapped |  |
| `marker` | [16:24] (byte+2) | raw/unmapped |  |
| `b3` | [24:32] (byte+3) | raw/unmapped |  |
| `scope` | [32:40] (byte+4) | raw/unmapped |  |
| `dir_offset` | [40:64] (byte+5) | raw/unmapped |  |

*LINK-REGISTER SAVE / RESTORE around a nested call in a non-leaf frame. save (before each CALL) = `07 00 54 00 81 00 00 00`; restore (after each CALL) = `07 00 54 00 81 ff 1f 00` (8 bytes). Same 0x07 fence/ordering family as the compute threadgroup_barrier (EXP-0025) and fragment pixel_order (EXP-0029), but an 8-byte form gated by byte+1==0x00 (the barrier/pixel-order forms are 6 bytes, byte+1 in {0x04,0x14}). byte+4==0x81 = scratch/stack scope; byte+5..+7 discriminate SAVE (00 00 00) from RESTORE (ff 1f 00, a scratch offset). A non-leaf callee spills its own link register because each inner CALL clobbers the hardware link register (ret 0x8f encodes no return target).*

## SIMD-group / quad

### `simd_reduce` — SIMD/quad reduce & prefix-scan

- **Length:** 8 bytes  ·  **Match:** bits[0:3]==0x7, bits[4:6]==0x3, bits[16:17]==0x0, bits[18:24]==0x15  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `scope` | [3:4] | enum | `0x1`=simd; `0x0`=quad |
| `b0hi` | [6:7] | raw/unmapped |  |
| `opcls` | [7:8] | modifier |  |
| `cache` | [17:18] | modifier |  |
| `op` | [8:16] (byte+1) | opcode-select | `0x0`=or/and; `0x1`=add/xor; `0x3`=?/umax; `0x5`=?/fmin; `0x6`=fadd/fmul(product); `0x7`=?/fmax; `0x2`=max/min |
| `b3` | [24:32] (byte+3) | raw/unmapped |  |
| `src` | [32:40] (byte+4) | register |  |
| `b5` | [40:48] (byte+5) | raw/unmapped |  |
| `shape` | [48:56] (byte+6) | modifier |  |
| `dtype` | [56:64] (byte+7) | enum | `0x3`=i_reduce; `0x7`=i_minmax; `0x12`=f_reduce; `0xb`=i_excl_scan; `0x9`=i_incl_scan; `0x32`=f_excl_scan; `0x22`=f_scan_variant |

*d = simd/quad reduce or prefix-scan of src over the SIMD-group (scope=1, width 32) or 2x2 quad (scope=0). Operation = (byte0 bit7, byte+1): byte+1=0x00 {and(bit7=0), or(1)}; 0x01 {xor(0), add/iadd(1)}; 0x03 {?, umax(1)}; 0x05 {?, fmin(1)}; 0x06 {FADD/simd_sum(0), FMUL/simd_product(1) -- NEW EXP-O2D, HW-splice byte0 0xbf->0x3f flips product 1.0 -> sum 32.0}; 0x07 {?, fmax(1)}; 0x02 {max/min}. byte+7 = datatype/shape: 0x03 int add|and|or|xor reduce, 0x07 int min|max, 0x12 float reduce, 0x0b int exclusive-scan, 0x09 int inclusive-scan, 0x32 FLOAT exclusive-scan (NEW), float inclusive-scan = the exclusive-scan followed by a 0x09 float op of the lane's own value. NB INTEGER simd_product / prefix-product have NO native reduce op -- they LOWER to a log2(32)-step shuffle(0x47)+multiply(0x9f) tree (only FLOAT product/prefix-product use this native op; the reduce unit has a float-mul mode but no int-mul mode).*

### `simd_shuffle` — SIMD/quad shuffle / broadcast

- **Length:** 10 bytes  ·  **Match:** bits[0:7]==0x47, byte+2==0x56  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dir` | [7:8] | enum | `0x0`=bcast/up; `0x1`=xor/down |
| `mode` | [8:16] (byte+1) | enum | `0x4`=simd; `0x0`=quad; `0x6`=rotate/fill |
| `b3` | [24:32] (byte+3) | raw/unmapped |  |
| `src` | [32:40] (byte+4) | register |  |
| `b5` | [40:48] (byte+5) | raw/unmapped |  |
| `lane` | [48:56] (byte+6) | immediate |  |
| `tail` | [56:80] (byte+7) | raw/unmapped |  |

*d = src from another lane. byte0 0x47 = broadcast / shuffle-up / fill_up, 0xc7 = shuffle-xor / shuffle-down / fill_down (bit7 = direction). byte+1 mode: 0x04 SIMD-group shuffle, 0x00 quad, 0x06 rotate / shuffle_and_fill (NEW EXP-O2D). byte+6 = source lane index (broadcast) or xor mask (shuffle_xor), encoded (value<<1). simd_broadcast_first & dynamic simd_shuffle(v,lane) use the same op with the lane index in a register. NEW (EXP-O2D): simd_shuffle_and_fill_up/down = byte+1==0x06; the FILL DATA is a SEPARATE operand loaded by a preceding 0x67 device_load before the shuffle. The modulo/rotate variant (v, fill, delta, modulo) is the same byte+1==0x06 op with byte+6 changed (fill 0x4a -> modulo 0x42) plus a tail byte (0x20 -> 0x30) carrying the modulo. simd_shuffle_up/down add edge-handling predication (0f80/0f9e) around the core op; simd_shuffle_xor is a single clean op.*

### `simd_ballot` — SIMD ballot / vote mask source

- **Length:** 10 bytes  ·  **Match:** byte+0==0x17, byte+1==0x07  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | raw/unmapped |  |
| `body` | [16:80] (byte+2) | raw/unmapped |  |

*produces the SIMD-group ballot / vote mask (per-lane boolean -> bitmask). simd_ballot(p) yields the 32-bit active-lane mask of the predicate; simd_active_threads_mask yields the active mask; simd_all/simd_any reduce it. SIMD width 32 -> low 32 bits are the mask (all-ones when all 32 active).*

## Matrix

### `matrix_mac` — 8x8 cooperative-matrix multiply-accumulate

- **Length:** 12 bytes  ·  **Match:** byte+0==0xcf  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dtype` | [8:16] (byte+1) | enum | `0x0`=f16(16-bit); `0x2`=f32/bf16(32-bit) |
| `mode` | [16:24] (byte+2) | enum | `0x56`=standalone; `0x54`=tiled/MPP |
| `a_desc` | [24:32] (byte+3) | raw/unmapped |  |
| `pad4` | [32:40] (byte+4) | raw/unmapped |  |
| `a_reg` | [40:48] (byte+5) | register |  |
| `b_reg` | [48:56] (byte+6) | register |  |
| `c_src` | [56:64] (byte+7) | register |  |
| `dst` | [64:72] (byte+8) | register |  |
| `dst_desc` | [72:80] (byte+9) | raw/unmapped |  |
| `op_enable` | [80:88] (byte+10) | opcode-select |  |
| `acc_en` | [88:89] (byte+11) | enum | `0x0`=multiply; `0x1`=multiply_accumulate |
| `b11hi` | [89:96] | raw/unmapped |  |

*d = a*b (+ c)  ; DEDICATED 8x8 cooperative-matrix multiply-accumulate over the 32-lane SIMD-group. One 0xcf = one full 8x8x8 tile MAC (r[i][j] += sum_k a[i][k]*b[k][j], row-major). OPERAND SELECTORS (all HW-splice-validated, EXP-O2C, on mad_f32 read back over one 32-lane simdgroup): byte+5 = A (LEFT) multiply-operand fragment register (splice +5 to B's reg -> B*B; swap +5/+6 -> B*A -- matmul is non-commutative so all A*B/B*A/A*A/B*B distinguishable); byte+6 = B (RIGHT) operand register; byte+7 = C accumulator source register; byte+8 = destination fragment register; byte+3 = an A-operand sub-descriptor (corrupting -> ZERO result: load-bearing); byte+10 = op-enable marker 0x24 (corrupting -> C passthrough, the multiply drops out); byte+4 and byte+9 bit1 splice-inert (padding). dtype (byte+1): 0x00 = 16-bit (half), 0x02 = 32-bit (float; bfloat shares the 32-bit datapath with input conversion; splicing 0x02->0x00 garbles fp32). mode (byte+2): 0x56 standalone, 0x54 tiled (MPP matmul2d) -- SEMANTIC, not a hint: splicing standalone 0x56->0x54 ZEROES the result (tiled mode sources its accumulator from the MPP tile context). ACCUMULATE-ENABLE = byte+11 bit0 (1 -> a*b+c, 0 -> a*b; simdgroup_multiply clears it). MSL element types: half, float, bfloat (incl. mixed half/bfloat -> float accumulate); integer matrices REJECTED (no int8 cooperative matrix). Only 8x8 exposed. ALL MPP tensor ops (matmul2d multiply/multiply_accumulate/transpose/f32/16x16x16/2-simdgroup) lower to THIS SAME op -- no new tensor opcode; transpose adds 4-byte data-move ops (ray_move family), not a new op; simdgroup_load/store (incl. transpose=true) are ordinary 0x67/0xe7 memory ops.*

## Ray tracing

### `rt_intersect` — dedicated ray-intersection primitive (motion + AS-select)

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x4, byte+1==0xea  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `subop` | [8:16] (byte+1) | opcode-select | `0xea`=trace |
| `mode` | [16:24] (byte+2) | enum | `0x10`=dyn_origin/motion; `0x90`=const_origin; `0xd0`=const_origin+fntable; `0x11`=result_read |
| `ray_param` | [24:32] (byte+3) | register |  |
| `as_type` | [32:40] (byte+4) | enum | `0x8b`=primitive_AS; `0x1b`=instance_AS; `0xbb`=primitive_motion_AS |
| `b5` | [40:48] (byte+5) | raw/unmapped |  |
| `flags` | [48:56] (byte+6) | modifier |  |
| `b7` | [56:64] (byte+7) | raw/unmapped |  |

*DEDICATED ray-intersection instruction (the raytracing:: intersect primitive). byte0 low-nibble 0x4 = group; byte0 HIGH nibble = result/destination register; byte+1 == 0xea = intersect sub-opcode (constant). byte+2 = mode: 0x90 const origin, 0x10 dynamic-origin OR primitive-MOTION (the time-parameterised form -- motion sets 0x10 even with a const origin), 0xd0 const-origin + intersection-function-table present (bit7=const-origin, bit6=fn-table), 0x11 result-read. byte+3 = ray/parameter operand register, and also carries the MOTION TIME (device-loaded time 0x46 vs folded-constant 0x26). byte+4 = AS-type selector: 0x8b primitive AS, 0x1b instance AS, 0xbb primitive-MOTION AS (HW-validated end-to-end: motion-AS trace interpolates the hit distance LINEARLY with the time parameter). byte+6 bit7 set when an intersection_function_table is bound. Emitted twice: op#1 traverse, op#2 (byte+2 0x10/0x11, trailing `26 9f`) result-read. The BVH TRAVERSAL itself is a compiler-generated shader loop (one -88-byte back-edge per intersector) using this op + the 0xdf AS-loads + the 0x5f ray-data ops -- NOT a fire-and-forget trace. PRIMITIVE TAG does not change the op (bounding_box op#1 == triangle op#1 byte-for-byte; curve differs only in the dst-reg nibble): tag discrimination lives in the AS + intersection-function-table. Works IDENTICALLY from a FRAGMENT shader (supportsRaytracingFromRender, HW-validated) -- only the bind stage differs.*

### `rt_as_load` — acceleration-structure / ray-data load

- **Length:** 14 bytes  ·  **Match:** byte+0==0xdf  ·  **Provenance:** inferred

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | raw/unmapped |  |
| `mode` | [16:24] (byte+2) | raw/unmapped |  |
| `body` | [24:112] (byte+3) | raw/unmapped |  |

*Dedicated acceleration-structure / ray-data load used during BVH traversal (byte0 0xdf, a memory-family sibling of the 0x67/0xe7 buffer load/store: byte+2 == 0x54 like the memory ops). Fetches BVH node / ray / traversal-stack data. 14-17 per intersector kernel, ~37 in an inline intersection_query. Field bit-packing inferred (byte-diff); not individually splice-validated.*

### `rt_ray_mem` — ray-data / traversal-stack memory op (payload copy-in/out)

- **Length:** 14 bytes  ·  **Match:** byte+0==0x5f, byte+2==0x54  ·  **Provenance:** inferred

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `subop` | [8:16] (byte+1) | opcode-select |  |
| `marker` | [16:24] (byte+2) | raw/unmapped |  |
| `body` | [24:112] (byte+3) | raw/unmapped |  |

*RAY-TRACING ray-data / traversal-stack memory op. byte0 0x5f (low-nibble 0xf, the memory-family low nibble, sibling of the 0xdf AS-load and the 0x67/0xe7 buffer load/store), byte+2 == 0x54 (memory-op marker). The store/spill-side companion of the 0xdf AS-data load: fetches/spills the ray struct + per-node BVH traversal-stack state during the (software) traversal loop, and carries the ray_data PAYLOAD copy-in/out for custom intersection functions (its count scales with payload size: float2 -> 13, 8-float -> 15, no payload -> 12; instance-motion -> 28). byte+1 = sub-op / addressing form (0x00/0x02/0x10/0x11; 0x10/0x11 mirror the 0x67 load space+index byte). Confirms ray_data is a distinct address space backed by RT scratch (RT kernels emit zero threadgroup ops and only one device store = the output).*

### `rt_transform_test` — ray-vs-node transform / AABB box-test companion

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0x2, byte+2==0x27, byte+3==0x81, byte+4==0x22  ·  **Provenance:** inferred

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `src` | [8:16] (byte+1) | register |  |
| `marker` | [16:24] (byte+2) | raw/unmapped |  |
| `b3` | [24:32] (byte+3) | raw/unmapped |  |
| `cmpmode` | [32:40] (byte+4) | raw/unmapped |  |
| `body` | [40:80] (byte+5) | raw/unmapped |  |

*RAY-TRACING transform / box-test companion op. byte0 low-nibble 0x2 (high nibble = dst reg), byte+2 == 0x27 (marker), byte+3 == 0x81, byte+4 == 0x22 (an ordered-compare-like mode). ~4-5 per intersector kernel; the ray-vs-node coordinate transform / AABB slab-test arithmetic executed inside the (software) traversal loop, distinct from the dedicated rt_intersect primitive. Gate on byte+2 == 0x27 to distinguish from the other low-nibble-2 ops (0x02 iminmax byte+2 0x1e, 0x12 icmpsel, 0x32 carry-gen byte+2 0x35). In motion kernels the tail differs (time-blended transform).*

### `ray_move` — ray register-marshalling move (also MPP matmul transpose)

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0xb, byte+2==0x81  ·  **Provenance:** inferred

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `src` | [8:16] (byte+1) | register |  |
| `form` | [16:24] (byte+2) | enum | `0x81`=copy_reg(b3=0x08); `0x80`=zero_init(b3=0x00) |
| `b3` | [24:32] (byte+3) | raw/unmapped |  |

*RAY register-marshalling MOVE (4 bytes). byte0 low-nibble 0xb, HIGH nibble = destination register; byte+1 = source register. Marshals the ray fields (origin.xyz / direction.xyz / min_distance / max_distance, and the ray_data payload) into the contiguous register block the rt_intersect op consumes, and moves results out. byte+2 == 0x81 (byte+3 == 0x08) = copy a computed source register; byte+2 == 0x80 (byte+1 == 0x00, byte+3 == 0x00) = zero-initialise a component (e.g. a const origin float3(0,0,0)). A compact move in the 0xNb family (sibling of the compact call-argument move / uniform_mov); disambiguated by byte+2 in {0x80,0x81}. The SAME op is reused (35-38 per kernel) to marshal MPP matmul2d TRANSPOSE tile data -- i.e. matrix transpose is data movement, not a matrix opcode.*

## Barrier / ordering

### `threadgroup_barrier` — threadgroup execution barrier + memory fence

- **Length:** 6 bytes  ·  **Match:** byte+0==0x07, byte+2==0x54  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `sub` | [8:16] (byte+1) | raw/unmapped |  |
| `mem_scope` | [24:32] (byte+3) | enum | `0x61`=threadgroup; `0x85`=device |
| `flags` | [32:40] (byte+4) | modifier |  |
| `b5` | [40:48] (byte+5) | raw/unmapped |  |

*threadgroup_barrier(mem_flags) -- execution barrier + memory fence. 6 bytes: 07 04 54 <mem_scope> <flags> 00. byte+3 = fenced memory scope: 0x61 = threadgroup (mem_threadgroup), 0x85 = device (mem_device). Makes threadgroup-memory stores by OTHER lanes visible before the barrier returns; the compiler emits it between a threadgroup store and a cross-lane threadgroup load. It is the ONLY explicit ordering/'wait' op in the compute stream (device load/store/atomic/texture are HW-register-interlocked, not scoreboard-waited). simdgroup_barrier emits no 0x07 op (a 32-lane SIMD-group is lockstep). Removing/neutralising the fence -> silent stale threadgroup reads (no fault).*

### `mem_fence` — device memory fence (atomic_thread_fence, no execution barrier)

- **Length:** 6 bytes  ·  **Match:** byte+0==0x07, byte+2==0x54, byte+3==0x84  ·  **Provenance:** inferred

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `sub` | [8:16] (byte+1) | raw/unmapped |  |
| `memclass` | [32:40] (byte+4) | modifier |  |
| `b5` | [40:48] (byte+5) | raw/unmapped |  |

*atomic_thread_fence(mem_flags::mem_device, memory_order_seq_cst[, thread_scope_device]) -- a standalone DEVICE-memory ordering fence with no execution barrier. 6 bytes: 07 04 54 84 0a 00. byte+3 == 0x84 = device-memory fence (vs threadgroup_barrier's 0x85 device = 0x84|0x01, the 0x01 being the added EXECUTION barrier); byte+4 == 0x0a = device memory-class flag. Ordering is realised by fence PRESENCE, not a bit on the 0x67 atomic RMW op: memory_order_relaxed emits NO fence, seq_cst emits this fence (acquire/release/acq_rel are REJECTED by MSL). Scope GATES emission: thread/simdgroup/threadgroup scope emit no device fence; thread_scope_device (default) does. The texture fence (mem_texture) is a byte+4==0x06 pair that decodes as pixel_order (same family).*

### `pixel_order` — raster-order-group wait/signal (fragment)

- **Length:** 6 bytes  ·  **Match:** byte+0==0x07, byte+2==0x54, byte+4==0x06  ·  **Provenance:** inferred

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `kind` | [8:16] (byte+1) | enum | `0x14`=acquire/wait; `0x4`=release/signal |
| `scope` | [24:32] (byte+3) | raw/unmapped |  |
| `flags` | [32:40] (byte+4) | raw/unmapped |  |
| `b5` | [40:48] (byte+5) | raw/unmapped |  |

*fragment PIXEL-ORDERING op (raster_order_group / fragment-shader-interlock; the wait_pix/signal_pix analogue). Same 0x07 memory-fence family as the compute threadgroup_barrier (EXP-0025), but with byte+4==0x06 (the raster-order/device fence flag) and byte+1 = 0x14 acquire (wait for prior overlapping fragments) / 0x04 release (signal this fragment done). Brackets the ordered read-modify-write of a [[raster_order_group]] resource so overlapping fragments serialise. There is NO dedicated one-shot pixel wait/signal opcode — ordering is these fence ops.*

## Fragment stage

### `iter` — varying interpolation (perspective/linear/W)

- **Length:** 10 bytes  ·  **Match:** bits[0:7]==0x2f, byte+2==0x54, byte+7==0x02  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `grp` | [0:8] (byte+0) | raw/unmapped |  |
| `lead` | [8:16] (byte+1) | raw/unmapped |  |
| `dst` | [24:32] (byte+3) | register |  |
| `c4` | [32:40] (byte+4) | raw/unmapped |  |
| `src_slot` | [40:48] (byte+5) | immediate |  |
| `mode` | [48:56] (byte+6) | enum | `0x0`=center/linear; `0x2`=centroid/sample; `0x4`=perspective-denominator(W) |
| `c7` | [56:64] (byte+7) | raw/unmapped |  |
| `tail` | [64:80] (byte+8) | raw/unmapped |  |

*r_dst = interpolate(varying_slot=src_slot, mode)  ; per-fragment varying interpolation ('iter'). One op per float4 component. byte+5 = the per-triangle varying/coefficient slot (slot<<1); byte+3 = destination GPR; byte+6 = interpolation location: 0x00 pixel-centre/linear, 0x02 centroid or per-sample (paired with the 8-byte iter_at setup + a 0x04/0x03 position preamble), 0x04 the perspective denominator (W) channel. PERSPECTIVE-CORRECT interpolation is a multi-instruction lowering, NOT a single mode bit: linear component iters (byte+6==0x00) + a W-denominator iter (byte+6==0x04) + a 0xaf reciprocal (rcp of interpolated 1/w) + a per-component fmul. [[flat]] uses the separate 6-byte iter_flat op instead (no barycentric interp). The pull-model interpolate_at_center/centroid/sample compile BYTE-IDENTICALLY to the matching [[*_perspective]] qualifier.*

### `iter_at` — interpolate-at setup (centroid / sample)

- **Length:** 8 bytes  ·  **Match:** bits[0:7]==0x2f, byte+2==0x54, byte+6==0x0a  ·  **Provenance:** inferred

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `grp` | [0:8] (byte+0) | raw/unmapped |  |
| `lead` | [8:16] (byte+1) | raw/unmapped |  |
| `dst` | [24:32] (byte+3) | register |  |
| `c4` | [32:40] (byte+4) | raw/unmapped |  |
| `b5` | [40:48] (byte+5) | raw/unmapped |  |
| `loc` | [56:64] (byte+7) | enum | `0x1`=centroid; `0x3`=sample |

*interpolate-at SETUP: computes the custom barycentric coordinate for centroid / per-sample / interpolate_at_* interpolation, consumed by the following iter ops (which carry byte+6==0x02). byte+7 = 0x01 centroid, 0x03 sample. Preceded by a sample/centroid-position preamble read (byte0 0x04 centroid / 0x03 sample).*

### `iter_flat` — flat varying load (provoking-vertex attribute)

- **Length:** 6 bytes  ·  **Match:** byte+0==0x1f, byte+2==0x54  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | raw/unmapped |  |
| `sel` | [24:32] (byte+3) | raw/unmapped |  |
| `b4` | [32:40] (byte+4) | raw/unmapped |  |
| `b5` | [40:48] (byte+5) | raw/unmapped |  |

*flat varying load: reads the provoking-vertex attribute directly (NO barycentric interpolation), one 6-byte op per component. Emitted for [[flat]] (nointerpolation). Distinct byte0 (0x1f) and length from the 10-byte perspective/linear iter op.*

### `frag_color_store` — colour output store to tilebuffer

- **Length:** 12 bytes  ·  **Match:** byte+0==0xe7, byte+1==0x06  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b2` | [16:24] (byte+2) | raw/unmapped |  |
| `src` | [24:32] (byte+3) | register |  |
| `b4` | [32:40] (byte+4) | raw/unmapped |  |
| `rt_index` | [40:48] (byte+5) | immediate |  |
| `b6` | [48:56] (byte+6) | raw/unmapped |  |
| `b7` | [56:64] (byte+7) | raw/unmapped |  |
| `tail` | [64:96] (byte+8) | raw/unmapped |  |

*store a fragment colour output to the tilebuffer / colour attachment. Memory-family store (byte0 0xe7) with the FRAGMENT variant byte+1==0x06 (compute device store is byte+1==0x00, 14 bytes). byte+3 = source colour GPR, byte+5 = render-target index (rt<<1): RT0=0x00, RT1=0x02, RT2=0x04. Each RT store is bracketed by 0x87 tile-access setup ops. The colour values are packed into GPRs by preceding 0x97 ops. discard_fragment suppresses the store (killed fragments write nothing).*

### `frag_color_pack` — pack/move colour into output GPR

- **Length:** 10 bytes  ·  **Match:** byte+0==0x97  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | raw/unmapped |  |
| `b2` | [16:24] (byte+2) | raw/unmapped |  |
| `dst` | [24:32] (byte+3) | register |  |
| `b4` | [32:40] (byte+4) | raw/unmapped |  |
| `b5` | [40:48] (byte+5) | raw/unmapped |  |
| `val` | [48:56] (byte+6) | immediate |  |
| `tail` | [56:80] (byte+7) | raw/unmapped |  |

*pack / move a colour value into an output GPR ahead of the tilebuffer store (converts the shader's float/half output to the attachment format). byte+6 carries a colour component value.*

### `frag_tile_setup` — tile / render-target access setup

- **Length:** 6 bytes  ·  **Match:** byte+0==0x87, byte+2==0x54  ·  **Provenance:** inferred

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | raw/unmapped |  |
| `sel` | [24:32] (byte+3) | raw/unmapped |  |
| `b4` | [32:40] (byte+4) | raw/unmapped |  |
| `b5` | [40:48] (byte+5) | raw/unmapped |  |

*fragment tile / render-target access setup, emitted around each colour store and each tilebuffer read (and around raster-order-group ordered accesses). byte+3 = the per-RT / per-tile selector (0x0c/0x30/0xc0 for RT0/RT1/RT2 in out_mrt; 0x08 before a tile read).*

### `tile_read` — tilebuffer read (programmable blend input)

- **Length:** 12 bytes  ·  **Match:** byte+0==0x67, byte+1==0x0e  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b2` | [16:24] (byte+2) | raw/unmapped |  |
| `dst` | [24:32] (byte+3) | register |  |
| `b4` | [32:40] (byte+4) | raw/unmapped |  |
| `rt_index` | [40:48] (byte+5) | immediate |  |
| `b6` | [48:56] (byte+6) | raw/unmapped |  |
| `b7` | [56:64] (byte+7) | raw/unmapped |  |
| `tail` | [64:96] (byte+8) | raw/unmapped |  |

*read the CURRENT tilebuffer / colour-attachment value into a GPR — the ld_tile analogue for PROGRAMMABLE BLENDING (a fragment [[color(n)]] INPUT). Load-family op (byte0 0x67) with the fragment variant byte+1==0x0e (compute device load uses byte+1 in {0x10,0x00,0x11,...}). On Apple TBDR the framebuffer lives in tile memory, so blend is done in-shader (EXP-0019): the shader reads the destination colour with this op and computes the blend with ordinary float ALU, then stores with frag_color_store.*

### `imageblock_store` — explicit imageblock<T>.write (tile shader; byte-offset slice addressing)

- **Length:** 12 bytes  ·  **Match:** byte+0==0xe7, byte+1==0x16, byte+2==0x54  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `src` | [24:32] (byte+3) | register |  |
| `b4` | [32:40] (byte+4) | raw/unmapped |  |
| `slice_off` | [40:48] (byte+5) | immediate |  |
| `b6` | [48:56] (byte+6) | raw/unmapped |  |
| `fmt` | [56:64] (byte+7) | enum | `0xe`=half4/16b-slot; `0x22`=float/32b-slot |
| `tail` | [64:96] (byte+8) | raw/unmapped |  |

*imageblock[slice].write(v)  ; EXPLICIT imageblock<T> WRITE from a fragment or TILE (dispatchThreadsPerTile) shader. Memory-family store byte0 0xe7 with the tile variant byte+1==0x16 (0x16 = 0x06|0x10, the 0x10 bit marking the FIRST store after a 0x87 tile-access setup). Same op as frag_color_store, GENERALISED: byte+5 = SLICE ADDRESSING = the field's BYTE-OFFSET WITHIN THE IMAGEBLOCK STRUCT, encoded (offset>>1). HW-proven: a GB imageblock {half4 albedo@0, half4 normal@8, float depthv@16} stores with byte+5 = 0x00 / 0x04 / 0x08 (=0,8,16 >>1). byte+7 = slice data format (0x0e half4, 0x22 float). This DIFFERS from simple-MRT frag_color_store where byte+5 = render-target index (rt<<1): explicit imageblocks address by BYTE-OFFSET, MRT addresses by RT index. img.write(v) writes the WHOLE struct (one 0xe7 per field). Bracketed by 0x87 frag_tile_setup + a 0x07 tile fence.*

### `imageblock_load` — explicit imageblock<T>.read (tile shader; byte-offset slice addressing)

- **Length:** 12 bytes  ·  **Match:** byte+0==0x67, byte+1==0x16, byte+2==0x54  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [24:32] (byte+3) | register |  |
| `b4` | [32:40] (byte+4) | raw/unmapped |  |
| `slice_off` | [40:48] (byte+5) | immediate |  |
| `b6` | [48:56] (byte+6) | raw/unmapped |  |
| `fmt` | [56:64] (byte+7) | raw/unmapped |  |
| `tail` | [64:96] (byte+8) | raw/unmapped |  |

*v = imageblock[slice].read()  ; EXPLICIT imageblock<T> READ from a fragment/tile shader (the load-side sibling of imageblock_store; generalises tile_read's 0x67 byte+1==0x0e). byte0 0x67 load with the tile first-access variant byte+1==0x16; byte+5 = slice byte-offset>>1 (albedo 0x00 / normal 0x04 / depthv 0x08 for the GB imageblock). Used for programmable-blend tile reads and explicit imageblock read-modify-write.*

### `frag_depth_store` — [[depth]] output store

- **Length:** 6 bytes  ·  **Match:** byte+0==0xd7, byte+1==0x14, byte+2==0x54  ·  **Provenance:** inferred

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b3` | [24:32] (byte+3) | raw/unmapped |  |
| `b4` | [32:40] (byte+4) | raw/unmapped |  |
| `b5` | [40:48] (byte+5) | raw/unmapped |  |

*write the shader [[depth]] output to the tile depth buffer. Memory-family store (byte0 0xd7) with the fragment depth variant byte+1==0x14, byte+2==0x54, 6 bytes — distinct from the 16-byte texture write (also 0xd7). Bracketed by 0x87/0x07 tile-access ops whose byte+3==0x01 selects the depth attachment (vs 0x0c for colour RT0).*

## Length rule (byte 0)

Parcels are 2 bytes (all lengths even). Length is a function of byte 0 plus a per-group length bit/signature. The authoritative rule is `instr_length()` in `tools/agx-isa/isadb.py`; this table summarizes it:

| byte 0 (group / signature) | length (bytes) |
|---|---|
| `0x0e` | 4 |
| `lownibble_0xC` | 4 |
| `0x67/0xe7` | 14  [load/store: device, threadgroup (byte+1 bit1=0x02) and constant all share this opcode pair -- EXP-0012] |
| `0x07 (+ byte+2==0x54)` | 6  [THREADGROUP/EXECUTION BARRIER (threadgroup_barrier): 07 04 54 <mem_scope> <flags> 00. byte+3 = fenced memory scope 0x61 threadgroup / 0x85 device. The ONLY explicit ordering op in compute -- device load/store/atomic/texture are NOT scoreboard-waited (HW register interlock). EXP-0025 HW/splice-proven] |
| `lownibble_0x9` | 6, or 8 if (byte[+2] & 0x02), or 4 if byte+2==0x38  [float ALU; byte+2==0x38 = compact 4-byte float accumulate, EXP-0025 -- NOT a wait. byte+2==0x25 (still 6B) = transcendental ESTIMATE SEED (byte0 0x29): byte+3 0x09 rcp / 0x0b rsqrt / 0x0d sqrt estimate, ~8 mantissa bits, the Newton-Raphson seed for precise 1/x/rsqrt/sqrt, EXP-0026] |
| `0x2f/0xaf` | 10  [float SPECIAL-FUNCTION UNIT (SFU): one op computes rcp/rsqrt/exp2 (byte0 0xaf) \| round/sqrt/log2 (byte0 0x2f), function = byte+1 (0x00 rcp\|round / 0x01 rsqrt\|sqrt / 0x02 exp2\|log2). exp/log/pow/div compose these. fast-math emits single ops; precise 1/x/sqrt/div refine with Newton-Raphson. EXP-0013 (exp2/log2/round) + EXP-0026 (rcp/rsqrt/sqrt)] |
| `lownibble_0xB` | 4 if (byte+2==0x01 and byte+3==0x08) [uniform_mov: uniform-reg -> GPR, EXP-0020]; else 10 [float unary / integer and/or/xor] |
| `0x02` | 6  [integer min/max \| compare-for-select] |
| `0x12` | 6 float min/max, or 14 if (byte+2 & 0x0f)==0x0d [int compare] |
| `0x9f/0x1f` | 10 if (byte+1 & 1) else 12  [integer add/sub \| mul-add] |
| `0xa7` | 10 if (byte+1 & 1) else 12  [integer shift-r \| bitfield] |
| `0x27` | 8  [integer unary / popcount] |
| `0x0a` | 6  [integer compare -> execution predicate (branch/return)] |
| `0x05/0x16` | 4  [conditional select (branchless if/ternary)] |
| `0x0f` | 10 if byte+1==0x00 (JUMP: 0f 00 54 <off6> 00, signed byte-rel); other sub-ops (mask push/pop/reconverge) variable = follow-up |
| `lownibble_0x5 + byte+1==0x80 + byte+2==0x0c` | 14  [TEXTURE sample / read: 4B coord/result companion + 10B sampler op (0xb0/0x90). EXP-0016 HW-validated] |
| `0xd7` | 16  [TEXTURE write (memory-family store). EXP-0016 HW-validated] |
| `0x37` | 8 if byte+2==0x56 [quad reduce/scan, EXP-0018]; else 10 [derivative / quad-difference dfdx/dfdy/fwidth, EXP-0016] |
| `0xbf/0x3f/0xb7 (+ byte+2==0x56)` | 8  [SUBGROUP/QUAD reduce & prefix-scan: bit3=scope(1 simd/0 quad), bit7+byte+1=op, byte+7=datatype/shape. SIMD width 32. EXP-0018 HW] |
| `0x47/0xc7` | 10  [SUBGROUP/QUAD shuffle & broadcast: bit7=dir, byte+1=simd/quad/rotate, byte+6=(lane<<1). EXP-0018 HW-validated] |
| `0x17` | 10  [simd_ballot / vote mask source. EXP-0018 HW-validated] |
| `0x67 (byte+1==0x11)` | 14  [device ATOMIC RMW (elected-lane), op at byte+12. EXP-0018 HW] |
| `0x67 (byte+1==0x01)` | 14  [standalone ATOMIC exchange/cmpxchg/indexed, op at byte+12. EXP-0018 HW]. Atomics are native single ops, NOT CAS loops. |
| `0xcf` | 12  [SIMD-group MATRIX multiply-accumulate: one full 8x8x8 cooperative-matrix tile MAC d=a*b(+c). DEDICATED matrix HW. byte+2 0x56 single / 0x54 tiled; byte+7=C src reg; byte+11 bit0=accumulate-enable. simdgroup_load/store are ordinary 0x67/0xe7 memory ops, NOT matrix ops. EXP-0022 HW] |
| `lownibble_0x4 + byte+1==0xea` | 8  [RAY TRACING: dedicated ray-INTERSECT op. byte0 hi nibble=result reg; byte+2 mode (0x90 const-origin / 0x10 dyn-origin / 0xd0 +fn-table); byte+6 bit7=intersection-function-table present. Emitted 2x/kernel (traverse + result-read). ABSENT from a software Moller-Trumbore loop. EXP-0023 HW] |
| `0xdf` | 14  [RAY TRACING: dedicated acceleration-structure / ray-data load (memory-family sibling of 0x67/0xe7, byte+2==0x54). BVH-node/ray/stack fetch during the (software) traversal loop. EXP-0023] |
| `byte0 low-3-bits 0b100` | 4 get_sr (SR#=byte1, dst=byte0-hi; byte+3 lo-nibble==6 suffix, covers 0xNc & 0xN4 forms) \| 2 mov_imm (byte0==0x0c, no suffix). EXP-0031 |
| `0x10` | 6, or 8 if (byte+2 & 0x02)  [NATIVE-HALF (fp16) float ALU, sibling of 0x09. EXP-0033] |
| `0x27 (byte+1==0x05, byte+2==0x56)` | 8  [popcount / bit-scan single op (ibitcount). EXP-0033] |
| `0x27 (byte+1==0x01)` | 12  [ROTATE-by-immediate funnel shift (irotate). EXP-0033] |
| `0xa7 (byte+1 in {0x04,0x05})` | 8  [reverse_bits / find-MSB bit-scan (ibitcount). EXP-0033] |
| `0x97 (byte+2==0x56)` | 10  [pack_convert (pack_float_to_unorm/snorm2x16); byte+2==0x54 is the fragment frag_color_pack. EXP-0033] |
| `0x17 (byte+2==0x56)` | 10  [unpack_convert (unpack_unorm2x16); simd_ballot (byte+1==0x07) is the ballot/vote source. EXP-0033/0018] |
| `0x22` | 6 if (byte+2 lo-nibble==0x0e) [iminmax_chain: min3/max3/clamp] else 10 [shift/sign-extend helper]. EXP-0033 |
| `0xNb (byte+2 low-nibble e/f, 0x2b/3b/5b/8b)` | 10 shift-amount PREP stage; (byte+2 hi-nibble 2) = 4 compact call-argument MOVE; (byte+2 in {0e,1e,1f}) = 10 funary/ilogic; (byte+2==0x01,byte+3==0x08) = 4 uniform_mov. EXP-0033/0036 |
| `0x43` | 4  [CALL-SITE / FRAME-SETUP marker (`43 00 00 01`), precedes every out-of-line CALL in compute & mesh. NOT mesh-unique. EXP-0035 (re-scoped EXP-0030)] |
| `0x0f (byte+1==0x05)` | 14 direct CALL if byte+4==0x8f (target = call_addr+4+off40) else 8 exec-mask push; (byte+1==0x80) = 6 INDIRECT CALL leader; (byte+1==0x06) = 6 reconverge. EXP-0035 |
| `0x8f` | 4  [function RETURN (`8f <lm> 54 00`); no encoded target (HW link register / CF stack); byte+1 0x02 leaf / 0x12 non-leaf. EXP-0035] |
| `0x57` | 8  [VERTEX varying / [[position]] store to the UVS/parameter buffer the FS iter op interpolates. Memory-family (low-nibble 7). byte+3=source GPR, byte+4=output slot (index<<5; position=slots 0-3). EXP-0037 HW-splice-proven] |
| `lownibble_0x5 + (byte+1 & 0xf0)==0x80 + byte+2==0x0c` | 14  [tex_sample companion-gate WIDENED (EXP-0037) from byte+1==0x80 to high-nibble 8 so the CHAINED-companion forms (0x82/0x84/0x88 before the 2nd..Nth sample op) also absorb their 10-byte 0xb0/0x90 sampler op] |
| `0x09 op-select 0x26/0x2e` | 8 if (byte+4 & 0x02) else 6  [fused mul / mul-add COORDINATE / matrix-multiply op -- byte+2 bit1 is SET yet the 2-source form is 6B, so length reads byte+4 bit1 not byte+2 bit1 (EXP-0037). 0x09 op-select 0x18/0x38 = 4 compact accumulate] |
| `0xNb (byte+2 in {0x27,0x2f})` | 10  [texture COORDINATE / LOD / gather-offset setup ALU (tex_coord_setup); must precede the (byte+2 hi-nibble 2)=4 compact-move branch. EXP-0037] |
| `0x2e/0x3e (byte+2==0x23)` | 10  [coordinate / interpolation fused mul-add ALU LEADER (coord_madf); gated tightly on the `23 a0 42` coord signature. EXP-0037] |
| `0x30/0x90/0xb0 (byte+2 in texture-variant set)` | 10  [standalone texture SAMPLER OP fallback, resync-only; primary closer is the companion-gate widening. EXP-0037] |
| `0x32` | 6  [u64 CARRY-GENERATE (carry_gen): unsigned-overflow compare (byte+2==0x35, byte+4==0x22) detecting the low-word add carry in a 64-bit ADD chain; predicate feeds a 0x05 psel. EXP-0038] |
| `0x22 (byte+2==0x35)` | 6  [carry-generate sibling of 0x32 (intermediate carry of a 3-operand u64 add); the byte+2 lo-nibble 0x0e min3/max3/clamp form is also 6, else 10. EXP-0038] |
| `0x6f` | 6  [NON-LEAF FUNCTION FRAME PROLOGUE (frame_prologue): establishes the per-thread scratch frame a non-leaf callee uses to save its link register around inner calls. EXP-0038] |
| `0x07 (byte+1==0x00, byte+2==0x54)` | 8  [LINK-REGISTER SAVE/RESTORE around a nested call in a non-leaf frame (link_save_restore); the byte+1 in {0x04,0x14} forms are the 6-byte threadgroup_barrier / pixel_order. EXP-0038] |
| `0x18` | 4  [HALF-LANE PACK (half_pack): assemble a half2's two fp16 lanes into one packed 32-bit register before the store. byte0 hi nibble = dst reg (0x08/0x18/0x28/0x38 = r0..r3). EXP-0038] |
| `0xbf/0x3f/0xb7 cache bit` | the reduce length/match gate accepts byte+2 in {0x54,0x56} (bit17 = a source cache/last-use hint, not an op change; EXP-0038). NB the 0x37 derivative-vs-quad-reduce byte+2==0x56 disambiguation is deliberately NOT relaxed. |
| `0x5f (byte+2 in {0x54,0x56})` | 14  [RAY-TRACING ray-data / traversal-stack memory op (rt_ray_mem); the store/spill-side sibling of the 0xdf AS-load, carries the ray_data payload copy-in/out. EXP-O2C] |
| `0xN2 (byte+2==0x27)` | 10  [RAY-TRACING ray-vs-node transform / AABB box-test companion (rt_transform_test), byte+3==0x81 byte+4==0x22; ~4-5 per intersector. Gated on byte+2==0x27 and placed BEFORE the 0x02/0x32 handlers (which return unconditionally). EXP-O2C] |
| `0xNb (byte+2 in {0x80,0x81})` | 4  [RAY register-marshalling MOVE (ray_move): byte+2==0x81 copies a computed reg into the block rt_intersect consumes, 0x80 zero-inits a component. Reused 35-38x for MPP matmul2d TRANSPOSE tile moves. EXP-O2C] |
| `0xcf operand decode` | the 0xcf matrix_mac operands are now FULLY decoded (EXP-O2C splice): byte+5=A (left) operand, byte+6=B (right), byte+7=C accumulator src, byte+8=dst, byte+3=A sub-descriptor (load-bearing), byte+10=op-enable 0x24, byte+1=dtype, byte+2=mode (0x56 standalone SEMANTIC vs 0x54 tiled/MPP), byte+11 bit0=accumulate-enable. All MPP tensor ops lower to this one op. |
| `0x11` | 6 if byte+1==0x03 (fp32->fp16 convert cvt_f2h); else 8 if byte+1 in {0x02,0x04} (NATIVE bfloat ALU add/mul, opsel byte+2 0x1c/0x1d) or 10 if also (byte+2 & 0x02) (bfloat fma, opsel 0x1e). LOAD-BEARING FIX (EXP-O2D): the old flat `8 if byte+2&0x02 else 6` mis-lengthed every bfloat op (bf_add 0x1c -> 6, bf_fma 0x1e -> 8) and desynced bfloat kernels. Disambiguate on byte+1 -- cvt_f2h and bf_add SHARE opsel byte+2==0x1c. |
| `0xe7 (byte+1 in {0x06,0x16})` | 12  [fragment COLOUR STORE (0x06 frag_color_store) / explicit imageblock<T>.write (0x16 = first tile store after a 0x87 setup, imageblock_store): byte+5 = imageblock field BYTE-OFFSET>>1 (vs MRT's RT index rt<<1), byte+7 = slice format. EXP-0029/O2D] |
| `0x67 (byte+1 in {0x06,0x0e,0x16})` | 12  [fragment TILEBUFFER READ (0x0e tile_read, programmable blend) / explicit imageblock<T>.read (0x06/0x16 tile variant, imageblock_load). EXP-0029/O2D] |
| `0x07 (byte+2==0x54, byte+3==0x84)` | 6  [DEVICE MEMORY FENCE (mem_fence): atomic_thread_fence(mem_device, seq_cst) = `07 04 54 84 0a 00`. byte+3 0x84 = device-memory FENCE (vs threadgroup_barrier's 0x85 device = 0x84\|0x01, the 0x01 = the added EXECUTION barrier); byte+4 0x0a = device memory-class flag. Ordering realised by fence PRESENCE, not a bit on the 0x67 RMW op (relaxed emits no fence, seq_cst emits it; acquire/release REJECTED by MSL). mem_texture is a byte+4==0x06 pair that decodes as pixel_order. EXP-O2D] |
| `get_sr SR 0x84` | simd_is_helper_thread (FS): the get_sr-family leader `04 84 11 06`, read then compared. Distinct from 0x82 simd_lane_id / 0x85 simd_group_id. EXP-O2D |
| `simd_reduce byte+1==0x06 bit7` | FLOAT simd_product / prefix-product (bit7=1, byte0=0xbf) vs simd_sum (bit7=0, byte0=0x3f); byte+7 0x32 = FLOAT exclusive-scan. INTEGER product has no native reduce op (shuffle+multiply tree). EXP-O2D |
| `simd_shuffle byte+1==0x06` | simd_shuffle_and_fill_up/down (fill data = a separate preceding 0x67 load) / rotate; modulo variant changes byte+6 (0x4a->0x42) + a tail modulo byte. EXP-O2D |

---

*Rendered from `tools/agx-isa/db.json` — 75 descriptors. The machine-readable source of truth is `db.json` / `isadb.py`; this document is its human-readable projection.*
