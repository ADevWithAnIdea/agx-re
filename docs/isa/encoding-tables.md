# A18 Pro (G17P) AGX — Instruction Encoding Tables

> **Generated** from `tools/agx-isa/db.json` by `tools/agx-isa/gen_encoding_tables.py` (2026-08-28). Regenerate after any DB change; do not hand-edit. This is the **authoritative, self-contained encoding table** a driver author reads to emit A18 Pro AGX instructions — 170 instruction descriptors.

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
| `srcA_reg` | [9:15] | register |  |
| `opsel` | [16:19] (byte+2) | opcode-select | `0x4`=fadd; `0x5`=fmul; `0x6`=fma; `0x7`=fmul_interp |
| `opflags` | [19:24] | modifier |  |
| `srcB_size` | [24:25] (byte+3) | enum | `0x1`=b32; `0x0`=b16 |
| `srcB_reg` | [25:31] | register |  |
| `ctrl` | [32:39] (byte+4) | modifier |  |
| `srcB_imm` | [39:40] | enum | `0x0`=reg; `0x1`=immediate |
| `mod_lo` | [40:43] (byte+5) | modifier |  |
| `srcB_neg` | [43:44] | modifier |  |
| `mod_hi` | [44:48] | modifier |  |
| `srcA_reg_top` | [15:16] | modifier |  |
| `srcB_reg_top` | [31:32] | modifier |  |

*d = op(srcA, [-]srcB)  ; 2-source float ALU. src operand byte = (reg<<1)|is32 (bit0=size; 7-bit reg field, GPR file = up to 96 addressable 32-bit regs, EXP-0020). dst here is the compact b0[4:8] nibble (r0..r15 only); a high GPR dst uses the 8-byte falu3 form (dst=byte+1, 7-bit) -- HW seen writing r64. srcB negate = bit43. srcB-immediate mode = bit39 (see falu2i). When bit39=1, srcB is NOT a GPR: byte+1's exponent nibble (bits[12:16], = instr bit15 = the 8s bit) SPLITS the two overloads -- exp>=8 (bit15=1) => packed minifloat immediate (falu2i), exp<8 (bit15=0) => UNIFORM-REGISTER source (falu2_uni). RT-1a-FIX HW-validated (supersedes the earlier `byte+2 bit4 / byte+5 bit1` guess, which was wrong).  [CORRECTED 2026-08-28] The source register operand is 6 BITS, not 7. Its former top bit (srcA_reg_top / srcB_reg_top) is HW-TESTED INERT for both addressing and retention -- refuted as a register-index bit (EXP-0099 H1: field value 67 reads r3, never the unwritten r67) AND refuted as a retention flag (EXP-0099 H2: outcome depends only on opflags bit19/bit20, identically whether the top bit is 0 or 1). Reconfirmed on falu2i, falu2_ext and falu3_srcmod12 (EXP-0119). ALIASING RULE (EXP-0112, HW-VALIDATED by a dense 15-point sweep with poison-register controls): a target register R resolves to r(R mod 64) for R in [64,112], and FAULTS the command buffer at R in {126,127}. That mod-64 aliasing is why value 67 reads r3. r64-95 have NO validated ALU-source path. LIFETIME FIELDS (EXP-0086/0089/0099/0119): opflags bit19 = release src0, bit20 = release src1, bit21 = destination publication. These are LOAD-BEARING, not hints: releasing a source that a LATER instruction reads makes that later read return zero, deterministically and without a fault, and the value is genuinely gone from the register file (it survives a memory round-trip and a threadgroup_barrier; an ordinary rewrite restores it). opflags bits 22/23 and mod_hi bit 44 are general silent CORRUPTORS (EXP-0105). ctrl bits 0/1 are the INSTRUCTION-LENGTH selector, not free bits (EXP-0119); ctrl bit4 is inert and bits 5/6 corrupt (EXP-0113).*

### `falu2i` — 2-source float ALU, srcB packed minifloat immediate

- **Length:** 6 bytes  ·  **Match:** bits[0:4]==0x9, bits[39:40]==0x1  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `imm_flag` | [8:9] (byte+1) | modifier |  |
| `imm_mant` | [9:12] | immediate |  |
| `imm_exp` | [12:16] | immediate |  |
| `opsel` | [16:19] (byte+2) | opcode-select | `0x4`=fadd; `0x5`=fmul; `0x6`=fma; `0x7`=fmul_interp |
| `imm_sign` | [19:20] | modifier |  |
| `opflags` | [20:24] | modifier |  |
| `srcA_size` | [24:25] (byte+3) | enum | `0x1`=b32; `0x0`=b16 |
| `srcA_reg` | [25:31] | register |  |
| `ctrl_lo` | [32:39] (byte+4) | modifier |  |
| `mods` | [40:48] (byte+5) | modifier |  |
| `srcA_reg_top` | [31:32] | modifier |  |

*d = op(srcA, K)  ; srcB is the packed non-IEEE float immediate K = imm_decode(b1, sign). exp(bits12:16,bias11) mant(bits9:12) flag(bit8) sign(bit19). Range +-{0,1/32..30}. HW-VALIDATED EXP-0006.  [CORRECTED 2026-08-28] srcA_reg is 6 BITS with an inert top bit -- see falu2's corrected note; the refutation was independently reproduced on falu2i by construction (EXP-0105). falu2i additionally requires mods = 0xC0 (bits 6+7 together; neither alone) when its operand is LOAD-SOURCED (EXP-0101).*

### `falu2_uni` — 2-source float ALU, srcB UNIFORM-register source (a + uniform)

- **Length:** 6 bytes  ·  **Match:** bits[0:4]==0x9, bits[39:40]==0x1, bits[15:16]==0x0  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `usrc` | [8:16] (byte+1) | register |  |
| `opsel` | [16:19] (byte+2) | opcode-select | `0x4`=fadd; `0x5`=fmul; `0x6`=fma; `0x7`=fmul_interp |
| `opflags` | [19:24] | modifier |  |
| `srcA_size` | [24:25] (byte+3) | enum | `0x1`=b32; `0x0`=b16 |
| `srcA_reg` | [25:32] | register |  |
| `ctrl_lo` | [32:39] (byte+4) | modifier |  |
| `uni_mode` | [39:40] | enum | `0x1`=srcB_not_gpr |
| `mods` | [40:48] (byte+5) | modifier |  |

*d = op(srcA_gpr, uniform_reg[usrc>>1])  ; srcB is a UNIFORM (thread-invariant) register, not a GPR and not an immediate. Selected when bit39=1 AND byte+1's exponent nibble < 8 (bit15=0); the minifloat immediate (falu2i) uses exp>=8 (bit15=1). uniform index = byte+1 = (ureg<<1)|size32. The uniform value is preloaded by the driver / the constant (uniform) program (EXP-0010/EXP-0020). RT-1a-FIX HW-VALIDATED.*

### `falu3` — 3-source float ALU (fma)

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x9, bits[17:18]==0x1  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst_lo` | [4:8] | register |  |
| `dst` | [8:16] (byte+1) | register |  |
| `op` | [16:24] (byte+2) | opcode-select | `0x1e`=fma; `0x26`=fma_coord; `0x2e`=fma_coord; `0x36`=fma; `0x3e`=fma; `0x46`=fma_coord; `0x4e`=fma_coord; `0x62`=fma; `0x66`=fma; `0x6e`=fma_coord; `0x8e`=fma_coord; `0xae`=fma_coord |
| `srcA` | [24:32] (byte+3) | register |  |
| `srcB` | [32:40] (byte+4) | register |  |
| `srcC` | [40:48] (byte+5) | register |  |
| `ctrl` | [48:56] (byte+6) | modifier |  |
| `srcmods` | [56:64] (byte+7) | modifier |  |

*d = +/-(a*b) + c ; three-source float ALU (fma). srcA=byte+3, srcB=byte+4, srcC=byte+5. The 16-bit tail is the float-ALU source-modifier/cache region (same family as the HW-validated falu3_srcmod12 ext_srcmod): ctrl (byte+6, cache/round; usually 0x02) and srcmods (byte+7): default 0xc0, bit3 (0x08) = negate the a*b product -- OWN-MSL byte-diff located (fma with -a or -b flips byte+7 0xc0->0xc8). Remaining srcmods bits (abs promotes to the 12B falu3_srcmod12 form) need splice for the full map.*

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
| `srcA` | [24:32] (byte+3) | register |  |
| `srcB` | [32:40] (byte+4) | register |  |
| `src_modifier` | [40:48] (byte+5) | modifier |  |

*d(half) = op(a, b)  ; NATIVE half-precision (fp16) float ALU. byte0 0x10 is the 16-bit-destination sibling of the 0x09 float ALU (and the 0x11 narrow-convert group); same op-select (byte+2 low-3 bits: 0b100=hadd/0x1c, 0b101=hmul/0x1d) and same 6/8-byte length bit (byte+2 bit1). A half2 (packed 2xfp16) op executes BOTH 16-bit lanes in ONE 0x10 op, then a 0x18 pack assembles the 32-bit result. (short2/2x-int16 does NOT pack: two separate 32-bit 0x9f integer adds.) HW-VALIDATED (splice, A18 EXP-M4-14, own-MSL pureh.metal k_pureadd `10 03 1c 02 00 c0`, a=[1,2,4,8] in r1(byte+3=0x02), b=[16,32,64,128] in r0(byte+4=0x00)): srcA (byte+3) is the FIRST, negatable source -- RETYPES the former 'srcB@byte+3'; sweeping byte+3 0x02->0x04/06/08 yields result=b alone (srcA read as 0). srcB (byte+4) = second source operand descriptor (baseline 0x00 reads b; low bits gate/type it, bit1 0x02 nulls the op; exact register-vs-type bit packing partially resolved). src_modifier (byte+5) = source-modifier/control byte: bits6:7 (0xc0) are a required operand-valid base (clearing -> op yields 0); bit3 (0x08) = srcA-negate (0xc8 -> -a+b, CONFIRMED); bit0 (0x01) suppresses srcB (result = srcA); bits1/2 (0x02/0x04) suppress srcA (result = srcB).*

### `falu_acc` — compact 4-byte float accumulate (reduction)

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0x9, bits[17:21]==0xc, bits[22:24]==0x0  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `srcA` | [8:16] (byte+1) | register |  |
| `op` | [16:17] (byte+2) | opcode-select | `0x0`=fadd_acc; `0x1`=fmul_acc |
| `cache` | [21:22] | modifier |  |
| `srcB` | [24:32] (byte+3) | register |  |

*d = srcA (+) srcB  ; COMPACT 4-byte float accumulate (float-ALU group low-nibble 9, byte+2 in {0x18,0x38} = opsel with the arithmetic-enable bit clear vs the 6-byte 0x3c fadd). Omits the byte+4/+5 modifier tail of the 6-byte falu2, so the compiler emits it for plain reduction accumulates. byte+3 = srcB register descriptor. byte+2 bit5 (`cache`: 0x18 vs 0x38) is a source-cache/last-use hint, NOT an op change (RT-1a-FIX: splice 0x18<->0x38 leaves the reduction result unchanged).*

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
| `fn_hi` | [7:8] | enum | `0x0`=direct (0x2f: sqrt/log2/round-family/sincos); `0x1`=reciprocal (0xaf: rcp/rsqrt/exp2) |
| `fnclass` | [8:12] (byte+1) | opcode-select | `0x0`=rcp|round; `0x1`=rsqrt|sqrt; `0x2`=exp2|log2; `0x3`=sincos/tan primitive (inferred); `0x4`=compound intermediate (pow/exp range-reduce, inferred) |
| `dst` | [12:16] | register |  |
| `src_cache` | [16:24] (byte+2) | modifier | `0x56`=cached source (fresh operand); `0x54`=uncached (later consumer of a shared/computed source) |
| `src` | [24:32] (byte+3) | register |  |
| `src_class` | [32:40] (byte+4) | enum | `0x3`=32-bit GPR source; `0x2`=16-bit / alt operand class |
| `src_ext` | [40:48] (byte+5) | register |  |
| `fnsel` | [48:56] (byte+6) | opcode-select | `0x10`=rcp datapath; `0xb0`=std SFU f32 (rsqrt/exp2/log2/round); `0x92`=sqrt / sincos datapath; `0xac`=SFU f16 datapath; `0x2`=rcp alt-operand form; `0x8a`=(inferred); `0x8e`=(inferred); `0x90`=(inferred); `0x0`=(inferred); `0x20`=compound range-reduce (inferred) |
| `precsel` | [56:64] (byte+7) | modifier | `0x40`=f32 result; `0x48`=rcp f32; `0x60`=f16 result; `0x44`=(inferred); `0xc0`=log2 negate (inferred); `0x0`=(inferred) |
| `roundmode` | [64:72] (byte+8) | enum | `0x0`=nearest / none; `0x2`=floor; `0x4`=ceil; `0x6`=trunc; `0x20`=reciprocal-precision flag (rcp/1-op SFU) |
| `sched_flag` | [72:80] (byte+9) | modifier |  |

*d[dst] = SFU(src). Function = (byte0 bit7 fn_hi, byte+1-lo fnclass): (direct,0x0)=round[floor/ceil/trunc/rint via byte+8], (direct,0x1)=sqrt, (direct,0x2)=log2, (direct,0x3)=sincos/tan primitive; (recip,0x0)=rcp(1/x), (recip,0x1)=rsqrt(1/sqrt x), (recip,0x2)=exp2(2^x). dst = byte+1 HIGH nibble (GPR, PROVEN by a 5-way rsqrt dst sweep 0x01/0x11/0x21/0x41/0x81). Source operand = byte+3 (reg low) + byte+5 (reg ext) + byte+4 (operand class 0x03 f32 / 0x02 f16-or-alt); byte+2 = source-cache bit (0x56 fresh / 0x54 shared). byte+6/+7 = the secondary function+precision datapath descriptor (co-varies with the function & result size: rcp 0x10/0x48, std-f32 0xb0/0x40, sqrt/sincos 0x92/0x40, f16 0xac/0x60). byte+8 = round mode (round family) or the reciprocal precision flag (0x20). byte+9 = a result/last-use scheduling flag. One hardware special-function op; fast-math emits it directly (~1 ULP). exp/exp10 = exp2(x*k); log/log10 = log2(x)*k; pow = exp2(b*log2(a)); a/b = a*rcp(b).*

### `fspecial_est` — transcendental estimate seed (rcp/rsqrt/sqrt NR seed)

- **Length:** 6 bytes  ·  **Match:** bits[0:4]==0x9, byte+2==0x25, bits[28:32]==0x0, bits[24:25]==0x1, bits[27:28]==0x1  ·  **Provenance:** HW-validated

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
| `addsub` | [7:8] | opcode-select | `0x1`=iadd; `0x0`=isub |
| `lenbit` | [8:9] (byte+1) | modifier |  |
| `srcB_reg_hi` | [9:16] | modifier |  |
| `b2_bit0` | [16:17] (byte+2) | modifier |  |
| `store_en` | [17:18] | modifier |  |
| `b2_fmt` | [18:24] | modifier |  |
| `dst` | [24:32] (byte+3) | register |  |
| `opmode` | [32:40] (byte+4) | modifier |  |
| `srcB_imm` | [40:48] (byte+5) | immediate |  |
| `srcB_imm_hi` | [48:49] (byte+6) | immediate |  |
| `srcB_ext` | [49:56] | modifier |  |
| `srcA` | [56:64] (byte+7) | register |  |
| `opc_tail` | [64:72] (byte+8) | modifier |  |
| `opc_tail2` | [72:80] (byte+9) | modifier |  |

*d = srcA + srcB (addsub=1, byte0 0x9f) | d = srcA - srcB (addsub=0, byte0 0x1f)  ; integer 2-source add/sub. byte0 bit7 (addsub) is the ADD/SUBTRACT selector: the compiler emits 0x9f for + and 0x1f for -, and splicing a real add's byte0 0x9f->0x1f turns 10+20 into 10-20=-10 on hardware (RT-1a-FIX -- corrects the earlier INVERTED `srcA_neg`/semantics). dst=b3 (reg<<1)|size, a full 8-bit byte -> 7-bit reg (r0..r127), so unlike the 6-byte falu2's 4-bit dst nibble the integer dst reaches the whole GPR file (up to 96 regs, EXP-0020). srcB may be an 8-bit inline immediate K in [0,255] encoded as (K<<1) at b5:b6bit0 (NOT a minifloat -- EXP-0007). A source may name a UNIFORM register: uniform srcB sets byte+5 bit4 (0x10), uniform srcA sets byte+6 (0x30) -- HW byte-diff EXP-0020. EXP-M4-13 R6 (own-MSL byte-diff): signed and unsigned add/sub are BYTE-IDENTICAL (the 10-byte 2-src add is sign-agnostic; there is no separate sign field). The srcB immediate is a 9-bit field (srcB_imm b5[0:8] + srcB_imm_hi b6bit0) stored (K<<1): addi{1,5,7,255}->b5=0x02/0x0a/0x0e/0xfe, b6bit0=1 at 255. srcB REGISTER NUMBER is scattered (srcB_reg_hi b1[1:8] + srcB_imm/b5 + srcB_ext b6[1:8]); the srcB-is-register-vs-immediate TYPE flips opc_tail/opc_tail2 (b8 bit1, b9 bit0) and srcA b7 bit5 -- reg-srcB tail = a8 17 05, imm-srcB tail = 88 15 04.*

### `imad` — integer multiply-add (imul = c=0)

- **Length:** 12 bytes  ·  **Match:** bits[0:7]==0x1f  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b0bit7` | [7:8] | modifier |  |
| `lenbit` | [8:9] (byte+1) | modifier |  |
| `b1hi` | [9:16] | modifier |  |
| `b2_bit0` | [16:17] (byte+2) | modifier |  |
| `store_en` | [17:18] | modifier |  |
| `b2_fmt` | [18:24] | modifier |  |
| `dst` | [24:32] (byte+3) | register |  |
| `opmode` | [32:40] (byte+4) | modifier |  |
| `srcB` | [40:48] (byte+5) | register |  |
| `srcC_lo` | [48:56] (byte+6) | modifier |  |
| `srcC_desc` | [56:64] (byte+7) | modifier |  |
| `mulsel` | [64:72] (byte+8) | modifier |  |
| `b9` | [72:80] (byte+9) | modifier |  |
| `b10` | [80:88] (byte+10) | modifier |  |
| `b11` | [88:96] (byte+11) | modifier |  |

*d = srcA*srcB (+ srcC)  ; integer multiply-add (imul is this with c=0). EXP-M4-13 R6 (own-MSL byte-diff): LOW-32 mul is sign-agnostic (a*b int==uint byte-identical); mad int==uint byte-identical. ACCUMULATE (srcC) is encoded in srcC_desc (b7): 0x00 = no addend (imul), 0x40 = register addend (b9->0x2f, b10->0x2a), (K<<3) = immediate addend (K in b7[3:8]+mulsel[0:3], proven K=1/5/7/255). HI vs LO multiply selects mulsel (b8): 0xd0 = low 32 bits, 0xe0 = high 32 bits (mulhi); MULHI is sign-dependent -- signed mulhi flips b10 (0x0a->0x1e) whereas low mul does not. dst=b3 (reg<<1)|size PROVEN by an r6/r4/r2 dst sweep.*

### `iminmax` — integer min/max (signed/unsigned)

- **Length:** 6 bytes  ·  **Match:** bits[0:4]==0x2, bits[16:19]==0x6  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `dst_full` | [8:16] (byte+1) | register |  |
| `fmt` | [19:24] | modifier |  |
| `srcA` | [24:32] (byte+3) | register |  |
| `sel` | [32:35] (byte+4) | opcode-select | `0x0`=fmax; `0x1`=fmin; `0x4`=umax; `0x5`=umin; `0x6`=imax; `0x7`=imin |
| `selhi` | [35:40] | modifier |  |
| `srcB` | [40:48] (byte+5) | register |  |

*d = min/max(a,b) by TYPE (32-bit int signed/unsigned, or float). byte0 hi nibble = dst r0..r15. byte1 = (dst<<1)|size. byte+2 = source-format marker (bits[16:19]==0b110). byte+3 = srcA. byte+4 = OP-SELECT (sel low 3 bits): 0=fmax 1=fmin 4=umax 5=umin 6=imax 7=imin. byte+5 = srcB.  [PROVENANCE FLAG 2026-08-28] Two independent experiments hit an unexplained anomaly here: splicing a REAL, IN-RANGE register field produced ZERO effect on output, and a hand-built program could not read back even a mov_imm-seeded low register (EXP-0105). EXP-0113 then found this family's spliced results NONDETERMINISTIC ACROSS RUNS -- identical bytes, different outcomes in 4/46 cases -- so the pilot impression that it could address r96-127 was an artifact, not a mechanism. Treat this descriptor's operand mapping as UNVALIDATED pending a dedicated experiment.*

### `iunary` — integer unary (popcount / reduce)

- **Length:** 8 bytes  ·  **Match:** byte+0==0x27  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | modifier |  |
| `opsel` | [16:24] (byte+2) | enum | `0x56`=int_unary/convert; `0x22`=rt/interp_datapath; `0x10`=convert; `0x26`=convert2; `0x7`=logic |
| `operand` | [24:64] (byte+3) | raw/unmapped |  |

*d = unary_int/convert(srcA) ; 8-byte byte0==0x27 datapath op. b1 (byte+1) = function/source descriptor. opsel (byte+2) = mode: 0x56 = the integer-unary / format-convert datapath (popcount/bitcount HW-VALIDATED here, EXP-0007/0033; vertex-fetch format unpack shares 0x56); 0x22 = the ray-tracing / interpolation datapath (byte+1==0x81, seen only in RT + interp kernels); 0x10 = a convert form; 0x07 = logic. operand (byte+3..+7) = source + coefficient/format word, MIXED (popcount source vs SFU/interp/format-conversion coefficient) -- kept raw; the SFU/interp/format coefficient SEQUENCE is not reconstructed (rule 5). NOTE: this is a loose byte0==0x27 catch-all; the popcount claim is the HW-validated member, but the corpus is dominated by RT/interp/convert siblings of the same length.*

### `ibitcount` — bit-count / bit-scan (popcount/reverse_bits/find-MSB)

- **Length:** 8 bytes  ·  **Match:** bits[0:7]==0x27, bits[9:10]==0x0, bits[16:17]==0x0, bits[18:24]==0x15  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `fn_hi` | [7:8] | opcode-select | `0x0`=popcount(b1=0x05); `0x1`=reverse_bits(b1=0x04)|find_msb(b1=0x05) |
| `form` | [8:16] (byte+1) | opcode-select | `0x4`=reverse; `0x5`=count/scan |
| `cache` | [17:18] | modifier |  |
| `dst` | [24:32] (byte+3) | register |  |
| `op_enable` | [32:40] (byte+4) | modifier | `0x2`=op computes (bit1 set); `0x3`=op computes (bit1 set) |
| `src` | [40:48] (byte+5) | register |  |
| `srcdesc` | [48:56] (byte+6) | modifier | `0x0`=passthrough/move (source returned raw, no count) |
| `tail` | [56:64] (byte+7) | modifier |  |

*single-op bit-count / bit-scan (8B). HW-VALIDATED (splice, A18 EXP-M4-14, own-MSL iunary.metal popcount `27 05 56 00 02 00 5c 04`, inputs [15,16,65535,0x40000001], baseline popcount [4,1,16,2]): the SUB-OP is selected by (byte0 bit7 fn_hi + byte+1 form), NOT by byte+4 -- splice byte0 0x27->0xa7 -> [3,4,15,30]=find_msb; splice (0xa7, byte+1 0x05->0x04) -> reverse_bits (matches k_reverse). CORRECTION: byte+4 is an op-ENABLE gate (op_enable), NOT the sub-op selector -- splicing byte+4 0x02->0x03 KEEPS popcount [4,1,16,2] (only bit1 matters: 0x02/0x03/0x06/0x07/0x0a compute, 0x00/0x01/0x04/0x05 -> result 0); this corrects the former "optype 0x02 popcount vs 0x03 find_msb" label (correlation, not causation). cache (byte+2 bit17, writeback-enable): only 0x54/0x55 (bit1 clear) break the stored result, 0x56 standalone writes back; all other byte+2 bits inert. dst (byte+3) = destination reg (reg<<1, r0=0x00): sweeping to 0x02/04/06/08 breaks delivery ([0,0,0,0]). src (byte+5) = source reg (reg<<2, r0=0x00): non-zero points at an empty register -> popcount(0)=0. srcdesc (byte+6) = source operand descriptor: 0x00 degenerates the op to identity (returns the raw input, popcount NOT applied), bit6 (0x40) must be set for the GPR source to be read (0x3c/0x9c -> 0; 0x5c/0x4e/0x58 read normally). tail (byte+7, 0x04 marker).*

### `carry_gen` — u64 carry-generate (unsigned-overflow compare for 64-bit add)

- **Length:** 6 bytes  ·  **Match:** bits[0:4]==0x2, byte+2==0x35  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `subop` | [8:16] (byte+1) | raw/unmapped |  |
| `srcA` | [24:32] (byte+3) | register |  |
| `cmpmode` | [32:40] (byte+4) | enum | `0x22`=ordered |
| `b5` | [40:48] (byte+5) | raw/unmapped |  |

*u64 CARRY-GENERATE. `32 01 35 03 22 81` (6 bytes). An unsigned-overflow compare in the integer compare / min-max family (byte0 0x32 = 0x02|0x30; byte+2==0x35 marker; byte+4==0x22 ordered-compare mode) detecting the carry-OUT of the immediately-preceding low-word 32-bit add (sum_lo < operand, unsigned). Its per-lane predicate feeds a following 0x05 psel that materializes the carry as {0,1}, added into the HIGH-word add. The compiler emits this explicit chain for 64-bit ADD; 64-bit SUB uses the single native 0x1f op. Siblings byte0 0x12 (a+const) and 0x22 (intermediate carry of a 3-operand add) share the byte+2==0x35 signature. Operand register bit-packing inferred (byte-diff).*

### `irotate` — rotate-by-immediate funnel shift

- **Length:** 12 bytes  ·  **Match:** byte+0==0x27, byte+1==0x01, bits[16:17]==0x0, bits[18:24]==0x15  ·  **Provenance:** HW-validated

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
| `form` | [9:16] | modifier |  |
| `src_cache` | [16:24] (byte+2) | modifier |  |
| `srcA` | [24:32] (byte+3) | register |  |
| `src_class` | [32:40] (byte+4) | modifier |  |
| `opB` | [40:48] (byte+5) | register |  |
| `shamt` | [48:56] (byte+6) | immediate |  |
| `shift_type` | [56:64] (byte+7) | modifier |  |
| `op8` | [64:72] (byte+8) | immediate |  |
| `pad9` | [72:80] (byte+9) | immediate |  |

*ARITHMETIC (sign-preserving) shift-right by an immediate is the HW-VALIDATED member of this BROAD 10-byte 0xa7 bucket (byte+1 bit0==1). d = a >> shamt: shift amount at byte+6 encoded as (shamt<<2) -- CONFIRMED EXP-M4-13 R8 own-MSL: >>1/2/4/8 -> byte+6 0x04/0x08/0x10/0x20 (k_ashr1/2/4/8), with byte+7 = 0x78 (arithmetic-shift-right op-type) and byte+2 = 0x56 flipping to 0x54 when the source is a computed/consumed register (k_ashr2_srcB). byte+3/+5 carry the operand-register bits (advance in k_ashr2_two). NOTE: this descriptor is length-selected (every odd-b1 10-byte 0xa7) and so also absorbs the 0xa7 10-byte INTERPOLATION / RT datapath siblings (byte+1==0x81, byte+2==0x22 -- corpus-dominant, 138/188); for those, byte+6/+8/+9 are operand/coefficient words, not a shift amount. Logical >> by immediate uses the 12-byte bitfield-extract form (ibfe); register-operand shifts are multi-instr with a 0x2b prep stage. Per-op-select tail semantics of the non-shift siblings NOT reconstructed (rule 5).*

### `ibfe` — bitfield-extract / logical shift-right

- **Length:** 12 bytes  ·  **Match:** byte+0==0xa7, bits[8:9]==0x0  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `lenhi` | [9:16] | modifier |  |
| `b2_bit0` | [16:17] (byte+2) | modifier |  |
| `store_en` | [17:18] | modifier |  |
| `b2_fmt` | [18:24] | modifier |  |
| `dst` | [24:32] (byte+3) | register |  |
| `b4` | [32:40] (byte+4) | modifier |  |
| `b5` | [40:48] (byte+5) | modifier |  |
| `b6_bit0` | [48:49] (byte+6) | modifier |  |
| `sign_ext` | [49:50] | modifier |  |
| `offset` | [50:56] | immediate |  |
| `b7` | [56:64] (byte+7) | modifier |  |
| `srcA` | [64:72] (byte+8) | register |  |
| `srcC_flags` | [72:80] (byte+9) | modifier |  |
| `width_lo` | [80:84] (byte+10) | modifier |  |
| `width` | [84:90] | immediate |  |
| `b11hi` | [90:96] | modifier |  |

*bitfield-extract extract_bits(a, off, cnt) (3-operand 12-byte form). Also the lowering for LOGICAL (unsigned) shift-right by an immediate: a>>k = extract_bits(a, k, 32-k). EXP-M4-13 R6 (own-MSL byte-diff): the bitfield OFFSET immediate is offset = b6>>2 (start bit50, PROVEN off 1/3/4/5/6/8 -> b6 0x04/0x0c/0x10/0x14/0x18/0x20); the WIDTH immediate is width = (b10|b11<<8)>>4 (start bit84, PROVEN width 1/4/8/12/16 -> 0x10/0x40/0x80/0xc0/0x100). An unsigned shift-right a>>k lowers to offset=k, width=0 (width=0 => extract-to-MSB / all remaining bits). SIGNED (sign-extending) extract_bits sets sign_ext (b6 bit1) and clears srcC_flags bit0 (b9 0x11->0x10); unsigned zero-extends. dst=b3 (reg<<1)|size PROVEN by a dst sweep (b3 0x0c/0x0a/0x06 = r6/r5/r3).*

### `icmpsel` — compare -> select 0/1 (full condition codes)

- **Length:** 14 bytes  ·  **Match:** bits[0:4]==0x2, bits[16:20]==0xd  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `dst_full` | [8:16] (byte+1) | register |  |
| `fmt` | [20:24] | modifier |  |
| `srcA` | [24:32] (byte+3) | register |  |
| `cmpmode` | [32:40] (byte+4) | enum | `0x22`=ordered(lt/gt); `0x26`=equal |
| `neg_lo` | [40:48] (byte+5) | modifier |  |
| `cond` | [48:56] (byte+6) | enum | `0x0`=f_eq; `0x2`=f_gt; `0x3`=f_lt; `0x4`=u_gt; `0x5`=u_lt; `0x6`=s_gt; `0x7`=s_lt |
| `cache` | [56:64] (byte+7) | modifier |  |
| `mark0` | [64:72] (byte+8) | modifier |  |
| `sel_marker` | [72:80] (byte+9) | modifier |  |
| `sel_operand` | [80:88] (byte+10) | register |  |
| `tail` | [88:112] (byte+11) | modifier |  |

*d = (a <cond> b) ? K1 : K0 ; integer/float compare feeding a select (14B). srcA=byte+3. cmpmode (byte+4): 0x22 relational, 0x26 equality (OWN-MSL k_icmpx: a==b flips 0x22->0x26). cond (byte+6): signed/uint/float x lt/gt (OWN-MSL: a>b 0x07->0x06, uint a<b 0x07->0x05). BODY (byte+7..+13): cache (byte+7, 0xc0 default), mark0/sel_marker (byte+8,+9 = 0x20/0x80 select-source markers), sel_operand (byte+10 = the second select/compare operand register, the byte that varies most corpus-wide), tail (byte+11..+13 = scoreboard). The body stayed byte-invariant under boolean-compare (?1:0) toggles; register-select variation needs splice for the operand map.*

## Conversions / pack

### `cvt_f2i` — float/half -> int/uint convert (round to zero)

- **Length:** 10 bytes  ·  **Match:** byte+0==0x27, byte+1==0x07  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `mode` | [16:24] (byte+2) | modifier |  |
| `dst` | [24:32] (byte+3) | register |  |
| `src_class` | [32:40] (byte+4) | modifier |  |
| `src` | [40:48] (byte+5) | register |  |
| `cvtop` | [48:56] (byte+6) | opcode-select | `0xb4`=f2int |
| `signflag` | [56:64] (byte+7) | modifier |  |
| `dst_class` | [64:72] (byte+8) | modifier |  |
| `b9` | [72:80] (byte+9) | modifier |  |

*d = (int|uint)(a)  ; float/half -> integer convert, round toward zero (truncation). byte+7 bit6 (0x40) = signed (int) vs unsigned (uint). byte+3 = dst reg (dst<<1), byte+5 = src reg (src<<2) -- BOTH byte-diff PROVEN (EXP-M4-13 R9) by a reversed-lane float4<->int4 chain: byte+3 steps 0,2,4,6 with the RESULT lane while byte+5 steps 0x18,0x14,0x10,0x0c with the SOURCE lane (the two move in opposite directions, so dst and src are separately located). byte+2 = result-routing/source-cache mode (same field as the byte+1==0x17 sibling cvt_i2f_src: 0x54 result-consumed-by-following-ALU vs 0x56 standalone). byte+4 = source format/class descriptor; byte+8 = dest format/width descriptor; byte+9 = reserved 0x00. Mode/class exact per-VALUE maps are role-typed (byte-diff located), not independently splice-proven (no fabricated value map).*

### `cvt_i2f` — int/uint -> float/half convert

- **Length:** 8 bytes  ·  **Match:** byte+0==0xa7, byte+1==0x07  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `mode` | [16:24] (byte+2) | modifier |  |
| `dst` | [24:32] (byte+3) | register |  |
| `src_class` | [32:40] (byte+4) | modifier |  |
| `src` | [40:48] (byte+5) | register |  |
| `cvtop` | [48:56] (byte+6) | opcode-select | `0xac`=int2f[32->32]; `0xa0`=i2f[16->16]; `0xa4`=i2f[16->32]; `0xa8`=i2f[32->16]; `0xb4`=i2f[8->32]; `0x8e`=i2f[sibling] |
| `signflag` | [56:64] (byte+7) | modifier |  |

*d = float(a)  ; integer/uint -> float convert (round to nearest even). byte+7 bit6 (0x40) = signed source (i2f) vs unsigned (u2f). byte+3 = dst reg (dst<<1), byte+5 = src reg (src<<2) -- BOTH byte-diff PROVEN (EXP-M4-13 R9) by a reversed-lane int4->float4 chain: byte+3 steps 0,2,4,6 with the RESULT lane while byte+5 steps 0x18,0x14,0x10,0x0c with the SOURCE lane (opposite directions => the two operands are separately located). byte+2 = result-routing/source-cache mode (0x54 result-consumed vs 0x56 standalone, same field as sibling cvt_i2f_src); byte+4 = source format/class descriptor. Mode/class role-typed (located), no fabricated per-value map.*

### `mov_zext16` — 16-bit zero-extend / narrow move

- **Length:** 4 bytes  ·  **Match:** byte+0==0x13  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `src_reg` | [8:15] (byte+1) | register |  |
| `src_flag` | [15:16] | modifier | `0x0`=gpr; `0x1`=uniform/class |
| `subform` | [16:24] (byte+2) | modifier |  |
| `extend` | [24:32] (byte+3) | modifier |  |

*d(r1) = a & 0xFFFF  ; 16-bit ZERO-extend / narrow move (uint -> ushort -> uint keeps the low halfword). byte0==0x13 fixed (dst r1 form of the 0x?3 16-bit narrow family). EXP-M4-13 R8 own-MSL byte-diff: byte+1 = source register descriptor (bits0-6 reg, bit7 = uniform/special-file flag; role follows the reg_move_cb sibling where byte+1=src is PROVEN, corroborated by the corpus n=596 byte+1 46-distinct spread). byte+2 = source-class / size sub-form selector (35-distinct). byte+3 = zero-extend-width / companion descriptor: 0x01 is the low-16 ZERO-extend companion (u2us). NEGATIVE controls proving byte+3 encodes the ZERO-extend (not a generic narrow): SIGN-extend short->int does NOT use 0x13 (lowers to an iadd/bfe sign path, k_s2ss `9f01560002000008 1303`); 8-bit narrow uchar does NOT use 0x13 (lowers to ilogic AND 0xff, k_u2uc `0b011fff...`). Per-value subform/extend maps partial (needs-splice for the non-0x01 companions).*

### `pack_convert` — pack_float_to_unorm/snorm2x16 (compute)

- **Length:** 10 bytes  ·  **Match:** byte+0==0x97, byte+2==0x56  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `src_desc` | [8:16] (byte+1) | modifier |  |
| `fmt_class` | [16:24] (byte+2) | raw/unmapped |  |
| `src` | [24:32] (byte+3) | register |  |
| `mode` | [32:40] (byte+4) | modifier |  |
| `fmt_word` | [40:80] (byte+5) | raw/unmapped |  |

*packed format-conversion pack: pack_float_to_unorm2x16 / snorm / half -> a 32-bit packed word (COMPUTE, gated by byte+2==0x56). src_desc (byte+1) = source/mode descriptor. src (byte+3) = source GPR. mode (byte+4) = mode/size (0x02/0x03). fmt_word (byte+5..+9) = the format-conversion / rounding descriptor -- kept raw (n=4; not individually decoded).*

### `unpack_convert` — unpack_unorm/snorm2x16_to_float (compute)

- **Length:** 8 bytes  ·  **Match:** byte+0==0x17, bits[8:12]==0x4, bits[16:17]==0x0, bits[18:24]==0x15  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `src_class` | [8:16] (byte+1) | raw/unmapped |  |
| `cache` | [16:24] (byte+2) | modifier | `0x56`=fresh; `0x54`=cache/last-use |
| `convert_desc` | [24:56] (byte+3) | raw/unmapped |  |
| `size` | [56:60] (byte+7) | modifier |  |
| `reg_sel` | [60:64] | register |  |

*packed format UNPACK/convert: unpack_unorm2x16_to_float / snorm -> a float2. byte0 0x17, 8 bytes. src_class (byte+1, low nibble 0x04 fixed by match). cache (byte+2) bit1 = source cache / last-use hint (0x56 fresh vs 0x54 cache/last-use, EXP-0038). convert_desc (byte+3..+6) = the format-conversion descriptor -- kept raw. byte+7: low nibble (size) = a size/const (0xa typical); high nibble (reg_sel) = a register selector, most likely the unpack RESULT destination -- it steps e/b/c/a/6/3 across successive unpacks in one kernel (role inferred, not splice-confirmed). Distinguished from simd_ballot (byte+1 low nibble != 4) by the match.*

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
| `srcA` | [8:16] (byte+1) | register |  |
| `op_base` | [16:17] (byte+2) | enum | `0x0`=xor-base; `0x1`=and/or-base |
| `srcB` | [24:32] (byte+3) | register |  |
| `lut_a` | [32:40] (byte+4) | modifier |  |
| `lut_b` | [40:48] (byte+5) | modifier |  |
| `z6` | [48:56] (byte+6) | raw/unmapped |  |
| `outmod` | [56:64] (byte+7) | modifier | `0x80`=output/store |
| `z8` | [64:72] (byte+8) | raw/unmapped |  |
| `z9` | [72:80] (byte+9) | raw/unmapped |  |

*d = LUT2(a, b) ; 2-input bitwise logic (all 16 boolean functions). srcA (byte+1) / srcB (byte+3) = the two source register descriptors (srcA at the falu srcA position, srcB at byte+3). op_base (byte+2 bit0) picks the xor vs and/or base; lut_a (byte+4 low bits) and lut_b (byte+5 bit3) are the per-source / output inverts -> any of the 16 LUT2 functions. outmod (byte+7) bit7 = an output/store flag (set for the store-consumed forms, clear for the compare-consumed dec2 forms). z6/z8/z9 = zero tail. ~a is the fmov(0x0e) op with an invert.*

## Move / special register

### `get_sr` — read a special register (thread/threadgroup/simd IDs, dims, VS/FS)

- **Length:** 4 bytes  ·  **Match:** bits[0:3]==0x4  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `form` | [3:4] | modifier |  |
| `dst` | [4:8] | register |  |
| `sr_sel` | [8:16] (byte+1) | enum | `0x82`=thread_index_in_simdgroup (simd_lane_id); `0x84`=simd_is_helper_thread (FS); `0x85`=simdgroup_index_in_threadgroup (simd_group_id); `0x88`=base_vertex (VS); `0x8a`=base_instance (VS); `0x98`=threads_per_threadgroup.x; `0x99`=threads_per_threadgroup.y; `0x9a`=threads_per_threadgroup.z; `0x9c`=threadgroup_position_in_grid.x; `0x9d`=threadgroup_position_in_grid.y; `0x9e`=threadgroup_position_in_grid.z; `0xa0`=thread_position_in_grid.x (FS: pixel x); `0xa1`=thread_position_in_grid.y (FS: pixel y); `0xa2`=thread_position_in_grid.z; `0xa4`=thread_position_in_threadgroup.x; `0xa5`=thread_position_in_threadgroup.y; `0xa6`=thread_position_in_threadgroup.z; `0xa7`=thread_index_in_threadgroup; `0xa8`=threadgroups_per_grid.x; `0xa9`=threadgroups_per_grid.y; `0xaa`=threadgroups_per_grid.z; `0xc5`=front_facing (FS); `0xd8`=instance_id (VS); `0xdd`=vertex_id (VS/FS-interp); `0x95`=compute SR (atomic/subgroup/threadgroup kernels; needs isolation); `0xe0`=mesh-stage SR (mesh shaders only; needs isolation); `0xe1`=mesh-stage SR (mesh shaders only; needs isolation) |
| `dp_width` | [16:24] (byte+2) | modifier | `0x10`=std 32-bit read (dst<r64); `0x50`=top dst bank (dst>=r64); `0x11`=bool/helper-thread read (inferred); `0x14`=lane-id datapath (inferred) |
| `dp_marker` | [24:29] (byte+3) | modifier |  |
| `dst_hi` | [29:32] | register |  |

*d[dst] = special_register[sr_sel]  ; read a built-in/special register (thread/threadgroup/simd IDs & dimensions; VS vertex_id/instance_id/base_*; FS position/front_facing) into a GPR. sr_sel = BYTE1 is the SR number (NOT byte0-hi, which is the dst GPR LOW nibble). The full destination register is dst = byte0[4:8] | (byte+3[5:8] << 4), reaching r0..r127 -- dst_hi (byte+3 bits5-7) is the register EXTENSION. byte0 low-3-bits = 0b100; bit3 (form) is a datapath/width modifier (set for the position-in-grid SR family) that does not change the SR select. byte+2 (dp_width) is a datapath width / dst-bank descriptor. byte+3 low 5 bits are a fixed 32-bit-read marker (0x06). IDs are read on demand -- no stage preloads them into GPRs. Constant-folded builtins (e.g. threads_per_simdgroup=32) use the 2-byte mov_imm instead.*

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
| `reserved` | [8:32] (byte+1) | immediate |  |

*conventional program-end word (whole body of an empty kernel). NOT a strictly-enforced terminator and NOT parameterized: the 24-bit body is RESERVED PAD -- HW-proven non-load-bearing (corrupting any of it is a no-op, EXP-0003/EXP-0010 E4). A driver emits 0x000000. The true end-of-program is out-of-band (the metadata code length), not this in-band token. There is NO scope/mask/wait operand: the 'end-of-program flags/scope' hypothesis is DISPROVEN by the EXP-0010 E4 splice-inertness result. Typed `imm` (reserved pad) because the bits are fully LOCATED and their role is fully KNOWN (inert padding); the rare nonzero corpus bodies are trailing-padding / mid-stream context words, not a decoded field.*

## Memory access

### `device_load` — load (device / threadgroup / constant)

- **Length:** 14 bytes  ·  **Match:** byte+0==0x67  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `space` | [8:16] (byte+1) | modifier |  |
| `addr_mode` | [16:24] (byte+2) | enum | `0x44`=indexed_load (base+index; terminal/standalone); `0x54`=base_rel_load (non-terminal of a base-sharing group / GPR index); `0x4`=rare CF form; `0x24`=rare CF form (loop_nested); `0x22`=rare RT form (rt_query_params); `0x46`=rare CF form (call_fptr) |
| `extmode` | [24:32] (byte+3) | modifier |  |
| `base_slot` | [32:40] (byte+4) | immediate |  |
| `index_reg` | [40:48] (byte+5) | register |  |
| `access_desc` | [48:56] (byte+6) | modifier | `0x20`=device/global buffer (bit5); `0x0`=threadgroup/other |
| `reserved7` | [56:64] (byte+7) | modifier |  |
| `ld_format` | [64:70] (byte+8) | enum | `0x11`=32-bit scalar (1x u32/i32/f32); `0x1`=16-bit scalar (1x u16/i16/f16); `0x21`=8-bit scalar (1x u8/i8); `0x19`=2x 32-bit (u64 / .xy 32-bit vec2); `0x1d`=3x 32-bit (.xyz 32-bit vec3); `0x17`=4x 32-bit (.xyzw 32-bit vec4); `0x7`=4x 16-bit (.xyzw 16-bit vec4) |
| `dst_lo` | [70:72] | register |  |
| `dst_ext9` | [72:79] (byte+9) | register |  |
| `idx_off` | [79:90] | immediate |  |
| `ldform_hi11` | [90:96] | modifier |  |
| `elem_size` | [96:104] (byte+12) | immediate |  |
| `reserved13` | [104:112] (byte+13) | modifier |  |

*load a vector into destination register dst = dst_lo | (dst_ext9 << 2) from the address space selected by `space` (+1 bit1: 0=device/constant, 1=threadgroup) at (index_reg + idx_off) * unit, base = buffer[base_slot] (+4). DEST REGISTER: byte+8 bits[6:8] = dst[0:2], byte+9 (dst_ext9) = dst[2:9] (register extension) -- together reach r0..r511. byte+8 bits[0:6] (ld_format) = the load data-format descriptor factoring as {bits[4:6]=element size (00=16b,01=32b,10=8b), bits[1:4]=vector-component code, bit0=valid}. +12 elem_size = the total-access-size code (bits[1:4]: 1=1B,2=2B,3=4B,4=8B,0=16B). ELEMENT addressing: +5 index_reg = the GPR holding the array index (RT-1a-FIX: NOT `count` -- sweeping +5 selects which GPR feeds the index; +6 is INERT). idx_off = the in-instruction additive IMMEDIATE element offset (RT-1a-FIX: +9 bit7=+1, +10=+2/unit, +11 low bits=+512/unit). Sub-32 signed types are sign-extended by a following ALU shift; unsigned use the zero-extend load.  [CORRECTED 2026-08-28 -- EXP-M4-13's dst FORMULA IS WRONG] dst = dst_lo | (dst_ext9<<2), used by every prior experiment and by this DB, PREDICTS THE WRONG REGISTER. The register a later falu2/falu2i must reference is extmode/2, i.e. extmode = 2 x target_register (EXP-0101, HW-VALIDATED across target registers 3/7/16/20 and both ALU forms, with 11/11 compiler-emitted load->ALU pairs independently confirming). dst_lo/dst_ext9 are a SEPARATE, independently required field that must be copied VERBATIM from a compiler-observed value ((1,1) for terminal scalar 32-bit loads) and never derived from the target register -- 4 adversarial cases break the load if derived, even with extmode correct. This mis-formula, not the consumer route, was the true cause of EXP-0099's ROUTE_LOAD failure. Target register aliases r(R mod 64) for R in [64,112] and faults at 126/127 (EXP-0112).*

### `device_store` — store (device / threadgroup)

- **Length:** 14 bytes  ·  **Match:** byte+0==0xe7  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `space` | [8:16] (byte+1) | modifier |  |
| `addr_mode` | [16:24] (byte+2) | enum | `0x54`=store (ALU-computed data / base-relative); `0x56`=store (direct live load-result data; bit1 set); `0x64`=store (mesh/extended); `0x4`=rare form; `0x24`=rare form |
| `extmode` | [24:32] (byte+3) | modifier |  |
| `base_slot` | [32:40] (byte+4) | immediate |  |
| `index_reg` | [40:48] (byte+5) | register |  |
| `access_desc` | [48:56] (byte+6) | modifier | `0x21`=device/global store (bit5 device | bit0 store-dir); `0x20`=device (bit5); `0x0`=threadgroup/other; `0x80`=extended |
| `reserved7` | [56:64] (byte+7) | modifier |  |
| `st_format` | [64:72] (byte+8) | enum | `0x11`=32-bit scalar (1x u32/i32/f32); `0x1`=16-bit scalar (1x u16/i16/f16); `0x21`=8-bit scalar (1x u8/i8); `0x19`=2x 32-bit (u64 / 32-bit vec2); `0x1d`=3x 32-bit (32-bit vec3); `0x17`=4x 32-bit (32-bit vec4) |
| `st_format_ext` | [72:79] (byte+9) | modifier |  |
| `idx_off` | [79:90] | immediate |  |
| `st_desc_hi` | [90:96] | modifier |  |
| `elem_size` | [96:104] (byte+12) | immediate |  |
| `reserved13` | [104:112] (byte+13) | modifier |  |

*store a vector to the address space in `space` (+1 bit1: 1=threadgroup) at (index_reg + idx_off) * unit, base = buffer[base_slot] (+4). Element addressing shared with device_load (RT-1a-FIX: +5 = index GPR, NOT `count`; +6 INERT; idx_off = the additive immediate element offset). DATA REGISTER IS NOT IN THIS INSTRUCTION: byte+8/+9 encode the store DATA FORMAT, not the source register -- an 8-live-value store sweep (st_livedata/st_regsweep) with the data provably in registers r0/r1/r2/r3/r4/r5 leaves +8/+9/+11 byte-identical, so the value register is supplied implicitly by the preceding op / amode (+2 0x54=ALU-computed vs 0x56=direct load-result). st_format (+8) mirrors device_load ld_format (same code per element type). st_format_ext (+9, bit set only for the 3-component store) and st_desc_hi (+11 bits[2:8]) are the store data-format descriptor tail; +12 elem_size is the store size descriptor.  [CORRECTED 2026-08-28] extmode = 2 x (source GPR) for ALU-forwarded stores (EXP-0090/0101) -- the same mechanism as the load side. idx_off is a FIXED 16-byte unit for store versus a fixed 4-byte unit for load (EXP-0082), and threadgroup-space store idx_off is likewise x16 while load is element-scaled x4 (EXP-0100). addr_mode bit1, at the same literal 0x54/0x56 position as falu2's lifetime bit, is INERT here (EXP-0119).*

### `vary_store` — vertex varying / [[position]] store to the UVS/parameter buffer

- **Length:** 8 bytes  ·  **Match:** byte+0==0x57  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `hint1` | [8:16] (byte+1) | modifier |  |
| `hint2` | [16:24] (byte+2) | modifier |  |
| `src` | [24:32] (byte+3) | register |  |
| `out_slot` | [32:40] (byte+4) | immediate |  |
| `out_slot_hi` | [40:41] (byte+5) | immediate |  |
| `b5_tag` | [41:48] | immediate |  |
| `hint6` | [48:56] (byte+6) | modifier |  |
| `b7` | [56:64] (byte+7) | modifier |  |

*uvs_buffer[slot] = reg[src]  ; VERTEX-stage store of a [[position]] component or a user varying to the UVS / vertex-parameter buffer the fragment stage interpolates from (the FS 0x2f iter op reads these coefficients, EXP-0029). Memory-family opcode (byte0 0x57, low-nibble 7, sibling of 0x67 load / 0xe7 store / 0xd7 texture-write). byte+3 = SOURCE GPR (reg<<1: an in-order 0,2,4,..,14 sequence over r0..r7 in a per-component store run). OUTPUT SLOT = out_slot(byte+4 bits[5:8]) | (out_slot_hi(byte+5 bit0) << 3): [[position]].xyzw = slots 0-3 (byte+4 0x00/0x20/0x40/0x60), user varyings at slots 4-7 (0x80/0xa0/0xc0/0xe0), and slots 8-15 wrap byte+4 back through 0x00 with byte+5 bit0 set. ONE op per scalar component. byte+5 bits[1:8] are a constant 0x20 tag. byte+2 (hint2) carries the same 0x54/0x55/0x56 data-source mode as the device_store amode. Mesh/object stages emit via the 0xe7 device store (EXP-0030); 0x57 is the traditional-VS path.  [MIS-TOKENIZATION FLAGGED 2026-08-28] The fragment kill/target-mask SUBMISSION op (byte0=0x57, byte+2=0x54, 6 bytes; byte+4 bits[4:0] a source-register select where 0x00 reads the real mask and any other tested value kills the fragment on colour+depth+occlusion together) is currently MIS-TOKENIZED BY THIS DESCRIPTOR as an 8-byte vertex-stage vary_store -- an opcode collision of the same shape EXP-0029 fixed elsewhere (EXP-0091). Mask width is exactly rasterSampleCount bits; excess bits are silently inert to 0xFFFFFFFF and never fault. NOTE the correction from EXP-0093: the accompanying `07 02 54 01` / `87 02 54 01` bracket is the ORDINARY UNCONDITIONAL FRAGMENT EPILOG, NOT a kill/mask companion as EXP-0091 first reported. A proper split of this collision is a pending DB change.*

## Atomics

### `atomic_rmw` — device atomic RMW (elected-lane, op at byte+12)

- **Length:** 14 bytes  ·  **Match:** byte+0==0x67, byte+1==0x11  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `amode` | [16:24] (byte+2) | modifier |  |
| `rsv3` | [24:32] (byte+3) | modifier |  |
| `base_slot` | [32:40] (byte+4) | immediate |  |
| `index_reg` | [40:48] (byte+5) | register |  |
| `addr_desc` | [48:56] (byte+6) | modifier |  |
| `ret_flag` | [56:64] (byte+7) | modifier |  |
| `ret_desc` | [64:72] (byte+8) | modifier |  |
| `idx_off` | [72:80] (byte+9) | modifier |  |
| `rsv10` | [80:88] (byte+10) | modifier |  |
| `rsv11` | [88:96] (byte+11) | modifier |  |
| `op_lsb` | [96:97] (byte+12) | modifier |  |
| `op` | [97:102] | opcode-select | `0x10`=add; `0x11`=and; `0x12`=cmpxchg; `0x13`=fadd; `0x14`=smax; `0x15`=smin; `0x16`=or; `0x1b`=sub; `0x1c`=umax; `0x1d`=umin; `0x1e`=xchg; `0x1f`=xor |
| `per_lane` | [102:103] | modifier |  |
| `op_msb` | [103:104] | modifier |  |
| `amode_hi` | [104:112] (byte+13) | modifier |  |

*atomic read-modify-write to a device buffer. The OP is a 5-bit selector at byte+12 bits[1:6] (start 97): 16 add, 17 and, 18 cmpxchg, 19 fadd, 20 smax, 21 smin, 22 or, 27 sub, 28 umax, 29 umin, 30 xchg (also atomic_store, discards result), 31 xor -- the SAME 5-bit op enum used by atomic_tg (bits[86:91]) and by atomic_mem (byte+12 bits[1:6]). byte+12 bit6 (per_lane) = 1 for a divergent per-lane address (&o[i]), 0 for a uniform address (&o[0]); byte+13 bit1 tracks the same choice. byte+1==0x11 selects the ALU/reduced/immediate-operand form (bit4) in the device space (bit1=0); the register-operand form is atomic_mem (byte+1==0x01). byte+5 = per-lane index GPR (zeroed for a uniform address). byte+7 bit0 = discard/no-writeback; byte+8 = return-register descriptor. The actual RMW operand register is implicit (supplied by the preceding op / amode), as in the 0x67/0xe7 load/store family. Emitted AFTER a SIMD-group simd_reduce pre-combine; NOT a CAS/retry loop.*

### `atomic_mem` — standalone atomic (exchange/cmpxchg/indexed)

- **Length:** 14 bytes  ·  **Match:** byte+0==0x67, byte+1==0x01  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `amode` | [16:24] (byte+2) | modifier |  |
| `rsv3` | [24:32] (byte+3) | modifier |  |
| `base_slot` | [32:40] (byte+4) | immediate |  |
| `index_reg` | [40:48] (byte+5) | register |  |
| `addr_desc` | [48:56] (byte+6) | modifier |  |
| `ret_flag` | [56:64] (byte+7) | modifier |  |
| `ret_desc` | [64:72] (byte+8) | modifier |  |
| `idx_off` | [72:80] (byte+9) | modifier |  |
| `rsv10` | [80:88] (byte+10) | modifier |  |
| `rsv11` | [88:96] (byte+11) | modifier |  |
| `op_lsb` | [96:97] (byte+12) | modifier |  |
| `op` | [97:102] | opcode-select | `0x10`=add; `0x11`=and; `0x12`=cmpxchg; `0x13`=fadd; `0x14`=smax; `0x15`=smin; `0x16`=or; `0x1b`=sub; `0x1c`=umax; `0x1d`=umin; `0x1e`=xchg; `0x1f`=xor |
| `per_lane` | [102:103] | modifier |  |
| `op_msb` | [103:104] | modifier |  |
| `amode_hi` | [104:112] (byte+13) | modifier |  |

*atomic memory op with a DIRECT register-value operand (byte+1==0x01, bit4 clear; device space, bit1 clear). Identical field layout to atomic_rmw (byte+1==0x11); the only match difference is byte+1 (0x01 register-operand vs 0x11 ALU/reduced/immediate-operand). The OP is the SAME 5-bit selector at byte+12 bits[1:6] (start 97): 16 add ... 30 xchg (also atomic_store, discards result) ... 31 xor. Emitted for atomic_store, atomic_exchange, per-lane fetch_* with a divergent address, and compare_exchange (op 18; the returned old value feeds a following icmp, NO hardware retry loop). byte+5 = per-lane index GPR; byte+7 bit0 = discard; byte+8 = return-register descriptor; the RMW operand register is implicit (supplied by the preceding op), as in the 0x67/0xe7 load/store family.*

## Texture / sampler

### `tex_sample` — sample/gather/read/compare/LOD-query bundle

- **Length:** 14 bytes  ·  **Match:** bits[0:3]==0x5, bits[12:16]==0x8, byte+2==0x0c  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `kind` | [0:4] (byte+0) | modifier |  |
| `chain` | [4:8] | modifier |  |
| `comp_flags` | [8:12] (byte+1) | modifier |  |
| `result_desc` | [24:32] (byte+3) | modifier | `0xa0`=scalar/compare/clamped-LOD (0xa0); `0xa4`=gather comp0=r (0xa4); `0xa8`=unclamped-LOD (0xa8); `0xac`=gather comp1=g (0xac); `0xb4`=gather comp2=b (0xb4); `0xb8`=vec4 (full sample/read 0xb8); `0xbc`=gather comp3=a (0xbc) |
| `result_sel` | [32:40] (byte+4) | register |  |
| `coord` | [40:48] (byte+5) | register |  |
| `variant` | [48:56] (byte+6) | opcode-select | `0x0`=sample|gather; `0x1`=sample|gather+offset; `0x3`=read 2D-array (const layer; op+3=(layer<<3)|3); `0x4`=sample_grad; `0x5`=sample 2D (implicit-LOD / bias base); `0x7`=sample_bias; `0x9`=sample_lod|array-sample; `0x13`=cube sample; `0x17`=read 2D; `0x1b`=sample_lod+offset; `0x20`=sample_compare|gather_compare; `0x21`=sample_compare+offset; `0x29`=sample_compare level; `0x33`=sample_compare (gradient/deriv-LOD); `0x37`=read cube (face=coord imm (face<<1)@main+0x09); `0x39`=3D sample; `0x3b`=sample_compare_lod+offset; `0x53`=cube-array sample; `0x79`=read 3D; `0x80`=read MSAA; `0x97`=read 2D-array (bit7=array); `0x9c`=read 3D (coord-register addressing); `0xa0`=read 1D (tex1d); `0xc3`=read cube-array (face imm; op+3=(array<<3)|3); `0xd9`=read MSAA (per-sample index) |
| `extra_coord` | [56:64] (byte+7) | register |  |
| `tex_slot` | [64:72] (byte+8) | immediate |  |
| `samp_slot_offset` | [72:80] (byte+9) | immediate |  |
| `mode` | [80:88] (byte+10) | modifier | `0x0`=gather/read/sample_compare; `0x10`=filtered sample; `0x20`=LOD query |
| `lod_present` | [88:96] (byte+11) | modifier |  |
| `tex_type` | [96:104] (byte+12) | enum | `0x1`=2D-class (2d/1d/cube/2d_array/ms/depth); `0x2`=3D (volumetric; carries a 3rd coordinate); `0x3`=buffer (linear texel buffer) |
| `samp_extra` | [104:112] (byte+13) | modifier |  |

*Texture sample/gather/read/compare/LOD-query bundle: a 4-byte companion (low-nibble 5 sample/gather/read, 0xd compute sample_compare) + a 10-byte sampler op. variant (op+2) selects operation/dimension/LOD-mode; op+2 bit5(0x20)=DEPTH-COMPARE (compareValue CMP sampledDepth; all 8 compareFuncs HW-validated; linear filter => native 2x2 hardware PCF), bit0(0x01)=const texel offset present. companion byte+3 = result descriptor: bit2(0x04)=GATHER, bits[3:5]=gather component r/g/b/a. op+6 = mode (0x10 filtered / 0x00 gather/read/compare / 0x20 LOD-query). tex_slot=op+4 (bit7=index bit), sampler slot + const offset in op+5. LOD/bias/grad and the depth-compare reference are register operands set up by preceding ALU. Same op in compute and fragment; implicit LOD needs a fragment stage.  [CORRECTED 2026-08-28] The bundle's op+4 byte is NOT a stable per-texture binding ID: textures declared at indices 5, 50 and 100 produce op4_sequence [0,128,0], i.e. it is a COMPILER-REUSED REGISTER/UNIFORM SLOT (EXP-0114). The field itself is 4 BITS (the byte's upper nibble) with the lower nibble PROVABLY INERT (12/12 constructed values); all 14 unpopulated nibble values were constructed and every one yields a deterministic SILENT ZERO, never a fault or alias. The true 0-127 binding-index selector lives in a still-UNDECODED PRECEDING POINTER-LOAD instruction. Gather offset is a signed [-8,7] per-axis field, HW-confirmed affine and alias-free at all 12 boundary/corner points and accepting a genuinely dynamic per-lane offset (EXP-0106).*

### `tex_write` — texture write (memory-family store)

- **Length:** 16 bytes  ·  **Match:** byte+0==0xd7  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `coord_pack` | [8:16] (byte+1) | register |  |
| `amode` | [16:24] (byte+2) | modifier |  |
| `seq_idx` | [24:32] (byte+3) | modifier |  |
| `layer_reg` | [32:40] (byte+4) | register |  |
| `coord_regs` | [40:64] (byte+5) | register |  |
| `rsv8` | [64:72] (byte+8) | modifier |  |
| `coord_dim` | [72:80] (byte+9) | enum | `0x4`=2 coords (2d / 2d_array); `0x8`=3 coords (3d); `0xc`=cube |
| `rsv10` | [80:88] (byte+10) | modifier |  |
| `rsv11` | [88:96] (byte+11) | modifier |  |
| `wop` | [96:104] (byte+12) | opcode-select | `0x88`=texture write |
| `data_desc` | [104:112] (byte+13) | modifier |  |
| `data_desc_hi` | [112:120] (byte+14) | modifier |  |
| `rsv15` | [120:128] (byte+15) | modifier |  |

*texture[slot].write(color, coord). Memory-family store (byte0 0xd7, low-nibble 7, sibling of the 0x67/0xe7 buffer load/store). Distinct from the sampler-path read: writes go through the store path, reads through the sample op. byte+9 = coordinate dimensionality (0x04 for a 2-coordinate 2d/2d_array write, 0x08 for a 3d write, 0x0c for a cube write); byte+4 = the extra-coordinate operand register (the array layer / cube face; 0x20 present for an array/layer store, 0 for a plain 2d/3d store); byte+1/+5..+7 = the coordinate/data operand register pack; byte+12 low nibble = a per-texture-op write-sequence index (0x88 base + N for the Nth write in a shader); byte+13/+14 = the write-data (color) source-register descriptor (0x3a/0x09 for a contiguous vec4 register block, 0xfa/0x08 when the four components are assembled from scattered sources). The write-data REGISTER itself is implicit / carried by these descriptors, matching the device_store finding that the store DATA register is not a standalone field. TEXTURE SLOT is NOT in this instruction (writing to texture 0/1/2 is byte-identical) -- it is bound via texture state, resolved outside this op. Fragment or compute.*

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
| `dst_lo` | [4:8] | register |  |
| `b1` | [8:16] (byte+1) | modifier |  |
| `subop` | [16:24] (byte+2) | opcode-select | `0x2f`=setup/modifier(2f) |
| `srcA` | [24:32] (byte+3) | register |  |
| `form` | [32:40] (byte+4) | enum | `0x42`=attribute-fetch/coord-address; `0x0`=float-modifier; `0x10`=bitfield/shift-prep; `0x12`=float-modifier(hi); `0x22`=float-modifier(merge) |
| `b5` | [40:48] (byte+5) | modifier |  |
| `b6` | [48:56] (byte+6) | modifier |  |
| `idx` | [56:64] (byte+7) | modifier |  |
| `b8` | [64:72] (byte+8) | modifier |  |
| `b9` | [72:80] (byte+9) | modifier |  |

*texture COORDINATE / LOD / gather-offset SETUP ALU (byte0 low-nibble 0x0b, 10 bytes, byte+2 in {0x27,0x2f}, tail `.. 00 42 00 00 0X 00 00`). Computes the texel address / normalized cube-face-or-array coordinate / explicit-LOD or bias / const gather offset that the following tex_sample (0xb0/0x90) sampler op consumes as its coordinate/LOD register operands. Emitted 1..N per sample. (The 0x27 byte+2 form gets the same length but is not separately named here; the descriptor matches the 0x2f coord/interp form.) EXP-M4-13 R7 CORRECTION: this 10-byte byte+2==0x2f op is POLYMORPHIC and NOT texture-specific -- across the own corpus it appears as (a) vertex attribute-fetch / varying destination-address setup (byte+4==0x42; byte+7 = dst-slot index = dst<<2) and (b) a float-classify / modifier ALU (isnan/isnormal/frexp/modf; byte+3 = srcA, byte+4 in {0x00,0x10,0x12,0x22}). The mnemonic is retained for stability but is a misnomer.*

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

- **Length:** 6 bytes  ·  **Match:** bits[0:4]==0xa  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst_pred` | [4:8] | register |  |
| `srcA` | [8:15] (byte+1) | register |  |
| `neg` | [15:16] | modifier |  |
| `cmpmode` | [16:20] (byte+2) | enum | `0x2`=relational(lt/gt); `0x3`=equality(eq/ne) |
| `opdesc_hi` | [20:24] | modifier |  |
| `srcB` | [24:32] (byte+3) | register |  |
| `cond` | [32:40] (byte+4) | enum | `0x0`=f_eq; `0x2`=f_gt; `0x3`=f_lt; `0x4`=u_gt; `0x5`=u_lt; `0x6`=s_gt; `0x7`=s_lt; `0x14`=u_gt|imm; `0x15`=u_lt|imm; `0x16`=s_gt|imm; `0x17`=s_lt|imm |
| `opclass` | [40:48] (byte+5) | modifier |  |

*predicate[dst_pred] = (srcA <cond> srcB) ; integer/float compare that sets a per-lane predicate register feeding a divergent block (early return / break / continue / if). byte0 hi nibble = destination predicate register. cond (byte+4) low 3 bits encode [type: float(0x0x)/uint(0x4-5)/sint(0x6-7)][direction: gt even/lt odd] EXACTLY like the 14-byte icmpsel byte+6 map; cond bit4 (0x10) flags the compact-immediate operand form. cmpmode (byte+2 low nibble): 0x2 relational, 0x3 equality. neg (byte+1 bit7) negates the result for le/ge/ne. srcB (byte+3) is a register (opclass byte+5==0xc0) or an immediate bound (opclass==0xc2, bit1 set). NOTE: the match is family-level (byte0 low nibble == 0xa, length 6) and also catches sibling 6-byte low-nibble-a ops that reuse the byte+2/byte+4 slots as opcode/operand bytes (corpus byte+4 values outside the cond map, e.g. 0x22/0x26); the cond/cmpmode semantics above hold for the integer/float compare-predicate subset (cond in 0x00-0x07 and the 0x14-0x17 immediate forms), which is the dominant use.*

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
| `flag` | [8:16] (byte+1) | modifier |  |
| `mode` | [16:24] (byte+2) | modifier |  |
| `sel` | [24:32] (byte+3) | modifier |  |

*d = pred ? A : B ; branchless conditional select (4B, grid-position ternary form). body split by located role: flag (byte+1, {0x00,0x02} size/predicate flag), mode (byte+2, {0x20,0x80} select mode), sel (byte+3, 0x80 select marker default + operand nibble {0x12,0x24,..}). Dominant corpus form 05 00 20 80. Role-typed 'mod'; the per-operand register map needs splice (own MSL ternaries fold to isel10, so psel was not single-toggle reproducible).*

### `jump` — PC-relative jump (loop back-edge)

- **Length:** 10 bytes  ·  **Match:** byte+0==0x0f, byte+1==0x00  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `branch_ctrl` | [16:24] (byte+2) | modifier |  |
| `offset` | [24:72] (byte+3) | immediate |  |
| `link` | [72:80] (byte+9) | modifier |  |

*PC-relative jump; offset is a signed 48-bit little-endian byte displacement (backward for loop back-edges). Taken while lanes remain active (execution-mask loop). byte+2 (branch_ctrl) = the branch/execution-mask FORM selector: 0x54 = the unconditional all-lane back-edge (645/646 corpus jumps + every own-MSL loop back-edge); a single corpus jump uses 0x64. byte+9 (link) = a reserved link/annul slot, const 0x00 across all 646 corpus jumps and all own-MSL loops -- never set for a plain loop back-edge (a genuine subroutine link uses the separate `call`).*

### `frame_marker` — call-site / frame-setup marker (before every CALL)

- **Length:** 4 bytes  ·  **Match:** byte+0==0x43  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `srcA_reg` | [8:15] (byte+1) | register |  |
| `srcA_uni` | [15:16] | modifier | `0x0`=gpr; `0x1`=uniform/hi |
| `subform` | [16:24] (byte+2) | modifier |  |
| `companion` | [24:32] (byte+3) | modifier | `0x1`=zext_hi_zero / pre-call frame marker (43 00 00 01) |

*byte0 0x43 is the dst=r4 member of the low-nibble-3 compact MOVE / zero-extend / half-pack family (identical field layout to n3_mov; dst r4 is fixed by the matched byte0). TWO roles share the encoding: (1) CALL-SITE / FRAME-SETUP marker -- the special form `43 00 00 01` (srcA=0, subform=0x00, companion=0x01 = the SAME `X3 00 00 01` zero-extend-companion shape as mov_zext16 `13 00 00 01`) is emitted immediately before every out-of-line CALL; `43 00 06 xx` is the non-leaf-frame prologue. In object/mesh stages this marker precedes the compiler helper-subroutine calls (write_childcount/write_uvb) -- NOT a mesh-emit op (set_vertex/index/primitive lower to ordinary 0xe7/0xd7 stores, EXP-0030). (2) ORDINARY COMPACT MOVE into r4 -- the general byte+1/+2/+3 forms (e.g. `43 a6 21 00`, `43 08 0e c1`, `43 0a 07 9f`) are register moves: srcA_reg (byte+1 bits0-6) = source register, srcA_uni (byte+1 bit7) = uniform-file/high-half flag, subform (byte+2) = source-class/size sub-form, companion (byte+3) = second-operand/pack descriptor -- the same fields, values and neighbour ops (reg_move / rt_ray_mem / sr_read_wide) as n3_mov to other dst regs.*

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
| `linkmode` | [8:16] (byte+1) | enum | `0x2`=leaf; `0x4`=cf_merge; `0x5`=cf_merge_push; `0x12`=nonleaf_restore_link |
| `scoreboard` | [24:32] (byte+3) | modifier |  |

*function RETURN / CF merge: `8f <lm> 54 <sb>` (4B). linkmode (byte+1): 0x02 leaf return, 0x12 non-leaf, 0x04/0x05 CF merge/reconvergence. scoreboard (byte+3, was raw 'tail'): execution/scoreboard-wait mask -- located, values {0x22,0x26,0x02,0x06,0x2a} (bit5 0x20 = wait-set present, bit2 0x04 = second-slot). No branch target (address is the HW link/CF stack). Role-typed 'mod'; exact scoreboard-slot map needs splice.*

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
| `subop` | [8:16] (byte+1) | modifier |  |
| `marker` | [16:24] (byte+2) | modifier |  |
| `frame_size` | [24:48] (byte+3) | immediate |  |

*NON-LEAF FUNCTION FRAME PROLOGUE. `6f 03 04 00 00 20` (6 bytes; the broader corpus also shows `6f 03 54 00 00 10`). Emitted at the entry of a NON-leaf callee (one that itself CALLs) to establish the per-thread SCRATCH frame in which it saves/restores its return/link register around each inner call. Leaf callees have no prologue and return via `8f 02 54 00`; a non-leaf callee has this prologue, brackets each nested CALL with the 8-byte 0x07 link save/restore, and returns via `8f 12 54 00`. HW-VALIDATED (splice, A18 EXP-M4-14, own-MSL frame.metal k_chain->mid()): subop (byte+1) is the frame sub-op selector -- only bits[1:0]==0b11 are load-bearing (0x03/0x0b/0x13/0x23/0x43 all run; 0x00/0x01/0x02/0x04 fault), bits[7:2] don't-care/reserved. marker (byte+2) is RESERVED/inert (0x04->0x00/0x54/0x55/0xff all run to baseline; corpus shows 0x04 and 0x54). frame_size (bytes+3/+4/+5, little-endian, +5 low byte) is the scratch frame/allocation size: high bytes +3/+4 must be 0 for these small frames (nonzero -> huge frame -> GPU fault); byte+5 is 16B-granular (0x20->0x30 over-alloc tolerated, 0x10/0x1f/0x21 too small/misaligned -> fault). NB byte+5 sub-encoding is not cleanly monotonic (0x40 faults while 0x30 runs), so its sub-field layout is not fully resolved -- see hypotheses. MERGES the DB's former separate b3/b4/frame_size raw fields.*

### `link_save_restore` — link-register save/restore around a nested call

- **Length:** 8 bytes  ·  **Match:** byte+0==0x07, byte+1==0x00, byte+2==0x54, byte+4==0x81  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | modifier |  |
| `marker` | [16:24] (byte+2) | modifier |  |
| `b3` | [24:32] (byte+3) | modifier |  |
| `scope` | [32:40] (byte+4) | modifier |  |
| `dir_offset` | [40:56] (byte+5) | immediate |  |
| `reserved7` | [56:64] (byte+7) | modifier |  |

*LINK-REGISTER SAVE / RESTORE around a nested call in a non-leaf frame. save (before each CALL) = `07 00 54 00 81 00 00 00`; restore (after each CALL) = `07 00 54 00 81 ff 1f 00` (8 bytes). Same 0x07 fence/ordering family as the compute threadgroup_barrier (EXP-0025) and fragment pixel_order (EXP-0029), but an 8-byte form gated by byte+1==0x00 (the barrier/pixel-order forms are 6 bytes, byte+1 in {0x04,0x14}). A non-leaf callee spills its own link register because each inner CALL clobbers the hardware link register (ret 0x8f encodes no return target). HW-VALIDATED (splice, A18 EXP-M4-14, own-MSL frame.metal): in a RACE-FREE frame (k_chain, no spills) the op is a NO-OP fence and every payload field is inert; in a SPILLING frame (k_bigframe / bigmid, 12 live temporaries around the call) the fields become load-bearing. byte0=0x07 is the fence-family opcode (0x07->0x00 corrupts the SAVE / HANGs the RESTORE when state actually spills). scope (byte+4=0x81) = scratch/stack scope: bit7 AND bit0 must both be set (0x81/0x83 pass; 0x00/0x80/0x01 corrupt; 0xff -> GPU page-fault; RESTORE-side corruption HANGs). dir_offset (bytes+5/+6, 16-bit LE) = scratch save/restore offset+direction: SAVE=0x0000, RESTORE=0x1fff; intermediate values relocate the scratch access (corruption scales with value). CORRECTION: dir_offset is 16-bit (bytes+5/+6), NOT the DB's former 24-bit field -- byte+7 (reserved7) is RESERVED/inert on BOTH the SAVE and RESTORE instances. marker (byte+2) and b3 (byte+3) are RESERVED/inert; b1 (byte+1) is mostly reserved (low bits inert, only 0xff perturbs).*

### `spill_frame_marker` — four-byte 0x60 form (historical name; exact role unresolved)

- **Length:** 4 bytes  ·  **Match:** byte+0==0x60  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | raw/unmapped |  |
| `b2` | [16:24] (byte+2) | raw/unmapped |  |
| `b3` | [24:32] (byte+3) | raw/unmapped |  |

*4-byte 0x60 form historically named spill_frame_marker after its position following entry get_sr in one prior A18 high-pressure kernel. Runtime-inert for that computation in our splice test (byte0/+1/+2 sweeps are no-ops); byte+3 is the only live byte (0xff faults). EXP-0041 found the exact word absent from nine retained M4 own mains, including 208--576 B declared scratch, so it is not a universal spill marker. Exact role unresolved. The descriptor preserves its validated four-byte tokenization.*

## SIMD-group / quad

### `simd_reduce` — SIMD/quad reduce & prefix-scan

- **Length:** 8 bytes  ·  **Match:** bits[0:3]==0x7, bits[4:6]==0x3, bits[16:17]==0x0, bits[18:24]==0x15  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `scope` | [3:4] | enum | `0x0`=quad; `0x1`=simd |
| `b0hi` | [6:7] | modifier |  |
| `opcls` | [7:8] | modifier |  |
| `cache` | [17:18] | modifier |  |
| `op` | [8:16] (byte+1) | opcode-select | `0x0`=ior/iand; `0x1`=isum/ixor; `0x2`=smax/smin; `0x3`=umax/umin; `0x4`=f16prod/f16sum; `0x5`=fmin; `0x6`=f32prod/f32sum; `0x7`=fmax |
| `dst` | [24:32] (byte+3) | register |  |
| `opmarker` | [32:40] (byte+4) | modifier |  |
| `src` | [40:48] (byte+5) | register |  |
| `shape` | [48:56] (byte+6) | modifier |  |
| `dtype` | [56:64] (byte+7) | enum | `0x3`=i32_reduce; `0x7`=s32_minmax; `0x8`=f16_reduce; `0x9`=i32_incl_scan; `0xb`=i32_excl_scan; `0x10`=f16_incl_scan; `0x12`=f32_reduce; `0x13`=f16_minmax; `0x18`=f16_excl_scan; `0x22`=f32_incl_scan; `0x32`=f32_excl_scan |

*d = simd/quad reduce or prefix-scan of src over the SIMD-group (scope=1) or 2x2 quad (scope=0). op (byte+1) + dtype (byte+7) select operation+datatype (HW-VALIDATED EXP-0018/O2D). REGISTER CORRECTION (EXP-M4-13 R10 own-MSL byte-diff, k_regtog red4): the operand registers are dst (byte+3, reg<<1) and src (byte+5, reg<<2) -- a 4-way live-reduce chain steps byte+3 = 0x0c,0x0a,0x06,0x02 (dst lane, <<1) and byte+5 = 0x18,0x14,0x0c,0x04 (src lane, <<2). byte+4 (opmarker, was labelled 'src') is a CONSTANT op-marker (0x02 in every own compile), NOT the source register. shape (byte+6). op-select/dtype HW-validated; register positions OWN-MSL located.*

### `simd_shuffle` — SIMD/quad shuffle / broadcast

- **Length:** 10 bytes  ·  **Match:** bits[0:7]==0x47, bits[16:17]==0x0, bits[18:24]==0x15  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dir` | [7:8] | enum | `0x0`=bcast/up; `0x1`=xor/down |
| `mode` | [8:16] (byte+1) | enum | `0x0`=quad; `0x1`=quad_updown; `0x4`=simd; `0x5`=simd_updown; `0x6`=simd_rotate/fill; `0x8`=quad_frag; `0x10`=quad_dyn; `0x14`=simd_dyn; `0x15`=simd_updown_dyn |
| `cache` | [17:18] | modifier |  |
| `dst` | [24:32] (byte+3) | register |  |
| `src` | [32:40] (byte+4) | register |  |
| `srctype` | [40:48] (byte+5) | modifier |  |
| `lane` | [48:56] (byte+6) | immediate |  |
| `rtype` | [56:64] (byte+7) | modifier |  |
| `dsthi` | [64:72] (byte+8) | register |  |
| `rsv9` | [72:80] (byte+9) | modifier |  |

*d = src read from another lane. byte0 0x47=broadcast/shuffle-up/fill_up, 0xc7=shuffle-xor/shuffle-down/fill_down (bit7=direction). byte+1 mode: 0x04 SIMD, 0x00 quad, 0x05 simd_updown, 0x06 rotate/shuffle_and_fill. byte+3=dst reg, byte+4=src reg, byte+5=src width/type, byte+6=lane index/xor mask (index<<1), byte+7=result width marker, byte+8=dst reg high, byte+9=reserved/rotate-tail. R9 typed the former b3/b5/tail raw region (40 bits/occ).*

### `simd_ballot` — SIMD ballot / vote mask source

- **Length:** 10 bytes  ·  **Match:** byte+0==0x17, bits[8:12]==0x7  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `pred` | [12:16] | enum | `0x0`=active_mask/any/all; `0x1`=ballot(predicate) |
| `cache` | [16:24] (byte+2) | modifier |  |
| `dst` | [24:32] (byte+3) | register |  |
| `psrc` | [32:40] (byte+4) | register |  |
| `psrctype` | [40:48] (byte+5) | modifier |  |
| `form` | [48:56] (byte+6) | modifier |  |
| `form_sig` | [56:80] (byte+7) | modifier |  |

*produces the SIMD-group ballot / vote mask (per-lane boolean -> 32-bit mask). byte+1 low nibble 0x7 = family; hi nibble (pred): 0x07 = simd_active_threads_mask / simd_any / simd_all, 0x17 = simd_ballot(predicate). byte+2 cache/marker; byte+3 = dest mask reg; byte+4 = predicate source reg; byte+5 = predicate operand type; byte+6..+9 = form/mask-format tail. R8 typed the former 64-bit raw body.*

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

- **Length:** 14 bytes  ·  **Match:** byte+0==0xdf  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `sub_space` | [8:16] (byte+1) | enum | `0x2`=as_load; `0x12`=as_load_idx1; `0x22`=as_load_idx2 |
| `mode` | [16:24] (byte+2) | enum | `0x54`=amode_54; `0x56`=amode_56; `0x4`=amode_04; `0x81`=amode_81 |
| `dst` | [24:32] (byte+3) | register |  |
| `addr_lo` | [32:40] (byte+4) | register |  |
| `addr_hi` | [40:48] (byte+5) | register |  |
| `flags` | [48:56] (byte+6) | modifier | `0x20`=device/global (bit5); `0x0`=threadgroup/other; `0x80`=extended (bit7); `0xa0`=device+extended |
| `reserved7` | [56:64] (byte+7) | modifier |  |
| `width` | [64:72] (byte+8) | immediate |  |
| `off_lo` | [72:80] (byte+9) | immediate |  |
| `field_off` | [80:88] (byte+10) | immediate |  |
| `off_hi` | [88:96] (byte+11) | immediate |  |
| `elem_size` | [96:104] (byte+12) | immediate |  |
| `reserved13` | [104:112] (byte+13) | modifier |  |

*Dedicated acceleration-structure / ray-data LOAD used during BVH traversal (byte0 0xdf, low-nibble 0xf memory-family sibling of the 0x67/0xe7 buffer load/store and the 0x5f rt_ray_mem; byte+2 == 0x54 memory marker). 14-byte memory-family shape: dst=+3, source address = (addr_lo:+4/addr_hi:+5 register pair) + idx_off(+9 bit7 / +10 field_off / +11 low) scaled by elem_size(+12), addressing/cache mode = +2, width/type = +8, flags = +6. WHICH BVH-node / ray / query-state FIELD is fetched is selected by the immediate offset field_off(+10) -- there is NO per-field opcode. 14-17 per intersector kernel, ~37 in an inline intersection_query.*

### `rt_ray_mem` — ray-data / traversal-stack memory op (payload copy-in/out)

- **Length:** 14 bytes  ·  **Match:** byte+0==0x5f, byte+1==0x02  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `mode` | [16:24] (byte+2) | enum | `0x54`=mem_54; `0x56`=mem_56; `0x4`=mode_04; `0x64`=mode_64 |
| `dst` | [24:32] (byte+3) | register |  |
| `addr_lo` | [32:40] (byte+4) | register |  |
| `addr_hi` | [40:48] (byte+5) | register |  |
| `flags` | [48:56] (byte+6) | modifier | `0x20`=device/global (bit5); `0x0`=threadgroup/other; `0x80`=extended (bit7); `0xa0`=device+extended |
| `reserved7` | [56:64] (byte+7) | modifier |  |
| `width` | [64:72] (byte+8) | immediate |  |
| `off_lo` | [72:80] (byte+9) | immediate |  |
| `field_off` | [80:88] (byte+10) | immediate |  |
| `off_hi` | [88:96] (byte+11) | immediate |  |
| `elem_size` | [96:104] (byte+12) | immediate |  |
| `reserved13` | [104:112] (byte+13) | modifier |  |

*RAY-TRACING ray-data / traversal-stack memory op (byte0 0x5f low-nibble 0xf, byte+1 == 0x02 addressing sub-op, byte+2 == mode). Store/spill + reload side of the 0xdf AS-load: fetches/spills the ray struct (origin/direction/tmin/tmax) + per-node BVH traversal-stack state during the software traversal loop, and carries the ray_data PAYLOAD copy-in/out (count scales with payload size). 14-byte memory-family shape identical to rt_as_load: dst=+3, address = (addr_lo:+4/addr_hi:+5) + idx_off(+9/+10/+11) * elem_size(+12), mode=+2, width=+8, flags=+6. WHICH ray/stack FIELD is read/written is selected by field_off(+10); NO per-field opcode.*

### `rt_transform_test` — ray-vs-node transform / AABB box-test companion

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0x2, byte+2==0x27, byte+3==0x81, byte+4==0x22  ·  **Provenance:** inferred

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `src` | [8:16] (byte+1) | register |  |
| `marker` | [16:24] (byte+2) | opcode-select |  |
| `subop` | [24:32] (byte+3) | opcode-select |  |
| `cmpmode` | [32:40] (byte+4) | opcode-select |  |
| `opA` | [40:48] (byte+5) | register |  |
| `opAmod` | [48:56] (byte+6) | modifier |  |
| `opAflags` | [56:64] (byte+7) | modifier |  |
| `mark2` | [64:72] (byte+8) | opcode-select |  |
| `opB` | [72:80] (byte+9) | register |  |

*RAY-TRACING ray-vs-node coordinate-transform / AABB slab-test companion op executed inside the (software) BVH traversal loop, distinct from the dedicated rt_intersect primitive. byte0 low-nibble 0x2 (hi nibble=result reg); byte+2/+3/+4 = fixed sub-opcode 0x27 0x81 0x22; byte+8 = fixed 0x20 marker. Operands: byte+1 primary source, plus a swapping register PAIR at byte+5(opA)/byte+9(opB), with type/flag bytes at +6/+7. ~4-5 per intersector / ray-query kernel. R9 typed the former marker/subop/cmpmode/body raw region (64 bits/occ). The per-lane transform/slab-test arithmetic sequence itself is intentionally NOT reconstructed (clean-room rule 5).*

### `ray_move` — ray register-marshalling move (also MPP matmul transpose)

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0xb, byte+2==0x81  ·  **Provenance:** inferred

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `src` | [8:16] (byte+1) | register |  |
| `form` | [16:24] (byte+2) | enum | `0x81`=copy_reg(b3=0x08); `0x80`=zero_init(b3=0x00) |
| `b3` | [24:32] (byte+3) | modifier | `0x8`=reg32 plain copy; `0x0`=zero form; `0x12`=uniform/high-class-source copy; `0x22`=uniform/high-class-source copy; `0x6`=zero variant |

*RAY register-marshalling MOVE (4 bytes). byte0 low-nibble 0xb, HIGH nibble = destination register; byte+1 = source register. Marshals the ray fields (origin.xyz / direction.xyz / min_distance / max_distance, and the ray_data payload) into the contiguous register block the rt_intersect op consumes, and moves results out. byte+2 == 0x81 (byte+3 == 0x08) = copy a computed source register; byte+2 == 0x80 (byte+1 == 0x00, byte+3 == 0x00) = zero-initialise a component (e.g. a const origin float3(0,0,0)). A compact move in the 0xNb family (sibling of the compact call-argument move / uniform_mov); disambiguated by byte+2 in {0x80,0x81}. The SAME op is reused (35-38 per kernel) to marshal MPP matmul2d TRANSPOSE tile data -- i.e. matrix transpose is data movement, not a matrix opcode. b3 (byte+3) is an operand type/size/CLASS descriptor (0x08=reg32 plain copy, 0x00=zero, 0x12/0x22=uniform/high-class-source copy, 0x06=zero variant); HW-shown structurally significant (splice, A18 EXP-M4-14: b3 bit6=0x40 on a uniform-class-source copy -> CMDBUF_ERROR; inert on plain copies). NEGATIVE (splice): the b3/src VALUE-semantics could NOT be splice-resolved -- all 16 ray_move ops are INERT to committed_distance in the intersection_query testbed (the traversal re-derives origin/direction from the direct device loads of rin[], so the marshalled ray copy is not its data sink); a getter returning a marshalled ray field is needed to pin the value map (see hypotheses).*

## Barrier / ordering

### `threadgroup_barrier` — threadgroup execution barrier + memory fence

- **Length:** 6 bytes  ·  **Match:** byte+0==0x07, byte+2==0x54  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `sub` | [8:16] (byte+1) | enum | `0x4`=compute threadgroup/execution barrier; `0x2`=fragment tile-access / imageblock-ordering barrier |
| `mem_scope` | [24:32] (byte+3) | enum | `0x41`=mem_none; `0x61`=mem_threadgroup; `0x85`=mem_device; `0x51`=mem_texture; `0xd1`=mem_texture (2nd of pair) |
| `flags` | [32:40] (byte+4) | modifier |  |
| `b5` | [40:48] (byte+5) | immediate |  |

*threadgroup_barrier(mem_flags) -- execution barrier + memory fence. 6 bytes: 07 <sub> 54 <mem_scope> <flags> 00. sub (byte+1): 0x04 = compute threadgroup/execution barrier, 0x02 = fragment tile-access / imageblock-ordering barrier (byte+1==0x00 is the 8-byte link save/restore, lengthed away). mem_scope (byte+3) = fenced memory scope: 0x41 mem_none, 0x61 mem_threadgroup, 0x85 mem_device, 0x51/0xd1 mem_texture (OWN-MSL byte-diff: base 0x41, +0x20 threadgroup, +0x10 texture, device 0x85). flags (byte+4) = memory-class (0x09 tg/none, 0x08 device, 0x0e texture). b5 (byte+5) = reserved pad, const 0x00 (own-MSL + corpus). Makes threadgroup-memory stores by OTHER lanes visible before the barrier returns; the compiler emits it between a threadgroup store and a cross-lane threadgroup load. It is the ONLY explicit ordering/'wait' op in the compute stream (device load/store/atomic/texture are HW-register-interlocked, not scoreboard-waited). simdgroup_barrier emits no 0x07 op (a 32-lane SIMD-group is lockstep). Removing/neutralising the fence -> silent stale threadgroup reads (no fault).  [CORRECTED 2026-08-28] compute threadgroup_barrier(mem_texture) is a GENUINE ACQUIRE (sub=0x14) / RELEASE (sub=0x04) INSTRUCTION PAIR, correcting an earlier provenance note that recorded sub=0x04 for both members (EXP-0093). byte+3 bit0 (0x85 vs 0x84) is the EXECUTION-CONVERGENCE enable, independent of the requested memory-fence class. Separately, simdgroup_barrier compiles byte-identically to no barrier in simple contexts (EXP-0104) but is NOT universally a no-op -- divergent call-count patterns force real branch machinery (EXP-0115).*

### `mem_fence` — device memory fence (atomic_thread_fence, no execution barrier)

- **Length:** 6 bytes  ·  **Match:** byte+0==0x07, byte+2==0x54, byte+3==0x84  ·  **Provenance:** inferred

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `sub` | [8:16] (byte+1) | modifier |  |
| `memclass` | [32:40] (byte+4) | modifier |  |
| `b5` | [40:48] (byte+5) | immediate |  |

*atomic_thread_fence(mem_flags::mem_device, memory_order_seq_cst[, thread_scope_device]) -- a standalone DEVICE-memory ordering fence with no execution barrier. 6 bytes: 07 04 54 84 0a 00. byte+3 == 0x84 = device-memory fence (vs threadgroup_barrier's 0x85 device = 0x84|0x01, the 0x01 being the added EXECUTION barrier); byte+4 == 0x0a = device memory-class flag. Ordering is realised by fence PRESENCE, not a bit on the 0x67 atomic RMW op: memory_order_relaxed emits NO fence, seq_cst emits this fence (acquire/release/acq_rel are REJECTED by MSL). Scope GATES emission: thread/simdgroup/threadgroup scope emit no device fence; thread_scope_device (default) does. The texture fence (mem_texture) is a byte+4==0x06 pair that decodes as pixel_order (same family).*

### `pixel_order` — raster-order-group wait/signal (fragment)

- **Length:** 6 bytes  ·  **Match:** byte+0==0x07, byte+2==0x54, byte+4==0x06  ·  **Provenance:** inferred

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `kind` | [8:16] (byte+1) | enum | `0x4`=release/signal; `0x14`=acquire/wait |
| `scope` | [24:32] (byte+3) | modifier |  |
| `flags` | [32:40] (byte+4) | modifier |  |
| `b5` | [40:48] (byte+5) | modifier |  |

*fragment PIXEL-ORDERING op (raster_order_group / fragment-interlock). kind (byte+1): 0x14 acquire/wait, 0x04 release/signal. scope (byte+3): memory scope {0x50,0xd0} (bit7 differs) -- located mod. flags (byte+4): the raster-order/device fence flag (0x06, coincides with the match constant). b5 (byte+5, constant 0x00). Brackets an ordered RMW of a [[raster_order_group]] resource. Raw bytes retyped raw->mod by located role; scope/flags value map needs splice.*

## Fragment stage

### `iter` — varying interpolation (perspective/linear/W)

- **Length:** 10 bytes  ·  **Match:** bits[0:7]==0x2f, byte+2==0x54, byte+7==0x02  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `grp` | [0:8] (byte+0) | modifier |  |
| `lead` | [8:16] (byte+1) | enum | `0xd`=leading; `0x5`=subsequent |
| `dst` | [24:32] (byte+3) | register |  |
| `coeff_sel` | [32:40] (byte+4) | modifier |  |
| `src_slot` | [40:48] (byte+5) | immediate |  |
| `mode` | [48:56] (byte+6) | enum | `0x0`=center/linear-component; `0x4`=perspective-W-denominator; `0xf`=centroid/sample-W-denominator; `0x14`=centroid/sample-component |
| `c7` | [56:64] (byte+7) | modifier |  |
| `loc` | [64:72] (byte+8) | enum | `0x10`=pixel-center; `0x8`=centroid/sample; `0x9`=centroid/sample-first; `0x0`=mid-component; `0x20`=last-component |
| `b9` | [72:80] (byte+9) | modifier |  |

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
| `store_mode` | [16:24] (byte+2) | modifier |  |
| `src` | [24:32] (byte+3) | register |  |
| `flags` | [32:40] (byte+4) | modifier |  |
| `rt_index` | [40:48] (byte+5) | immediate |  |
| `mask` | [48:56] (byte+6) | modifier |  |
| `fmt` | [56:64] (byte+7) | modifier |  |
| `slice_addr` | [64:96] (byte+8) | modifier |  |

*store a fragment colour output to the tilebuffer / colour attachment. Memory-family store (byte0 0xe7) with the FRAGMENT variant byte+1==0x06 (compute device store is byte+1==0x00, 14 bytes). byte+3 = source colour GPR, byte+5 = render-target index (rt<<1): RT0=0x00, RT1=0x02, RT2=0x04. byte+2 = tile-store addressing MODE (const 0x54, 130/130 corpus). byte+7 (fmt) = the tilebuffer/attachment FORMAT descriptor, byte-diff PROVEN by a color-format sweep of our own single-RT fragment (float4 return, ONLY the pipeline colour-attachment format varied): RGBA8Unorm/sRGB/BGRA8=0x4e, RGBA16Float=0x0e, RGBA32Float=0x2e, R32Float=0x22, R8Unorm=0x42 (the return width was held at float4, so byte+7 tracks the ATTACHMENT format, not the shader vector width -- confirmed: float/float2/float3 returns into an R32Float target all give 0x22). byte+4 (flags) = store flags (0x00 in every plain store; 0x08 appears in the MRT/array-slice variant). byte+6 (mask) = a component/enable descriptor (0x01 in plain stores). byte+8..11 (slice_addr) = an array/layer slice-address block, const 0x00000000 in single-RT stores and carrying the layer/slice address only in array-target stores. Each RT store is bracketed by 0x87 tile-access setup ops; colour values are packed into GPRs by preceding 0x97 ops. discard_fragment suppresses the store.*

### `frag_color_pack` — pack/move colour into output GPR

- **Length:** 10 bytes  ·  **Match:** byte+0==0x97  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `src_desc` | [8:16] (byte+1) | modifier |  |
| `fmt_class` | [16:24] (byte+2) | enum | `0x54`=tilebuffer/attachment; `0x56`=compute_pack |
| `dst` | [24:32] (byte+3) | register |  |
| `mode` | [32:40] (byte+4) | modifier |  |
| `comp_off` | [40:48] (byte+5) | modifier |  |
| `val` | [48:56] (byte+6) | immediate |  |
| `src_present_mask` | [56:64] (byte+7) | modifier | `0x10`=component-0 present (bit4); `0x40`=component-1 present (bit6); `0x20`=suppress component-1 (bit5); `0xd0`=both present (register-source baseline); `0x50`=both present (immediate-source baseline); `0xff`=ILLEGAL -> GPU fault |
| `src_gate_select` | [64:72] (byte+8) | modifier | `0x4`=both-components present gate (bit2); `0x40`=component-0 present gate (bit6) |
| `conv_scale` | [72:80] (byte+9) | modifier | `0x2`=component-1 enable (bit1); `0xc0`=per-component scale/exponent (bits6-7) |

*pack / move a colour value into an output GPR ahead of the tilebuffer store (converts the shader's float/half output to the attachment format). src_desc (byte+1) = source/mode descriptor. fmt_class (byte+2) = 0x54 tilebuffer/attachment (fragment) vs 0x56 compute pack. dst (byte+3) = destination GPR. mode (byte+4) = mode/size (0x02/0x03). comp_off (byte+5) = component / byte-offset selector into the packed word. val (byte+6, HW-VALIDATED) = the colour component value. HW-VALIDATED (splice, A18 EXP-M4-14): the old raw 24-bit fmt_word (byte+7..+9) is NOT an inert attachment-format constant -- it is a LIVE per-component source-present + gate/select + conversion-scale descriptor for the two packed components, SYMMETRIC across both pack ops (pack1=R,G / pack2=B,A). src_present_mask (byte+7) = per-component source-present bitmask (0x10=comp0 only, 0x40=comp1 only, 0xd0/0x50=both present [register/immediate source baseline]; byte+7==0xff is an ILLEGAL encoding that hard-faults the GPU). byte+7 bit7 (0x80) is NON-gating for presence (it correlates with source class reg-vs-imm) and byte+7 bit5 (0x20) suppresses component-1 -- both RESERVED-ish, not independently useful. src_gate_select (byte+8) = per-component present gate + source-component select (bit2=both-present gate, bit6=comp0 gate; the low bits can reroute which source channel feeds a slot -- characterized directionally, not exhaustively bit-typed; no value in the swept range faults). conv_scale (byte+9) = per-component conversion scale/round + enable (bit1=comp1 enable, bits6-7=scale/exponent; extreme values alias/overflow across the 2-wide pair; no value in range faults).*

### `frag_tile_setup` — tile / render-target access setup

- **Length:** 6 bytes  ·  **Match:** byte+0==0x87, byte+2==0x54  ·  **Provenance:** inferred

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | modifier |  |
| `sel` | [24:32] (byte+3) | modifier |  |
| `access` | [32:40] (byte+4) | modifier |  |
| `b5` | [40:48] (byte+5) | modifier |  |

*fragment tile / render-target access setup (6B), emitted around each colour store and tilebuffer read. b1 (byte+1, constant 0x02). sel (byte+3) = per-RT/per-tile selector: steps 0x0c->0x30->0xc0 across RT0/RT1/RT2 (OWN-MSL out_mrt) and 0x00/0x08 around a tile read. access (byte+4) = access mode: 0x06 store-setup vs 0x08 tile-read (OWN-MSL render byte-diff: epilog emits 87 02 54 00 06 then 87 02 54 0c 08). b5 (byte+5, constant 0x00). All bytes located; role-typed 'mod'.*

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

## Other

### `falu2_ext`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x9, bits[17:18]==0x0, bits[18:19]==0x1

### `falu3_ext`

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0x9, bits[17:18]==0x1

### `hminmax`

- **Length:** 6 bytes  ·  **Match:** bits[0:4]==0x2, byte+2==0x1c

### `isel_reg`

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0x2, byte+2==0x2f

### `isel_reg8`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x2, byte+2==0x25

### `n2_op6`

- **Length:** 6 bytes  ·  **Match:** bits[0:4]==0x2

### `jump_cond`

- **Length:** 10 bytes  ·  **Match:** byte+0==0x0f, byte+1==0x01

### `if_push`

- **Length:** 4 bytes  ·  **Match:** byte+0==0x0f, byte+1==0x05

### `pop_reconverge`

- **Length:** 6 bytes  ·  **Match:** byte+0==0x0f, byte+1==0x06

### `mask_op`

- **Length:** 4 bytes  ·  **Match:** byte+0==0x0f, byte+1==0x04

### `rt_ray_mem_ldidx`

- **Length:** 12 bytes  ·  **Match:** byte+0==0x5f, byte+1==0x10, byte+2==0x54

### `rt_ray_mem_short`

- **Length:** 6 bytes  ·  **Match:** byte+0==0x5f, byte+1==0x11, byte+2==0x54

### `scoreboard_fence`

- **Length:** 4 bytes  ·  **Match:** byte+0==0x07, bits[16:17]==0x0

### `frame_marker_compact`

- **Length:** 2 bytes  ·  **Match:** byte+0==0x60

### `cubearray_coord_const`

- **Length:** 4 bytes  ·  **Match:** byte+0==0xf0, byte+1==0xc0, byte+2==0x04

### `tg_addr_compute`

- **Length:** 6 bytes  ·  **Match:** byte+0==0x1c, byte+1==0x02, byte+2==0x00

### `pad_operand`

- **Length:** 2 bytes  ·  **Match:** bits[0:4]==0x0

### `dev_scoreboard_fence`

- **Length:** 4 bytes  ·  **Match:** byte+0==0x80, byte+1==0x02, byte+2==0x00

### `n3_mov`

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0x3

### `n3_addr_prep`

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0x3, byte+2==0x27

### `n3_sample_read`

- **Length:** 10 bytes  ·  **Match:** byte+0==0x03, byte+2==0x26

### `cvt_f2h_dst`

- **Length:** 6 bytes  ·  **Match:** bits[0:4]==0x1, bits[28:32]==0x8

### `cvt_bf16`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x1, byte+3==0x81, byte+4==0x01

### `bf_add_dst`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x1, byte+2==0x1c

### `bf_mul_dst`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x1, byte+2==0x1d

### `bf_fma_dst`

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0x1, byte+2==0x1e

### `sr_read_wide`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x4, bits[15:16]==0x1, byte+3==0x00, bits[16:17]==0x0, bits[17:18]==0x1

### `rt_query_traverse`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0xf, byte+1==0x80, byte+2==0x86, byte+5==0x22, byte+6==0x82

### `fldexp`

- **Length:** 6 bytes  ·  **Match:** bits[0:4]==0xf, byte+1==0x15, byte+2==0x80

### `ibfins`

- **Length:** 12 bytes  ·  **Match:** byte+0==0x27, bits[16:17]==0x0, bits[18:24]==0x15

### `atomic_tg`

- **Length:** 12 bytes  ·  **Match:** byte+0==0x67, byte+1==0x03

### `tile_read_mrt`

- **Length:** 12 bytes  ·  **Match:** byte+0==0x67, byte+1==0x06, byte+2==0x54

### `tex_addr_setup`

- **Length:** 12 bytes  ·  **Match:** byte+0==0x17, bits[16:17]==0x0, bits[18:24]==0x15

### `h_alu_hi`

- **Length:** 6 bytes  ·  **Match:** bits[0:4]==0x8, bits[18:21]==0x7

### `h_alu_hi_ext`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x8, bits[18:21]==0x7

### `h_coord_hi`

- **Length:** 6 bytes  ·  **Match:** bits[0:4]==0x8, bits[16:19]==0x6, bits[21:22]==0x1

### `h_coord_hi_ext`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x8, bits[16:19]==0x6, bits[21:22]==0x1

### `packed_half2_hi`

- **Length:** 6 bytes  ·  **Match:** bits[0:4]==0x8, byte+2==0x24

### `rtq_pred`

- **Length:** 4 bytes  ·  **Match:** byte+0==0x06, byte+1==0xc2, bits[16:32]==0x0

### `sfu_marker`

- **Length:** 2 bytes  ·  **Match:** byte+0==0x06, byte+1==0x02

### `ray_move_copy6`

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0xb, byte+2==0x41

### `ray_move_zero6`

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0xb, byte+2==0x40

### `ray_move_zinit`

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0xb, byte+2==0x80

### `rtq_state_move`

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0xb, byte+2==0x09, byte+3==0x00

### `funary_imm`

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0xb, byte+2==0x0f

### `b_alu10_lo7`

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0xb, bits[16:20]==0x7

### `b_alu10_loe`

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0xb, bits[16:20]==0xe

### `b_alu10_lof`

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0xb, bits[16:20]==0xf

### `reg_move_c0`

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0xb, bits[16:20]==0x0

### `reg_move_c1`

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0xb, bits[16:20]==0x1

### `reg_move_c9`

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0xb, bits[16:20]==0x9

### `reg_move_cb`

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0xb, bits[16:20]==0xb

### `tg_atomic_prep`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0xb, byte+2==0x06

### `b_alu14_c83`

- **Length:** 14 bytes  ·  **Match:** bits[0:4]==0xf, bits[7:8]==0x0, byte+2==0x83

### `if_push_pred`

- **Length:** 4 bytes  ·  **Match:** byte+0==0x0f, bits[8:12]==0x5

### `b_alu14_prep2`

- **Length:** 2 bytes  ·  **Match:** bits[0:4]==0x2, bits[8:9]==0x1

### `int_alu_ehi`

- **Length:** 10 bytes  ·  **Match:** byte+0==0xef, byte+2==0x54, byte+9==0x40

### `vtx_out_pos`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0xb, byte+1==0x00, byte+2==0x26, byte+3==0x00, byte+4==0x40, byte+5==0x00, byte+6==0x00

### `vary_slot`

- **Length:** 4 bytes  ·  **Match:** byte+0==0x00, byte+2==0x40

### `vtx_coord_xform`

- **Length:** 10 bytes  ·  **Match:** byte+0==0x17, byte+2==0xa2, byte+3==0xb0

### `mesh_out_src`

- **Length:** 2 bytes  ·  **Match:** byte+0==0x04

### `isel8`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x2, bits[16:19]==0x7

### `isel10`

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0x2, bits[16:19]==0x7

### `isel10_c`

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0x2, bits[16:19]==0x5

### `n2_compact2`

- **Length:** 2 bytes  ·  **Match:** byte+0==0x02, byte+1==0x00

### `n2_op8`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x2

### `n2_op10`

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0x2

### `cvt_i2f_src`

- **Length:** 8 bytes  ·  **Match:** byte+0==0xa7, byte+1==0x17

### `copysign`

- **Length:** 4 bytes  ·  **Match:** byte+0==0x07, byte+1==0xc2, byte+2==0x88

### `ibfe_mesh_attr`

- **Length:** 12 bytes  ·  **Match:** byte+0==0x27, byte+1==0x00, byte+2==0x66

### `ret_luse`

- **Length:** 4 bytes  ·  **Match:** byte+0==0x8f, byte+2==0x56

### `mem_fence8`

- **Length:** 8 bytes  ·  **Match:** byte+0==0x07, byte+1==0x00, byte+2==0x54, byte+4==0x80

### `rtq_dualsrc`

- **Length:** 12 bytes  ·  **Match:** byte+0==0x17, byte+1==0x02, byte+2==0x00

### `n4_cf_word`

- **Length:** 4 bytes  ·  **Match:** byte+0==0x04, byte+1==0x01, byte+2==0x00

### `n4_rt_word`

- **Length:** 4 bytes  ·  **Match:** byte+0==0x04, byte+2==0x20, byte+3==0x80

### `n1_word`

- **Length:** 2 bytes  ·  **Match:** byte+0==0x01, byte+1==0x00

### `n3_word`

- **Length:** 2 bytes  ·  **Match:** byte+0==0x03, byte+1==0x02

### `falu_compact4`

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0x9

### `falu2_srcmod10`

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0x9, bits[17:18]==0x0, bits[18:19]==0x1

### `falu3_srcmod12`

- **Length:** 12 bytes  ·  **Match:** bits[0:4]==0x9, bits[17:18]==0x1

### `rt_query_traverse2`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0xf, byte+1==0x80, byte+2==0x86

### `half_alu_ext8`

- **Length:** 8 bytes  ·  **Match:** byte+0==0x10

### `half_alu_fma12`

- **Length:** 12 bytes  ·  **Match:** byte+0==0x10

### `falu2_ext8b`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x9, bits[17:18]==0x0, bits[18:19]==0x0

### `falu_srcmod12b`

- **Length:** 12 bytes  ·  **Match:** bits[0:4]==0x9, bits[17:18]==0x0

### `compute_fence_scoped`

- **Length:** 4 bytes  ·  **Match:** byte+0==0x87

### `shift_amt_move`

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0xb, bits[16:20]==0xc

### `reg_move_c2var`

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0xb, bits[20:24]==0x2

### `bf_alu8_var`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x1

### `op04_len8`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x4

### `operand_word_x2_h5`

- **Length:** 2 bytes  ·  **Match:** bits[0:4]==0x2, bits[8:9]==0x1, bits[13:14]==0x1

### `operand_word_x2_h6`

- **Length:** 2 bytes  ·  **Match:** bits[0:4]==0x2, bits[8:9]==0x1, bits[14:15]==0x1

### `operand_word_x2_h7`

- **Length:** 2 bytes  ·  **Match:** bits[0:4]==0x2, bits[8:9]==0x1, bits[15:16]==0x1

### `operand_word_a2_01`

- **Length:** 2 bytes  ·  **Match:** byte+0==0xa2, byte+1==0x01

### `operand_word`

- **Length:** 2 bytes  ·  **Match:** (none)

## Length rule (byte 0)

Parcels are 2 bytes (all lengths even). Length is a function of byte 0 plus a per-group length bit/signature. The authoritative rule is `instr_length()` in `tools/agx-isa/isadb.py`; this table summarizes it:

| byte 0 (group / signature) | length (bytes) |
|---|---|
| `0x0e` | 4 |
| `lownibble_0xC` | 4 |
| `0x67/0xe7` | 14  [load/store: device, threadgroup (byte+1 bit1=0x02) and constant all share this opcode pair -- EXP-0012] |
| `0x07 (+ byte+2==0x54)` | 6  [THREADGROUP/EXECUTION BARRIER (threadgroup_barrier): 07 04 54 <mem_scope> <flags> 00. byte+3 = fenced memory scope 0x61 threadgroup / 0x85 device. The ONLY explicit ordering op in compute -- device load/store/atomic/texture are NOT scoreboard-waited (HW register interlock). EXP-0025 HW/splice-proven] |
| `lownibble_0x9` | 6, or 8 if (byte[+2] & 0x02), or 4 if byte+2 in {0x18,0x38}  [float ALU; byte+2 in {0x18,0x38} = compact 4-byte float accumulate (falu_acc), EXP-0025 / RT-1a-FIX -- NOT a wait; 0x18 vs 0x38 is a source cache/last-use hint. srcB-imm form (bit39=1): byte+1 exp>=8 (bit15=1) = minifloat immediate (falu2i), exp<8 (bit15=0) = UNIFORM-register source (falu2_uni), RT-1a-FIX. byte+2==0x25 (still 6B) = transcendental ESTIMATE SEED (byte0 0x29): byte+3 0x09 rcp / 0x0b rsqrt / 0x0d sqrt estimate, ~8 mantissa bits, the Newton-Raphson seed for precise 1/x/rsqrt/sqrt, EXP-0026] |
| `0x2f/0xaf` | 10  [float SPECIAL-FUNCTION UNIT (SFU): one op computes rcp/rsqrt/exp2 (byte0 0xaf) \| round/sqrt/log2 (byte0 0x2f), function = byte+1 (0x00 rcp\|round / 0x01 rsqrt\|sqrt / 0x02 exp2\|log2). exp/log/pow/div compose these. fast-math emits single ops; precise 1/x/sqrt/div refine with Newton-Raphson. EXP-0013 (exp2/log2/round) + EXP-0026 (rcp/rsqrt/sqrt)] |
| `lownibble_0xB` | 4 if (byte+2==0x01 and byte+3==0x08) [uniform_mov: uniform-reg -> GPR, EXP-0020]; else 10 [float unary / integer and/or/xor] |
| `0x02` | 6  [integer min/max \| compare-for-select] |
| `0x12` | 6 float min/max, or 14 if (byte+2 & 0x0f)==0x0d [int compare] |
| `0x9f/0x1f` | 10 if (byte+1 & 1) else 12  [integer add/sub \| mul-add] |
| `0xa7` | 10 if (byte+1 & 1) else 12  [integer shift-r \| bitfield] |
| `0x27` | 8  [integer unary / popcount] |
| `0x0a` | 6  [integer compare -> execution predicate (branch/return)] |
| `0x05/0x16` | 4  [conditional select (branchless if/ternary)] |
| `0x0f` | EXECUTION-MASK family, byte+1 sub-op (RT-ISA-FIX): 0x00 jump 10 / 0x01 jump_cond(else,loop-guard) 10 / 0x05 if_push 4 (or 14 if byte+4==0x8f = direct CALL) / 0x06 pop_reconverge 6 / 0x80 call_indirect(computed branch) 6 / 0x04 mask_op 4 |
| `0x07 (byte+2 in {0x00,0x02})` | 4  [compute memory/scoreboard fence around calls & divergent CF (07 22 02 00 pre-call; 07 02/00 00 CF). RT-ISA-FIX HW] |
| `lownibble_0x5 + byte+1==0x80 + byte+2==0x0c` | 14  [TEXTURE sample / read: 4B coord/result companion + 10B sampler op (0xb0/0x90). EXP-0016 HW-validated] |
| `0xd7` | 16  [TEXTURE write (memory-family store). EXP-0016 HW-validated] |
| `0x37` | 8 if byte+2==0x56 [quad reduce/scan, EXP-0018]; else 10 [derivative / quad-difference dfdx/dfdy/fwidth, EXP-0016] |
| `0xbf/0x3f/0xb7 (+ byte+2==0x56)` | 8  [SUBGROUP/QUAD reduce & prefix-scan: bit3=scope(1 simd/0 quad), bit7+byte+1=op, byte+7=datatype/shape. SIMD width 32. EXP-0018 HW] |
| `0x47/0xc7` | 10  [SUBGROUP/QUAD shuffle & broadcast: bit7=dir, byte+1=simd/quad/rotate, byte+6=(lane<<1), byte+2 0x54/0x56 (cache bit, RT-ISA-FIX). EXP-0018 HW] |
| `0x17` | 10  [simd_ballot (byte+1 low-nib 7: 0x07 active-mask/any/all, 0x17 ballot(pred), RT-ISA-FIX) \| unpack_convert (byte+1 low-nib 4). EXP-0018/0033 HW] |
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
| `0x60` | 4  [FOUR-BYTE 0x60 FORM (historical name spill_frame_marker): `60 00 00 00` was observed after entry get_sr in one prior A18 high-pressure kernel. Runtime-inert for that computation (byte0/+1/+2 splices no-op), byte+3 live (0xff faults). EXP-0041 found it absent from nine M4 own mains including 208--576 B scratch, so it is not a universal spill marker. Length 4 validated; exact role unresolved] |
| `device_load/store +5 index_reg (RT-1a-FIX)` | +5 is the INDEX GPR that supplies a[idx] (NOT `count`; sweeping +5 selects which GPR feeds the index); +6 is INERT; +1 = address space; the additive IMMEDIATE index-offset lives at +9 bit7 (+1) / +10 (+2/unit) / +11 low (+512/unit). Vector width/count is at +8 (dst_width) / +12 (elem_size). RT-1a-FIX HW-validated. |
| `iadd2 add/sub polarity (RT-1a-FIX)` | byte0 bit7 = ADD(1,0x9f) / SUBTRACT(0,0x1f) select. The DB previously had this INVERTED (labelled every add srcA_neg=1 and gave 0x1f d=srcA+srcB although 0x1f subtracts). Splice 0x9f->0x1f turns 10+20 into 10-20=-10. HW-validated. |
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

*Rendered from `tools/agx-isa/db.json` — 170 descriptors. The machine-readable source of truth is `db.json` / `isadb.py`; this document is its human-readable projection.*
