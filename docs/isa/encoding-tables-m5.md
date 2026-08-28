# M5 (Apple10 / G17g) AGX — Instruction Encoding Tables

> [!IMPORTANT]
> **Scope: Apple M5 (Apple10 / G17g / T8142). NOT evidence for Apple9 (A18 Pro / M4).**
> The M5 workstream is **complete and deferred** (`CLAUDE.md`). Nothing in this file may be
> used to support an A18/G17P or M4/G16G claim, and no value here may be emitted by an Apple9
> driver without being independently established on an Apple9 target. M5 is a G17-family
> *sibling*, not the same device: treat every number as M5-only unless an `EXP-M4-*` or
> `EXP-00NN` experiment says otherwise.

> **Generated** from `tools/agx-isa-m5/db.json` by `tools/agx-isa-m5/gen_encoding_tables.py` (2026-07-13). Regenerate after any DB change; do not hand-edit. This is the **authoritative, self-contained encoding table** a driver author reads to emit M5 (Apple10/G17g) AGX instructions — 194 instruction descriptors.

**Clean-room:** every encoding here was learned from the compiled form of MSL **we wrote** (OWN-SHADER) — by byte-diffing our own shaders and by splicing bytes and running them on the real M5 GPU (hardware validation). No Apple binary was disassembled. See `../../CLAUDE.md`.

## How to read this

- Bit numbering: an *N*-byte instruction is one **little-endian** integer. Bit 0 = bit 0 of byte 0; bit 16 = bit 0 of byte +2; so *byte offset +k, bit b* = bit (8·k + b).
- **Length** is a function of byte 0 (the group) plus a per-group length bit/signature — the first parcel does *not* encode length on G17g. The full length rule is the byte-0 table in the [Length rule](#length-rule-byte-0) appendix and `tools/agx-isa-m5/isadb.py::instr_length`.
- **Match** = the constant bits that identify the instruction. **Fields** = every non-constant bit, with its bit-range, type, and enum values where known.
- Field **type**: `register` · `immediate` · `enum` · `modifier` · `opcode-select` · `raw/unmapped` (byte-diff-localized but not individually bit-decoded).

## Contents

- [M5 Memory Access (G17g split model)](#m5-memory-access-(g17g-split-model))
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

## M5 Memory Access (G17g split model)

### `m5_addr_gen` — address generation: base[slot] + index -> address register (EXP-M5-07)

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0xf, byte+2==0x03  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `addr_reg` | [4:8] | register |  |
| `base_slot` | [8:16] (byte+1) | immediate |  |
| `idx_mode` | [24:32] (byte+3) | enum | `0x2`=auto gid thread-index; `0x0`=no auto-index (index from the load's computed-index reg); `0x4`=vec2 indexed; `0x6`=vec3 indexed; `0x8`=vec4 indexed; `0x18`=store data-forward |

*M5 memory ADDRESS-GENERATION op: computes the effective base address of buffer[base_slot] into a register the following m5_load/m5_store dereferences. byte0 low-nibble 0xf; byte+2==0x03 is the family signature (separates it from the jump, byte+2==0x54). byte0 HIGH nibble = destination address register. byte+1 = BUFFER BASE SLOT << 2 (slot 0=0x00, 1=0x04, 2=0x08, 3=0x0c). byte+3 = index/access mode: 0x02 = the op AUTO-applies the gid thread-index (simple a[gid], the following load has amode==0x22 gid-direct); 0x00 = the op does NOT auto-index -- the index is supplied by the following load's COMPUTED-INDEX register (amode==0x02, index_reg at load byte+5), used for a[idx[gid]] AND a[i+k] (EXP-M5-11: the +k immediate is folded into a preceding m5_alu/m5_iadd add, NOT an addr_gen field -- there is NO immediate-offset field in this op). 0x04/0x06/0x08 = vec2/vec3/vec4 element indexing. Precedes EVERY M5 load(0x18/38/58/78) and store(0x01/21/41/61).*

### `m5_load` — device/threadgroup load, 1-4 component (0x18/38/58/78)

- **Length:** 10 bytes  ·  **Match:** bits[0:5]==0x18, byte+2==0x10  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `ncomp_m1` | [5:7] | immediate |  |
| `amode` | [8:16] (byte+1) | enum | `0x22`=scalar gid-direct; `0x2a`=vector; `0x2`=computed-index |
| `elem_size` | [24:32] (byte+3) | enum | `0xc0`=4-byte / 32-bit stride; `0x80`=16-byte / 128-bit stride; `0xa0`=1-byte / 8-bit stride; `0xe0`=vec2 32-bit |
| `fmt_desc` | [32:40] (byte+4) | modifier |  |
| `index_reg` | [40:48] (byte+5) | register |  |

*M5 device LOAD (terminal 10-byte form). byte0 = 0x18 | ((ncomp-1)<<5): 0x18/0x38/0x58/0x78 = 1/2/3/4-component load. byte+1 (amode) selects the index source: 0x22 = gid-direct (auto thread index, from the preceding m5_addr_gen idx_mode==0x02) with byte+5 INERT; 0x02 = COMPUTED-index -- the load index comes from the GPR at byte+5 (index_reg), and the preceding m5_addr_gen has idx_mode==0x00. byte+2==0x10 is a load-bearing enable. byte+3 (elem_size) sets the ADDRESS STRIDE / element size (HW: 0xc0=4B->a[i], 0x80=16B->a[4i], 0xa0=1B->a[i/4]). byte+4 = load-bearing format/dest descriptor. byte+5 (index_reg) = the ARBITRARY INDEX REGISTER for a[computed]/a[idx[gid]] (0x00 gid/reg0, 0x20 = a loaded index GPR). NOTE (EXP-M5-11): for a CONSTANT offset a[i+k] there is NO immediate-offset field in the load -- the compiler folds i+k into a PRECEDING m5_alu/m5_iadd add (byte0 0x27/0x2f, byte+6==0xa3=add) and this load then uses computed-index mode (amode 0x02). LOAD DEST register is positional (consumed by the following store/ALU); byte+4 carries its format+reg descriptor. The buffer base comes from the preceding m5_addr_gen (no base_slot here).*

### `m5_load_compact` — compact 4-byte load (result feeds an ALU)

- **Length:** 4 bytes  ·  **Match:** bits[0:5]==0x18, byte+2==0x10, byte+3==0x40  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `ncomp_m1` | [5:7] | immediate |  |
| `amode` | [8:16] (byte+1) | modifier |  |

*M5 device LOAD, compact 4-byte NON-TERMINAL form (byte+3==0x40): the load result feeds directly into a following ALU op rather than a store. Same byte0 component encoding as m5_load. Emitted e.g. for a[gid] in out=a[gid]+b[gid] (ld_2sum load#1).*

### `m5_store` — device/threadgroup store, 1-4 component (0x01/21/41/61)

- **Length:** 6 bytes  ·  **Match:** bits[0:5]==0x1, byte+2==0x10  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `ncomp_m1` | [5:7] | immediate |  |
| `dsrc` | [8:16] (byte+1) | modifier |  |
| `st_fmt` | [24:32] (byte+3) | modifier |  |

*M5 device STORE, 6-byte form (byte+2==0x10 store-enable). byte0 = 0x01 | ((ncomp-1)<<5): 0x01/0x21/0x41/0x61 = 1/2/3/4-component store; byte+3 = store format. Names the vec3/vec4 (0x41/0x61) and half-scalar (0x01, byte+3=0x80) 6-byte stores that otherwise byte-collided with the inherited cvt_f2h_dst; a real fp32->fp16 convert has byte+2 in {0x1c,0x3c} and is excluded. Same op as m5_store_ext, higher match specificity so it wins the length-6 tie.*

### `m5_store_ext` — extended store form

- **Length:** 6 bytes  ·  **Match:** bits[0:5]==0x1  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `ncomp_m1` | [5:7] | immediate |  |
| `dsrc` | [8:16] (byte+1) | modifier |  |
| `st_fmt` | [24:32] (byte+3) | modifier |  |

*M5 device STORE, 6-byte load-forwarded / vector form: carries a trailing `00 20` store-data-format word (byte+3 in {0xc0 load-forward, 0x80/0xe0 vector}). Emitted when the stored value is forwarded straight from a preceding m5_load (out=a[gid]) or is a multi-component vector (ld_vec2/3/4 stores 0x21/0x41/0x61).*

## Float ALU

### `falu2` — 2-source float ALU (fadd/fmul), reg-reg

- **Length:** 6 bytes  ·  **Match:** bits[0:4]==0x9  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `srcA_size` | [8:9] (byte+1) | enum | `0x1`=b32; `0x0`=b16 |
| `srcA_reg` | [9:16] | register |  |
| `opsel` | [16:19] (byte+2) | opcode-select | `0x4`=fadd; `0x5`=fmul; `0x6`=fma; `0x7`=fmul_interp |
| `opflags` | [19:24] | modifier |  |
| `srcB_size` | [24:25] (byte+3) | enum | `0x1`=b32; `0x0`=b16 |
| `srcB_reg` | [25:32] | register |  |
| `ctrl` | [32:39] (byte+4) | modifier |  |
| `srcB_imm` | [39:40] | enum | `0x0`=reg; `0x1`=immediate |
| `mod_lo` | [40:43] (byte+5) | modifier |  |
| `srcB_neg` | [43:44] | modifier |  |
| `mod_hi` | [44:48] | modifier |  |

*d = op(srcA, [-]srcB)  ; 2-source float ALU. src operand byte = (reg<<1)|is32 (bit0=size; 7-bit reg field, GPR file = up to 96 addressable 32-bit regs, EXP-0020). dst here is the compact b0[4:8] nibble (r0..r15 only); a high GPR dst uses the 8-byte falu3 form (dst=byte+1, 7-bit) -- HW seen writing r64. srcB negate = bit43. srcB-immediate mode = bit39 (see falu2i). When bit39=1, srcB is NOT a GPR: byte+1's exponent nibble (bits[12:16], = instr bit15 = the 8s bit) SPLITS the two overloads -- exp>=8 (bit15=1) => packed minifloat immediate (falu2i), exp<8 (bit15=0) => UNIFORM-REGISTER source (falu2_uni). RT-1a-FIX HW-validated (supersedes the earlier `byte+2 bit4 / byte+5 bit1` guess, which was wrong).*

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
| `srcA_reg` | [25:32] | register |  |
| `ctrl_lo` | [32:39] (byte+4) | modifier |  |
| `mods` | [40:48] (byte+5) | modifier |  |

*d = op(srcA, K)  ; srcB is the packed non-IEEE float immediate K = imm_decode(b1, sign). exp(bits12:16,bias11) mant(bits9:12) flag(bit8) sign(bit19). Range +-{0,1/32..30}. HW-VALIDATED EXP-0006.*

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

*d = estimate(a) ; low-precision (~7.5-8 mantissa bit) hardware seed for the Newton-Raphson lowering of the precise-path 1/x (subop 0x09), rsqrt (0x0b) and sqrt (0x0d). **Rounding caveat (EXP-0074, 2026-08-27):** "precise" here means the non-fast-math path, NOT proven correctly rounded across all input classes. EXP-0074 showed the sibling precise FP32 divide on this same machinery is bit-exact vs a correctly-rounded reference EXCEPT for DAZ+FTZ (subnormal operands read as zero; subnormal results flush to zero). rcp/rsqrt/sqrt themselves were NOT directly tested for subnormal behavior — treat their subnormal rounding as `UNKNOWN` pending a dedicated probe. byte0 0x29, 6 bytes, byte+2==0x25 discriminator, byte+3 = function. Appears ONLY in the precise (non-fast-math) reciprocal/root lowerings; fast-math uses the single-op SFU (fspecial 0xaf/0x2f) instead.*

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

*d = min/max(a,b) by TYPE (32-bit int signed/unsigned, or float). byte0 hi nibble = dst r0..r15. byte1 = (dst<<1)|size. byte+2 = source-format marker (bits[16:19]==0b110). byte+3 = srcA. byte+4 = OP-SELECT (sel low 3 bits): 0=fmax 1=fmin 4=umax 5=umin 6=imax 7=imin. byte+5 = srcB.*

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

*load a vector into destination register dst = dst_lo | (dst_ext9 << 2) from the address space selected by `space` (+1 bit1: 0=device/constant, 1=threadgroup) at (index_reg + idx_off) * unit, base = buffer[base_slot] (+4). DEST REGISTER: byte+8 bits[6:8] = dst[0:2], byte+9 (dst_ext9) = dst[2:9] (register extension) -- together reach r0..r511. byte+8 bits[0:6] (ld_format) = the load data-format descriptor factoring as {bits[4:6]=element size (00=16b,01=32b,10=8b), bits[1:4]=vector-component code, bit0=valid}. +12 elem_size = the total-access-size code (bits[1:4]: 1=1B,2=2B,3=4B,4=8B,0=16B). ELEMENT addressing: +5 index_reg = the GPR holding the array index (RT-1a-FIX: NOT `count` -- sweeping +5 selects which GPR feeds the index; +6 is INERT). idx_off = the in-instruction additive IMMEDIATE element offset (RT-1a-FIX: +9 bit7=+1, +10=+2/unit, +11 low bits=+512/unit). Sub-32 signed types are sign-extended by a following ALU shift; unsigned use the zero-extend load.*

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

*store a vector to the address space in `space` (+1 bit1: 1=threadgroup) at (index_reg + idx_off) * unit, base = buffer[base_slot] (+4). Element addressing shared with device_load (RT-1a-FIX: +5 = index GPR, NOT `count`; +6 INERT; idx_off = the additive immediate element offset). DATA REGISTER IS NOT IN THIS INSTRUCTION: byte+8/+9 encode the store DATA FORMAT, not the source register -- an 8-live-value store sweep (st_livedata/st_regsweep) with the data provably in registers r0/r1/r2/r3/r4/r5 leaves +8/+9/+11 byte-identical, so the value register is supplied implicitly by the preceding op / amode (+2 0x54=ALU-computed vs 0x56=direct load-result). st_format (+8) mirrors device_load ld_format (same code per element type). st_format_ext (+9, bit set only for the 3-component store) and st_desc_hi (+11 bits[2:8]) are the store data-format descriptor tail; +12 elem_size is the store size descriptor.*

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

*uvs_buffer[slot] = reg[src]  ; VERTEX-stage store of a [[position]] component or a user varying to the UVS / vertex-parameter buffer the fragment stage interpolates from (the FS 0x2f iter op reads these coefficients, EXP-0029). Memory-family opcode (byte0 0x57, low-nibble 7, sibling of 0x67 load / 0xe7 store / 0xd7 texture-write). byte+3 = SOURCE GPR (reg<<1: an in-order 0,2,4,..,14 sequence over r0..r7 in a per-component store run). OUTPUT SLOT = out_slot(byte+4 bits[5:8]) | (out_slot_hi(byte+5 bit0) << 3): [[position]].xyzw = slots 0-3 (byte+4 0x00/0x20/0x40/0x60), user varyings at slots 4-7 (0x80/0xa0/0xc0/0xe0), and slots 8-15 wrap byte+4 back through 0x00 with byte+5 bit0 set. ONE op per scalar component. byte+5 bits[1:8] are a constant 0x20 tag. byte+2 (hint2) carries the same 0x54/0x55/0x56 data-source mode as the device_store amode. Mesh/object stages emit via the 0xe7 device store (EXP-0030); 0x57 is the traditional-VS path.*

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

*atomic read-modify-write to a device buffer. The OP is a 5-bit selector at byte+12 bits[1:6] (start 97): 16 add, 17 and, 18 cmpxchg, 19 fadd, 20 smax, 21 smin, 22 or, 27 sub, 28 umax, 29 umin, 30 xchg (also atomic_store, discards result), 31 xor -- the SAME 5-bit op enum used by atomic_tg (bits[86:91]) and by atomic_mem (byte+12 bits[1:6]). byte+12 bit6 (per_lane) = 1 for a divergent per-lane address (&o[i]), 0 for a uniform address (&o[0]); byte+13 bit1 tracks the same choice. byte+1==0x11 selects the ALU/reduced/immediate-operand form (bit4) in the device space (bit1=0); the register-operand form is atomic_mem (byte+1==0x01). byte+5 = per-lane index GPR (zeroed for a uniform address). byte+7 bit0 = discard/no-writeback; byte+8 = return-register descriptor. The actual RMW operand register is implicit (supplied by the preceding op / amode), as in the 0x67/0xe7 load/store family. Emitted AFTER a SIMD-group simd_reduce pre-combine; NOT a CAS/retry loop. [M5/G17g CAVEAT (EXP-M5-16): the A18 device-atomic 0x67 (byte+1 0x11/0x01) is SUPERSEDED on M5 -- a UNIFORM-address atomic migrates to m5_reduce (simd pre-combine, byte+6 op-selector) and a DIVERGENT per-lane atomic `atomic_fetch_<op>(&buf[gid],x)` to m5_atomic_div / m5_atomic_xchg (`0f 00 03 .. c0 ..`). 0x67/0xe7 still occur on M5 for plain device load/store. See db.json m5_atomic_div / m5_reduce.]*

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

*atomic memory op with a DIRECT register-value operand (byte+1==0x01, bit4 clear; device space, bit1 clear). Identical field layout to atomic_rmw (byte+1==0x11); the only match difference is byte+1 (0x01 register-operand vs 0x11 ALU/reduced/immediate-operand). The OP is the SAME 5-bit selector at byte+12 bits[1:6] (start 97): 16 add ... 30 xchg (also atomic_store, discards result) ... 31 xor. Emitted for atomic_store, atomic_exchange, per-lane fetch_* with a divergent address, and compare_exchange (op 18; the returned old value feeds a following icmp, NO hardware retry loop). byte+5 = per-lane index GPR; byte+7 bit0 = discard; byte+8 = return-register descriptor; the RMW operand register is implicit (supplied by the preceding op), as in the 0x67/0xe7 load/store family. [M5/G17g CAVEAT (EXP-M5-16): A18/G17P register-operand device-atomic form; on M5 a divergent-address atomic lowers to m5_atomic_div / m5_atomic_xchg (`0f 00 03`), a uniform one to m5_reduce -- see db.json.]*

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

*Texture sample/gather/read/compare/LOD-query bundle: a 4-byte companion (low-nibble 5 sample/gather/read, 0xd compute sample_compare) + a 10-byte sampler op. variant (op+2) selects operation/dimension/LOD-mode; op+2 bit5(0x20)=DEPTH-COMPARE (compareValue CMP sampledDepth; all 8 compareFuncs HW-validated; linear filter => native 2x2 hardware PCF), bit0(0x01)=const texel offset present. companion byte+3 = result descriptor: bit2(0x04)=GATHER, bits[3:5]=gather component r/g/b/a. op+6 = mode (0x10 filtered / 0x00 gather/read/compare / 0x20 LOD-query). tex_slot=op+4 (bit7=index bit), sampler slot + const offset in op+5. LOD/bias/grad and the depth-compare reference are register operands set up by preceding ALU. Same op in compute and fragment; implicit LOD needs a fragment stage. [M5/G17g CAVEAT (EXP-M5-16): this is the A18/G17P sample bundle; on M5 the sampling op is SUPERSEDED by the m5_tex / m5_tex_read leaders (`<rr>f <op> {12,1a} <b3> <4X> 80`, 6-byte leader + raw coord/LOD operand words) -- see db.json m5_tex.]*

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

*texture[slot].write(color, coord). Memory-family store (byte0 0xd7, low-nibble 7, sibling of the 0x67/0xe7 buffer load/store). Distinct from the sampler-path read: writes go through the store path, reads through the sample op. byte+9 = coordinate dimensionality (0x04 for a 2-coordinate 2d/2d_array write, 0x08 for a 3d write, 0x0c for a cube write); byte+4 = the extra-coordinate operand register (the array layer / cube face; 0x20 present for an array/layer store, 0 for a plain 2d/3d store); byte+1/+5..+7 = the coordinate/data operand register pack; byte+12 low nibble = a per-texture-op write-sequence index (0x88 base + N for the Nth write in a shader); byte+13/+14 = the write-data (color) source-register descriptor (0x3a/0x09 for a contiguous vec4 register block, 0xfa/0x08 when the four components are assembled from scattered sources). The write-data REGISTER itself is implicit / carried by these descriptors, matching the device_store finding that the store DATA register is not a standalone field. TEXTURE SLOT is NOT in this instruction (writing to texture 0/1/2 is byte-identical) -- it is bound via texture state, resolved outside this op. Fragment or compute. [M5/G17g NOTE (EXP-M5-16): the 0xd7 image-write STILL OCCURS on M5 (19 tp-corpus occurrences, correctly lengthed 16B) -- retained, NOT superseded. In ADDITION, M5 texture-atomic / image-store paths emit a distinct `24 80 03 0a 27 ..` write form (11 own / 2 tp occurrences, EXP-M5-16) whose full length/operand split is OPEN (documented, not yet integrated).]*

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

*direct out-of-line CALL: `0f 05 54 1a 8f 00 56 <off40> 00` (14 B). offset = a SIGNED little-endian PC-relative byte displacement; branch target = (call_addr + 4) + offset. Reuses the execution-mask push (0f 05) machinery -- a masked branch that saves the return context -- so byte+4=0x8f and byte+6=0x56 are the CALL/link signature (also the 14-vs-8-byte disambiguator vs a plain predication push). Bracketed by the 0x43 frame marker (before) and a 0f 06 reconverge (after). Args in r10,r11,r12..; return value in r10; return via ret (0x8f). [M5/G17g CAVEAT (EXP-M5-11 MAJOR-4): this is the A18/G17P direct-call form. INTRA-shader control flow (jump/jump_cond/if_push/reconverge/ret) is confirmed on M5, but the M5 out-of-line CALL ABI (0xef/0xff / linked-function variant) is OPEN -- a visible_function_table caller extracts to a 4-byte stub in the standalone archive (the call resolves at pipeline-link time); isolating it needs a shdump extension that builds a pipeline with linkedFunctions.]*

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

*INDIRECT CALL through a function pointer (visible_function_table / intersection_function_table). Leader `0f 80 ..`: byte+1 0x80 selects the call-to-address variant of the control-flow group (vs 0x00 jump, 0x05 direct call). The target is a CODE VA loaded into a register from the function table (entry[i] = 8-byte code VA of function i's entry point); this op transfers control to it and returns via the same ret (0x8f). Per-lane (dynamic) targets are marshalled through a run of 0x4b move ops before the 0f 80. [M5/G17g CAVEAT (EXP-M5-11 MAJOR-4): A18/G17P indirect-call form; the M5 dynamic-dispatch / linked-function ABI is OPEN (same pipeline-link resolution as the direct call).]*

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

### `spill_frame_marker` — spill/frame-setup marker (after entry get_sr in spilling kernels)

- **Length:** 4 bytes  ·  **Match:** byte+0==0x60  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | raw/unmapped |  |
| `b2` | [16:24] (byte+2) | raw/unmapped |  |
| `b3` | [24:32] (byte+3) | raw/unmapped |  |

*4-byte spill/frame-setup marker emitted right after the entry get_sr in high-register-pressure / SPILLING kernels (byte0 0x60). Runtime-inert for the computation in our splice test (byte0/+1/+2 sweeps are no-ops); byte+3 is the only live byte (0xff faults). Best-understood role: scratch-frame / occupancy setup for the spill path; exact semantics a follow-up. Adding it unblocks tokenization (RT-1a-FIX: without a length rule the tokenizer halted).*

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

*d = a*b (+ c)  ; DEDICATED 8x8 cooperative-matrix multiply-accumulate over the 32-lane SIMD-group. One 0xcf = one full 8x8x8 tile MAC (r[i][j] += sum_k a[i][k]*b[k][j], row-major). OPERAND SELECTORS (all HW-splice-validated, EXP-O2C, on mad_f32 read back over one 32-lane simdgroup): byte+5 = A (LEFT) multiply-operand fragment register (splice +5 to B's reg -> B*B; swap +5/+6 -> B*A -- matmul is non-commutative so all A*B/B*A/A*A/B*B distinguishable); byte+6 = B (RIGHT) operand register; byte+7 = C accumulator source register; byte+8 = destination fragment register; byte+3 = an A-operand sub-descriptor (corrupting -> ZERO result: load-bearing); byte+10 = op-enable marker 0x24 (corrupting -> C passthrough, the multiply drops out); byte+4 and byte+9 bit1 splice-inert (padding). dtype (byte+1): 0x00 = 16-bit (half), 0x02 = 32-bit (float; bfloat shares the 32-bit datapath with input conversion; splicing 0x02->0x00 garbles fp32). mode (byte+2): 0x56 standalone, 0x54 tiled (MPP matmul2d) -- SEMANTIC, not a hint: splicing standalone 0x56->0x54 ZEROES the result (tiled mode sources its accumulator from the MPP tile context). ACCUMULATE-ENABLE = byte+11 bit0 (1 -> a*b+c, 0 -> a*b; simdgroup_multiply clears it). MSL element types: half, float, bfloat (incl. mixed half/bfloat -> float accumulate); integer matrices REJECTED (no int8 cooperative matrix). Only 8x8 exposed. ALL MPP tensor ops (matmul2d multiply/multiply_accumulate/transpose/f32/16x16x16/2-simdgroup) lower to THIS SAME op -- no new tensor opcode; transpose adds 4-byte data-move ops (ray_move family), not a new op; simdgroup_load/store (incl. transpose=true) are ordinary 0x67/0xe7 memory ops. [M5/G17g CAVEAT (EXP-M5-16 / EXP-M5-09): on M5 the simdgroup_matrix MAC DIVERGES off 0xcf to m5_matrix_mac (`2f 00 05 .. 20 <af|ab> .. <accum> ..`, 14B) fed by the `?f ..07..` tile load/store family; 0xcf is RETAINED on M5 only for the TILED MPP tensor_ops::matmul2d path (0xcf still occurs -- 22 own / 44 tp). See db.json m5_matrix_mac.]*

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

*Dedicated acceleration-structure / ray-data LOAD used during BVH traversal (byte0 0xdf, low-nibble 0xf memory-family sibling of the 0x67/0xe7 buffer load/store and the 0x5f rt_ray_mem; byte+2 == 0x54 memory marker). 14-byte memory-family shape: dst=+3, source address = (addr_lo:+4/addr_hi:+5 register pair) + idx_off(+9 bit7 / +10 field_off / +11 low) scaled by elem_size(+12), addressing/cache mode = +2, width/type = +8, flags = +6. WHICH BVH-node / ray / query-state FIELD is fetched is selected by the immediate offset field_off(+10) -- there is NO per-field opcode. 14-17 per intersector kernel, ~37 in an inline intersection_query. [M5/G17g RESOLVED (EXP-M5-19, AS-aware splice vs a real single-triangle AS): rt_intersect (`?4 ea`) SURVIVES and is now splice-confirmed load-bearing on M5 (byte+1 ea=traverse, byte+2 a functional mode, byte+4 the per-lane ray/AS operand). The 0xdf AS-load MIGRATED into the M5 0x?f split-memory family, NOT a distinct opcode: the AS HANDLE is an index-fixed argument/uniform load (`?f 48 43/03 00`, byte+1=0x48) -- the Metal buffer binding index does NOT change the encoding (as_slot1==as_slot3 byte-identical, unlike plain device buffers); ray ORIGIN/DIR ride 0x?f split-memory loads with byte+2 in {0x43,0x83} (byte+1 in {0x10,0x68}), origin-vs-direction separated by ray0-survival splice. byte+2 low-bits 0b11 = family signature, top-2 bits = mode (0x03 addr-gen, 0x43/0x83 load). In-loop BVH-node loads inferred same 0x?f family (past the traversal loop back-edge, not per-op spliced). Faults fully contained (180 splices, 0 reboots). A driver emits RT loads with the general argument-load (AS handle) + split-memory (ray data) forms -- no dedicated 0xdf op on M5. Open: exact 0x83-load sub-field widths, op#2 result-field layout (needs a primitive_id/barycentric kernel).]*

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

*RAY-TRACING ray-data / traversal-stack memory op (byte0 0x5f low-nibble 0xf, byte+1 == 0x02 addressing sub-op, byte+2 == mode). Store/spill + reload side of the 0xdf AS-load: fetches/spills the ray struct (origin/direction/tmin/tmax) + per-node BVH traversal-stack state during the software traversal loop, and carries the ray_data PAYLOAD copy-in/out (count scales with payload size). 14-byte memory-family shape identical to rt_as_load: dst=+3, address = (addr_lo:+4/addr_hi:+5) + idx_off(+9/+10/+11) * elem_size(+12), mode=+2, width=+8, flags=+6. WHICH ray/stack FIELD is read/written is selected by field_off(+10); NO per-field opcode. [M5/G17g CAVEAT (EXP-M5-09): the 0x5f ray-data/traversal-stack leader does NOT survive as a distinct high-frequency op on M5 (0-2/kernel vs 12-28 on A18) -- ray-data spill/reload migrated into the M5 split memory family; exact M5 encoding OPEN (EXP-M5-11 MAJOR-5).]*

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

*threadgroup_barrier(mem_flags) -- execution barrier + memory fence. 6 bytes: 07 <sub> 54 <mem_scope> <flags> 00. sub (byte+1): 0x04 = compute threadgroup/execution barrier, 0x02 = fragment tile-access / imageblock-ordering barrier (byte+1==0x00 is the 8-byte link save/restore, lengthed away). mem_scope (byte+3) = fenced memory scope: 0x41 mem_none, 0x61 mem_threadgroup, 0x85 mem_device, 0x51/0xd1 mem_texture (OWN-MSL byte-diff: base 0x41, +0x20 threadgroup, +0x10 texture, device 0x85). flags (byte+4) = memory-class (0x09 tg/none, 0x08 device, 0x0e texture). b5 (byte+5) = reserved pad, const 0x00 (own-MSL + corpus). Makes threadgroup-memory stores by OTHER lanes visible before the barrier returns; the compiler emits it between a threadgroup store and a cross-lane threadgroup load. It is the ONLY explicit ordering/'wait' op in the compute stream (device load/store/atomic/texture are HW-register-interlocked, not scoreboard-waited). simdgroup_barrier emits no 0x07 op (a 32-lane SIMD-group is lockstep). Removing/neutralising the fence -> silent stale threadgroup reads (no fault).*

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

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x9, bits[17:18]==0x0, bits[18:19]==0x1  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `srcA_size` | [8:9] (byte+1) | enum | `0x0`=b16; `0x1`=b32 |
| `srcA_reg` | [9:16] | register |  |
| `opsel` | [16:19] (byte+2) | opcode-select | `0x4`=fadd; `0x5`=fmul; `0x6`=fma; `0x7`=fmul_interp |
| `opflags` | [19:24] | modifier |  |
| `srcB_size` | [24:25] (byte+3) | enum | `0x0`=b16; `0x1`=b32 |
| `srcB_reg` | [25:32] | register |  |
| `ctrl` | [32:39] (byte+4) | modifier |  |
| `srcB_imm` | [39:40] | modifier |  |
| `mod_lo` | [40:43] (byte+5) | modifier |  |
| `srcB_neg` | [43:44] | modifier |  |
| `mod_hi` | [44:48] | modifier |  |
| `ext_tail` | [48:64] (byte+6) | modifier |  |

*d = saturate?( op(srcA,[+/-]srcB) ) ; 8-byte extended 2-source float ALU. op=opsel (0b100 fadd/0b101 fmul). Tail bytes inherit the HW-validated falu2_srcmod10 layout: ctrl (byte+4 low7), srcB_imm (bit39), mod_lo/srcB_neg/mod_hi (byte+5) -- srcB_neg (bit43, 0x08) = negate srcB (OWN-MSL byte-diff: saturate(a-b) sets byte+5=0x08); ext_tail (byte+6,+7) = the saturate/output-cache tail: byte+7 bit1 (0x02) = SATURATE clamp to [0,1] (OWN-MSL byte-diff: saturate(a+b)/saturate(a*b) set byte+7=0x82), bit7 (0x80) = output cache. Per-bit map beyond srcB_neg/saturate inherited from the srcmod family (needs splice).*

### `falu3_ext`

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0x9, bits[17:18]==0x1  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst_lo` | [4:8] | register |  |
| `dst` | [8:16] (byte+1) | register |  |
| `op` | [16:24] (byte+2) | opcode-select | `0x1e`=fma; `0x36`=fma; `0x26`=fma_coord; `0x2e`=fma_coord; `0x66`=fma; `0x6e`=fma_coord; `0x3e`=fma |
| `srcA` | [24:32] (byte+3) | register |  |
| `srcB` | [32:40] (byte+4) | register |  |
| `srcC` | [40:48] (byte+5) | register |  |
| `ext` | [48:80] (byte+6) | raw/unmapped |  |

*d = saturate?( a*b + c )  ; the 10-byte EXTENDED fma. Same op-select as the 8-byte falu3 (opsel 0b110; dst=byte+1, srcA=byte+3, srcB=byte+4, srcC=byte+5). The 2-byte tail (byte+6..+9) carries the saturate / source modifier; length = EXP-M4-10 `6 + 2*(byte+4 & 3)` with byte+4 low2 == 10. op-select 0x26/0x2e/0x6e are the fused mul-add COORDINATE forms.*

### `hminmax`

- **Length:** 6 bytes  ·  **Match:** bits[0:4]==0x2, byte+2==0x1c  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `dst_full` | [8:16] (byte+1) | register |  |
| `srcA` | [24:32] (byte+3) | register |  |
| `sel` | [32:35] (byte+4) | opcode-select | `0x0`=hmax; `0x1`=hmin |
| `selhi` | [35:40] | modifier |  |
| `srcB` | [40:48] (byte+5) | register |  |

*d = min/max(a,b), 16-bit (half/half2). Identical layout to iminmax but byte+2==0x1c. byte+4 low 3 bits = op-select (0=hmax 1=hmin).*

### `isel_reg`

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0x2, byte+2==0x2f  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `cmpA` | [8:16] (byte+1) | register |  |
| `cmpB` | [24:32] (byte+3) | register |  |
| `cmp_mode` | [32:40] (byte+4) | modifier |  |
| `selTrue` | [40:48] (byte+5) | register |  |
| `cc` | [48:56] (byte+6) | enum | `0x2`=fcmp_gt; `0x3`=fcmp_lt; `0x4`=ucmp_gt; `0x5`=ucmp_lt; `0x6`=scmp_gt; `0x7`=scmp_lt; `0x0`=eq_form |
| `flags` | [56:64] (byte+7) | modifier |  |
| `selFalse_file` | [64:72] (byte+8) | modifier |  |
| `selFalse` | [72:80] (byte+9) | register |  |

*d = (cmpA CC cmpB) ? selTrue : selFalse ; register-operand compare-SELECT, 10-byte form (byte+2==0x2f). Emitted in integer division/modulo correction. Adopts the isel10 field layout (byte+1/+3 = compare sources, byte+4 = compare-mode, byte+5 = selTrue, byte+6 = condition code, byte+7 = flags, byte+8:9 = false-operand word, byte+9 = selFalse register). dst = byte0 high nibble. The division algorithm is NOT reconstructed (rule 5).*

### `isel_reg8`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x2, byte+2==0x25  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `cmpA` | [8:16] (byte+1) | register |  |
| `cmpB` | [24:32] (byte+3) | register |  |
| `cmp_mode` | [32:40] (byte+4) | modifier |  |
| `selTrue` | [40:48] (byte+5) | register |  |
| `cc` | [48:56] (byte+6) | enum | `0x2`=fcmp_gt; `0x3`=fcmp_lt; `0x4`=ucmp_gt; `0x5`=ucmp_lt; `0x6`=scmp_gt; `0x7`=scmp_lt; `0x0`=eq_form |
| `flags` | [56:64] (byte+7) | modifier |  |

*d = (cmpA CC cmpB) ? selTrue : <folded-false> ; register-operand SELECT, 8-byte form (byte+2==0x25, register operands, no trailing false-operand word). Adopts the isel8 field layout: byte+1/+3 = compare sources, byte+4 = compare-mode, byte+5 = selTrue, byte+6 = condition code, byte+7 = flags. dst = byte0 high nibble.*

### `n2_op6`

- **Length:** 6 bytes  ·  **Match:** bits[0:4]==0x2  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `src_desc` | [8:16] (byte+1) | modifier |  |
| `opsel` | [16:24] (byte+2) | enum | `0x0`=compact_select/move; `0x2`=mode2; `0x8`=mode8; `0x10`=mode10; `0x12`=mode12; `0x29`=mode29 |
| `opA` | [24:32] (byte+3) | register |  |
| `opB` | [32:40] (byte+4) | modifier |  |
| `imm_sel` | [40:48] (byte+5) | immediate |  |

*Compact 6-byte low-nibble-2 select/predicate/helper. dst = byte0 high nibble (reg-sweep PROVEN across r0..r15). src_desc (byte+1) = source/mode descriptor (bit7 = uniform/special-file flag). opsel (byte+2) = op/mode selector: 0x00 = compact select/move (dominant), others select the sub-op. imm_sel (byte+6) = trailing small index/immediate -- in the output-write-mask helper family (SPIRV-Cross masking_write_outputs kernels) it steps the mask/location index 0..0xd; in the shuffle-helper family the tail is a lane/mode word; in the transcendental family it is an SFU coefficient/select. opA (byte+3) = the second operand / source-register descriptor (bit7 = uniform/special-file flag, like src_desc; corpus n=1747 shows the bit7-set files 0x80/0x82/0x81 dominant) -- TYPED reg. opB (byte+4) = the compare-mode / operand-mode descriptor (0x2x compare-mode-like values 0x20/0x22/0x24/0x26 dominant, matching the isel8 byte+4 cmp_mode slot; also SFU/shuffle mode words) -- TYPED mod. n2_op6 is a genuine catch-all bucket (write-mask helper + compact select + fcmp-mask + SFU range-reduction select); opA/opB are the two operand/mode SLOTS (located and typed) but their per-sub-op value maps are mixed and needs-splice; the SFU coefficient SEQUENCE is NOT reconstructed (clean-room rule 5).*

### `jump_cond`

- **Length:** 10 bytes  ·  **Match:** byte+0==0x0f, byte+1==0x01  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `cf_scope` | [16:24] (byte+2) | enum | `0x54`=scope54(guard/exit); `0x64`=scope64(else-skip) |
| `offset` | [24:72] (byte+3) | immediate |  |
| `reserved` | [72:80] (byte+9) | modifier |  |

*CONDITIONAL PC-relative jump (masked branch). offset = signed 48-bit little-endian byte displacement; target = jump_addr + 4 + offset (same convention as the 0f 00 unconditional jump). Taken while the divergent execution mask still has active lanes; used for if/else forward skips and while/for loop-exit guards. cf_scope (byte+2) selects the reconvergence mask bank (0x54 / 0x56) the branch condition is drawn from.*

### `if_push`

- **Length:** 4 bytes  ·  **Match:** byte+0==0x0f, byte+1==0x05  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `scope` | [16:24] (byte+2) | enum | `0x54`=mask_bankA(outer/even); `0x56`=mask_bankB(nested/odd) |
| `scope_kind` | [24:32] (byte+3) | enum | `0x1`=cond_skip(if/loop-guard); `0x1a`=loop_iter; `0x5`=cond_skip+b2; `0x21`=cond_skip+b5; `0x25`=cond_skip+b2+b5 |

*execution-mask PUSH: enters a divergent region, saving the reconvergence point and narrowing the active-lane mask. scope (byte+2) selects the reconvergence mask bank -- it ping-pongs 0x54/0x56 with nesting parity (outer even = 0x54, nested odd = 0x56); the low 0x04 form is the inner mask-op variant. scope_kind (byte+3) names the KIND of region: 0x01 for a conditional-skip scope (a plain if / loop-entry guard) and 0x1a for a loop-iteration scope. Paired with a later 0f 06 pop_reconverge. Shares the 0f 05 leader with the direct CALL (14 bytes, 0x8f link at byte+4; disambiguated by length). The predicate-register PUSH variant sets a non-zero byte+1 high nibble (see if_push_pred).*

### `pop_reconverge`

- **Length:** 6 bytes  ·  **Match:** byte+0==0x0f, byte+1==0x06  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `scope` | [16:24] (byte+2) | enum | `0x4`=mask_bankA; `0x24`=mask_bankB |
| `scope_kind` | [24:32] (byte+3) | enum | `0x1`=guard/outermost; `0x2`=loop_body |
| `reserved` | [32:48] (byte+4) | modifier |  |

*execution-mask POP / reconverge: re-enables the lanes masked off by the matching if_push (0f 05) or loop scope, restoring the active mask at a block/loop end. scope_kind (byte+3) names the reconvergence scope popped -- 0x02 for a loop-body scope, 0x01 for the outermost / loop-entry guard scope. Every loop back-edge is immediately followed by a scope_kind 0x02 pop; the final reconverge is 0x01. scope (byte+2) is the mask-bank selector (low 0x04 form).*

### `mask_op`

- **Length:** 4 bytes  ·  **Match:** byte+0==0x0f, byte+1==0x04, byte+3==0x19  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `mask_bank` | [16:24] (byte+2) | enum | `0x4`=mask_bankA; `0x24`=mask_bankB |
| `scope_kind` | [24:32] (byte+3) | modifier |  |

*inner execution-mask op (0f 04 <mask_bank> <scope_kind>, 4 bytes). Appears inside nested divergence just before a 0f 01 jump_cond -- the continue-edge mask narrow / inner-scope re-mask (distinct from if_push 0f 05, byte+2==0x54, by byte+2 low form). mask_bank (byte+2) selects the execution-mask bank: 0x04 = bankA, 0x24 = bankB (0x20 bit = alternate bank), the same low-form mask-bank selector as pop_reconverge's scope field. scope_kind (byte+3) is a fixed scope-kind / level tag == 0x19 in the whole corpus (no observed variation to map a range).*

### `rt_ray_mem_ldidx`

- **Length:** 12 bytes  ·  **Match:** byte+0==0x5f, byte+1==0x10, byte+2==0x54  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `idx_dst` | [24:32] (byte+3) | register |  |
| `rsv4` | [32:40] (byte+4) | modifier |  |
| `addr_mode` | [40:48] (byte+5) | modifier |  |
| `marker` | [48:56] (byte+6) | modifier |  |
| `idx_lo` | [56:64] (byte+7) | register |  |
| `idx_hi` | [64:72] (byte+8) | register |  |
| `wtype` | [72:80] (byte+9) | modifier |  |
| `scale` | [80:88] (byte+10) | modifier |  |
| `rsv11` | [88:96] (byte+11) | modifier |  |

*RAY-TRACING ray-data memory op, load-INDEX variant (12B). byte0 0x5f, byte+1==0x10 (0x67 device-load indexed addressing byte, low nibble 0 = indexed), byte+2==0x54. Computes a per-lane index/address into the traversal/query state from a register pair; WHICH query field is later read is NOT selected here (byte-diff: identical ldidx bytes for instance_id vs geometry_id loads) -- consistent with the R6 rt_ray_mem finding that the field is chosen by an immediate offset, not a per-field opcode. Length 12 (R4): all occurrences back-to-back at gap 12. R9 typed the former 72-bit body raw region.*

### `rt_ray_mem_short`

- **Length:** 6 bytes  ·  **Match:** byte+0==0x5f, byte+1==0x11, byte+2==0x54  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `reg` | [24:32] (byte+3) | register |  |
| `rsv4` | [32:40] (byte+4) | modifier |  |
| `rsv5` | [40:48] (byte+5) | modifier |  |

*RAY-TRACING ray-data memory op, SHORT form (6B). byte0 0x5f, byte+1==0x11 (the 0x67 load index+1 addressing byte), byte+2==0x54, body `<reg> 00 00`. Length 6 (R4): all corpus occurrences sit back-to-back at gap 6. R9 typed the former b3/tail raw region (24 bits/occ).*

### `scoreboard_fence`

- **Length:** 4 bytes  ·  **Match:** byte+0==0x07, bits[16:17]==0x0  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `kind` | [8:16] (byte+1) | enum | `0x0`=CF-edge fence (break/continue); `0x2`=CF-edge fence (variant); `0x22`=pre-call / pre-atomic register+scoreboard fence; `0xc0`=wide/device-order fence (inferred); `0xc2`=wide/device-order fence (inferred) |
| `scope` | [17:24] | enum | `0x1`=ordered (byte+2 0x02: default CF/call scope); `0x0`=unordered (byte+2 0x00); `0x10`=extended scope (byte+2 0x20: nested-divergence); `0x11`=extended+ordered (byte+2 0x22) |
| `mask` | [24:32] (byte+3) | modifier |  |

*compute memory / scoreboard fence (4 bytes): 07 <kind> <scope> <mask>. A short ordering fence the compiler inserts before an out-of-line CALL (`07 22 02 00`, immediately preceding the 43 frame marker) and around break/continue divergence (`07 02 00 00` / `07 00 00 00`). byte+2 in {0x00,0x02} distinguishes it from the 6-byte threadgroup_barrier / mem_fence / pixel_order (byte+2==0x54) of the same 0x07 family. Orders scoreboard/register state across the control-flow edge; NOT a cross-lane threadgroup-memory barrier.*

### `m5_call`

- **Length:** 8 bytes  ·  **Match:** byte+0==0xff, byte+1==0xc7, byte+2==0xff, byte+3==0x7f  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b4` | [32:40] (byte+4) | raw/unmapped |  |
| `b5` | [40:48] (byte+5) | raw/unmapped |  |
| `b6` | [48:56] (byte+6) | raw/unmapped |  |
| `b7` | [56:64] (byte+7) | raw/unmapped |  |

*M5 out-of-line function-CALL branch-and-link `ff c7 ff 7f be 03 40 0e` (8B). The actual control transfer for BOTH a direct([[noinline]]) and an indirect(visible_function_table) call; byte-identical and operand-invariant across arg-count and callee body. Preceded by the 0x43 frame_marker (`43 00 00 01`) and a `9e 60 <type> 0e ..` call-setup op (byte+2 type: 0x00 direct = embeds the target PC in a `fe ..` tail; 0x01 indirect = target code-VA loaded from the function table by a preceding m5_load). Callee returns via the epilogue `27 00 04 00 20 00 a5 02`. RESOLVES the EXP-M5-11 MAJOR-4 open (M5 out-of-line CALL ABI). b4(0xbe)/byte0(0xff) load-bearing (splice->CMDBUF_ERROR, redirects the branch); b6(0x40) inert; b4..b7 kept raw (rule 5).*

### `m5_call_tail`

- **Length:** 4 bytes  ·  **Match:** byte+0==0xfb, byte+1==0x1e, byte+2==0x1f, byte+3==0x00  ·  **Provenance:** HW-validated

*indirect call-setup tail `fb 1e 1f 00` (4B): the last setup word before the m5_call branch on an INDIRECT (visible_function_table) call; completes materialising the return context. Absent on the direct-call path. EXP-M5-18.*

### `frame_marker_compact`

- **Length:** 2 bytes  ·  **Match:** byte+0==0x60  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | raw/unmapped |  |

*2-byte compact frame/scope marker (byte0 0x60, byte+2 != 0x00). Precedes a threadgroup-atomic store or a divergent control-flow block; the following op is a full 14-byte threadgroup device_store or a CF op. Distinct from the 4-byte spill_frame_marker (byte+2==0x00).*

### `cubearray_coord_const`

- **Length:** 4 bytes  ·  **Match:** byte+0==0xf0, byte+1==0xc0, byte+2==0x04  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b3` | [24:32] (byte+3) | raw/unmapped |  |

*4-byte constant / reciprocal-of-major-axis load feeding the cube/cube-array face-select coordinate math (`f0 c0 04 00`, k_tex_array_cube@48). Precedes the fspecial + coord_madf chain that normalizes the cube face coordinate.*

### `tg_addr_compute`

- **Length:** 6 bytes  ·  **Match:** byte+0==0x1c, byte+1==0x02, byte+2==0x00  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b3` | [24:32] (byte+3) | modifier |  |
| `b4` | [32:40] (byte+4) | modifier |  |
| `b5` | [40:48] (byte+5) | modifier |  |

*6-byte threadgroup-buffer base/offset compute (`1c 02 00 00 00 00`, k_threadgroup@46), bracketed between the low-nibble-3 threadgroup-id ops and the threadgroup device_store. Distinct from the 4-byte get_sr datapath form (byte+3 low-nibble 6). HW-VALIDATED (splice, A18 EXP-M4-14, own-MSL k_thr.metal threadgroup-tile reduction): byte0 HIGH nibble [bit4:8] is a LIVE dst-register / operand selector (splicing 0x1c->0x2c/0x3c/0x5c/0x6c corrupts the tile dataflow from o[i]=2i+3 to o[i]=i+2; 0x1c/0xfc reproduce baseline) -- so the DB match (0,8,0x1c) OVER-FITS the r1 form; the true opcode key is low-nibble 0xc + the byte+1/byte+2 discriminator, high nibble a live operand (value->register map not a clean linear index -- needs more sweeps). byte+1 (fixed 0x02 in match) is likewise a LIVE source/operand selector (0x00/0x01/0x03 corrupt, 0x06/0xff reproduce), not an opcode constant. byte+2 (fixed 0x00 in match) is runtime-INERT to the computation (0x01/0x02/0x08/0xff all baseline) but is the disassembler's length discriminator (==0x00 -> 6B vs 2B mov_imm). bytes +3/+4/+5 are RESERVED/inert (spliced ff/ee/dd simultaneously -> output unchanged, op ran).*

### `pad_operand`

- **Length:** 2 bytes  ·  **Match:** bits[0:4]==0x0  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `hi` | [4:8] | immediate |  |
| `word` | [8:16] (byte+1) | immediate |  |

*NOT A STANDALONE HARDWARE OPCODE. A 2-byte low-nibble-0 slot carrying a trailing operand / immediate / SFU-coefficient WORD of the PRECEDING instruction, or inter-op zero PADDING, or the interior bytes of one longer under-lengthed op. byte0 high nibble and byte1 are a verbatim raw passthrough; the coefficient/immediate bits are intentionally NOT semantically decoded (clean-room rule 5 -- the SFU range-reduction coefficient SEQUENCE is not reconstructed). Named only so the tokenizer resolves these vetted slots out of the unknown bucket; the more-specific frame_marker_compact (0x60) and mov_imm (0x0c) win where they apply.*

### `dev_scoreboard_fence`

- **Length:** 4 bytes  ·  **Match:** byte+0==0x80, byte+1==0x02, byte+2==0x00  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `scope_flag` | [24:32] (byte+3) | modifier | `0x0`=default device/wide scope; `0x4`=scope variant |

*Compute memory / scoreboard FENCE, device/wide-scope variant: `80 02 00 <scope_flag>` (4 bytes). The 0x80 sibling of the 0x07/0x87 scoreboard_fence family (high bit = wider memory/device scope). The compiler inserts it around divergent control flow and before atomics/calls. scope_flag (byte+3) is a scope/flag operand: 0x00 in the dominant form, 0x04 in a rare variant (one texture_sample occurrence). A bare `80 02` with byte+2 != 0x00 is the 2-byte compact form (pad_operand).*

### `n3_mov`

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0x3  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `srcA_reg` | [8:15] (byte+1) | register |  |
| `srcA_uni` | [15:16] | modifier | `0x0`=gpr; `0x1`=uniform/hi |
| `subform` | [16:24] (byte+2) | modifier |  |
| `companion` | [24:32] (byte+3) | modifier | `0x1`=zext_hi_zero |

*d = mov/zero-extend(srcA) ; compact 4-byte register move / 16-bit zero-extend / half-pack. dst = byte0 high nibble (r0..r15) PROVEN by parallel-extend diffs. srcA_reg (byte+1 bits0-6) = source register; srcA_uni (byte+1 bit7) = uniform-file/high-half flag. subform (byte+2) = source-class / size sub-form selector (0x00 full-word move; 0x20 a source-class variant; 0x01/0x02 half/size selects). companion (byte+3) = companion / second-operand descriptor: value 0x01 with subform 0x00 is the ZERO-EXTEND high-half-zero companion `X3 00 00 01` (emitted after the low-half move to zero the upper 16 bits, matching the HW-validated mov_zext16 lowering); other values carry a second-source / shuffle-move descriptor. Generalises mov_zext16 (0x13) and frame_marker (0x43) to all dst regs.*

### `n3_addr_prep`

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0x3, byte+2==0x27  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `src_reg` | [8:16] (byte+1) | register |  |
| `op_variant` | [24:32] (byte+3) | enum | `0xbf`=atomic_fetch_add texel-address prep; `0x36`=atomic_fetch_max texel-address prep; `0x22`=texture read() texel-address prep |
| `src_companion` | [32:40] (byte+4) | raw/unmapped |  |
| `tail` | [40:80] (byte+5) | raw/unmapped |  |

*d = address/coordinate prep for a 2D read_write (image) texture op (the texel-address compute that feeds an atomic_fetch_* / read on texture2d<...,access::read_write>). 10-byte low-nibble-3 form, op-select byte+2 == 0x27. dst (byte0 high nibble) = destination register for the computed texel address. src_reg (byte+1) = coordinate source register: bit7 = file flag (always 1), bits[6:0] = reg index. op_variant (byte+3) selects the image memory-op / addressing-format variant (0xbf atomic_fetch_add, 0x36 atomic_fetch_max, 0x22 texture read). src_companion (byte+4) = companion operand byte that tracks src_reg (part of the register/addressing encoding). tail (byte+5..+9) = mostly-constant operand/immediate descriptor (02 00 00 00 00; byte+5 always 0x02). Distinct from the low-nibble-2 rt_transform_test (also byte+2==0x27 but with byte+3==0x81, byte+4==0x22).*

### `n3_sample_read`

- **Length:** 10 bytes  ·  **Match:** byte+0==0x03, byte+2==0x26  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b1` | [8:16] (byte+1) | raw/unmapped |  |
| `b3` | [24:32] (byte+3) | raw/unmapped |  |
| `tail` | [32:80] (byte+4) | raw/unmapped |  |

*fragment sample-id / sample-position read (byte0 0x03, op-select byte+2 == 0x26). 10-byte low-nibble-3 form.*

### `cvt_f2h_dst`

- **Length:** 6 bytes  ·  **Match:** bits[0:4]==0x1, bits[28:32]==0x8  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `srcfmt` | [8:16] (byte+1) | raw/unmapped |  |
| `opsel` | [16:24] (byte+2) | opcode-select | `0x1c`=f2h; `0x3c`=f2h(srcmode) |
| `src` | [24:32] (byte+3) | raw/unmapped |  |
| `dhalf` | [32:40] (byte+4) | raw/unmapped |  |
| `tail` | [40:48] (byte+5) | raw/unmapped |  |

*d(half) = half(a)  ; fp32 -> fp16 narrowing convert, for ANY dst register (byte0 high nibble). Generalises the byte0==0x11 (dst r1) cvt_f2h to r0..r15. byte+2 0x1c is the base convert, 0x3c the same convert with the source-mode bit (bit5) set. byte+3 hi-nibble 8 (== 0x8x) is the single-source convert descriptor marker.*

### `cvt_bf16`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x1, byte+3==0x81, byte+4==0x01  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `srcw` | [8:16] (byte+1) | opcode-select | `0x2`=src16; `0x3`=src32 |
| `opsel` | [16:24] (byte+2) | raw/unmapped |  |
| `src` | [24:32] (byte+3) | raw/unmapped |  |
| `fmt` | [32:40] (byte+4) | raw/unmapped |  |
| `b5` | [40:48] (byte+5) | raw/unmapped |  |
| `dir` | [48:56] (byte+6) | opcode-select | `0x40`=to_bfloat; `0x80`=to_half |
| `b7` | [56:64] (byte+7) | raw/unmapped |  |

*bfloat convert (8-byte). byte+1 = source width (0x03 float32, 0x02 float16); byte+6 = direction (0x40 = result bfloat: float->bfloat / half->bfloat; 0x80 = result half: bfloat->half). byte+4 == 0x01 marks a bfloat operand. 8-byte sibling of the 6-byte cvt_f2h_dst (byte+4 bit0 set = bfloat, so longer).*

### `bf_add_dst`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x1, byte+2==0x1c  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `fmt` | [8:16] (byte+1) | opcode-select | `0x2`=bf; `0x4`=bf2 |
| `srcA` | [24:32] (byte+3) | register |  |
| `srcB` | [32:40] (byte+4) | register |  |
| `tail` | [40:64] (byte+5) | raw/unmapped |  |

*d(bfloat) = a + b  ; native bfloat add for ANY dst register. Generalises the byte0==0x11 bf_alu (dst r1) to r0..r15. byte+1 = 0x02 scalar / 0x04 bfloat2-packed lane. Distinguished from the 8-byte convert cvt_bf16 by byte+3 (a register here vs the 0x81 convert-source descriptor there). The byte0==0x11 bf_alu (16 match bits) wins its own bytes.*

### `bf_mul_dst`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x1, byte+2==0x1d  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `fmt` | [8:16] (byte+1) | opcode-select | `0x2`=bf; `0x4`=bf2 |
| `srcA` | [24:32] (byte+3) | register |  |
| `srcB` | [32:40] (byte+4) | register |  |
| `tail` | [40:64] (byte+5) | raw/unmapped |  |

*d(bfloat) = a * b  ; native bfloat multiply for ANY dst register. op-select byte+2 == 0x1d (vs 0x1c add) -- single-bit byte-diff (bf_add vs bf_mul).*

### `bf_fma_dst`

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0x1, byte+2==0x1e  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `fmt` | [8:16] (byte+1) | opcode-select | `0x2`=bf; `0x4`=bf2 |
| `srcA` | [24:32] (byte+3) | register |  |
| `srcB` | [32:40] (byte+4) | register |  |
| `srcC` | [40:48] (byte+5) | register |  |
| `tail` | [48:80] (byte+6) | raw/unmapped |  |

*d(bfloat) = a*b + c  ; native bfloat fused multiply-add. op-select byte+2 == 0x1e (the fma length bit, byte+2 bit1, is set) -> 10-byte 3-source form. Covers the byte0==0x11 case the EXP-O2D length rule sized as 10 but had no descriptor for, plus all other dst regs.*

### `sr_read_wide`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x4, bits[15:16]==0x1, byte+3==0x00, bits[16:17]==0x0, bits[17:18]==0x1  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `sel` | [8:15] (byte+1) | enum | `0x7f`=simd_matrix_ld/st_builtin; `0x0`=wide_builtin_base; `0x21`=rtq_property(a1); `0x1`=rtq_property(81); `0x48`=rtq_property(c8) |
| `width` | [16:24] (byte+2) | enum | `0x22`=w22; `0x2`=w02; `0x6`=w06; `0x46`=w46; `0x26`=w26 |
| `operand` | [32:40] (byte+4) | immediate |  |
| `marshal` | [40:56] (byte+5) | modifier |  |
| `phase` | [56:64] (byte+7) | modifier |  |

*d[dst] = wide_special_read(sel, width) ; 8-byte member of the get_sr low-nibble-4 datapath family. dst = byte0 high nibble (PROVEN, spans r0..r15). sel (byte+1 bits0-6; bit7 always 1 = match) = the special-register / property / builtin SELECTOR: 0x7f = the simd-matrix load/store wide builtin (appears only in subgroupMatrixLoad/Store kernels); 0x00 = a wide scalar builtin base; 0x21/0x01/0x48 = intersection_query committed/candidate PROPERTY reads (type / geometry-id / primitive-id / instance-id / distance / barycentrics / transform component). width (byte+2, low bits 0/1 fixed by match) = the sub-selector / component-WIDTH: toggles 0x02<->0x06 across successive component reads of one wide value, and 0x22/0x26/0x46 across property kinds. operand (byte+4) = an element/offset operand that STEPS with the wide-component index (0x00,0x10,0x18,.. as dst advances r0->r3). marshal (byte+5/+6) = the RT-getter / matrix element operand descriptor (typed mod: located as a getter/element operand that co-steps with the component, e.g. 0x0c/0x01/0x05; the getter/marshal SEQUENCE itself is NOT reconstructed, rule 5). phase (byte+7) = the getter-PHASE / marshal-continuation FLAG: 0x00 in the wide-builtin and COMMITTED (post-traversal) property reads; bit7 (0x80) marks the CANDIDATE (during-traversal) property read; 0x20 is a further candidate sub-variant. byte-diff PROVEN (EXP-M4-13 R9): own-MSL intersection_query CANDIDATE getters (get_candidate_primitive_id/geometry_id/triangle_distance inside the q.next() traversal loop) emit byte+7==0x80, while COMMITTED getters (get_committed_* after traversal) emit byte+7==0x00; corpus (n=996) confirms 0x80/0x20 occur only in ray-query getter files. NOT a constant reserved byte (the earlier n=26 "const 0x00" note was superseded by the larger corpus).*

### `rt_query_traverse`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0xf, byte+1==0x80, byte+2==0x86, byte+5==0x22, byte+6==0x82  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `opA` | [24:32] (byte+3) | raw/unmapped |  |
| `sel` | [32:40] (byte+4) | enum | `0x7`=sel0; `0xf`=sel1 |
| `opB` | [56:64] (byte+7) | register |  |

*8-byte special op emitted only inside intersection_query traversal / committed+candidate result getters. byte0 HIGH nibble = dst register; byte+1=0x80, byte+2=0x86 (SFU/special-function datapath marker). The trailing `[07|0f] 22 82 ZZ` (bytes +4..+7) is the SECOND HALF of THIS instruction, not a separate 0x0f op. HW-VALIDATED (splice, A18 EXP-M4-14, own-MSL k_dist intersection_query committed-distance, 2-triangle AS, near tri t=1 / far tri t=5, baseline committed=1.0, load-bearing op@_agc.main+0x155a = bf 80 86 1a 07 22 82 48): opB (byte+7) is a CONSUMED traversal operand-register/descriptor -- 0x48/0x42/0xc8 give the correct near hit (1.0), 0x00/0x1a/0x20/0x0f/0xff skip the near triangle (commit far=5.0), and 0x02/0x06/0x40/0x07 HANG the traversal (contained) -> a structured operand descriptor (the correct-value set {0x42,0x48,0xc8} is NOT a simple linear register index; internal class/index bit-split not fully decoded, see unresolved). sel (byte+4) is a CONSUMED result-lane/operand selector: valid 0x07=sel0 / 0x0f=sel1 preserve correctness, invalid values corrupt operand selection (only this committed-path op is load-bearing on sel; the other 17 rtq ops are inert). byte+5 (0x22) and byte+6 (0x82), pinned by the match, are OPCODE/form bytes not free operands: splicing byte+5 to 0x1a/0x50/0x07/0x0f/0xff -> CMDBUF_ERROR (illegal opcode), and byte+6 to 0x40/0x48/0x50 -> CMDBUF_ERROR while 0x20/0x60/0xff commit the far hit -> a structural opcode/descriptor byte. opA (byte+3) is INERT on this load-bearing committed-path instance (0x18/0x1a/0x00/0xff all -> 1.0 unchanged); its role is UNRESOLVED (a secondary operand not consumed on the box-test path, or a reserved/dst-related slot) and is kept raw. Internal getter algorithm not lifted (clean-room rule 5).*

### `fldexp`

- **Length:** 6 bytes  ·  **Match:** bits[0:4]==0xf, byte+1==0x15, byte+2==0x80  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `operand` | [24:32] (byte+3) | raw/unmapped |  |
| `b4` | [32:40] (byte+4) | raw/unmapped |  |
| `b5` | [40:48] (byte+5) | raw/unmapped |  |

*fldexp: d = ldexp(a, n) = a * 2^n for a RUNTIME integer exponent n (float scale-by-power-of-two). byte0 low-nibble 0xf, high-nibble = dst; byte+1=0x15 sub-op, byte+2=0x80 constant; byte+3 = operand descriptor. Only emitted for the dynamic-exponent ldexp -- the constant-exponent form folds to an fmul by a power-of-two literal.*

### `ibfins`

- **Length:** 12 bytes  ·  **Match:** byte+0==0x27, bits[16:17]==0x0, bits[18:24]==0x15  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `form` | [8:16] (byte+1) | opcode-select | `0x10`=shl(reg); `0x0`=insert/mask/narrow; `0x2`=addr/matrix-prep; `0x20`=shl/merge(var); `0x11`=insert(var) |
| `cache` | [17:18] | modifier |  |
| `dst` | [24:32] (byte+3) | register |  |
| `b4` | [32:40] (byte+4) | modifier |  |
| `mask_imm` | [40:48] (byte+5) | immediate |  |
| `mask_hi` | [48:49] (byte+6) | immediate |  |
| `b6hi` | [49:56] | modifier |  |
| `b7` | [56:64] (byte+7) | modifier |  |
| `srcdesc` | [64:72] (byte+8) | enum | `0xf0`=reg-operand(loaded); `0xd0`=reg-operand(computed); `0xc0`=imm-operand |
| `srcC` | [72:80] (byte+9) | modifier |  |
| `b10` | [80:88] (byte+10) | modifier |  |
| `b11` | [88:96] (byte+11) | modifier |  |

*d = shift-left / bitfield-insert (integer). The byte0-bit7 LEFT/INSERT mirror of the 0xa7 ibfe (right/extract) family -- shl_reg (`27 10 54 ..`) is byte-identical to shr_log (`a7 10 54 ..`) except byte0. 12-byte operand-descriptor form (byte+8 = 0xf0 register / 0xc0 immediate). byte+1 (form) selects the sub-op. byte+2 bit1 (cache) = source last-use hint.*

### `atomic_tg`

- **Length:** 12 bytes  ·  **Match:** byte+0==0x67, byte+1==0x03  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `amode` | [16:24] (byte+2) | modifier |  |
| `ret_desc` | [24:32] (byte+3) | modifier |  |
| `rsv4` | [32:40] (byte+4) | modifier |  |
| `op_desc` | [40:48] (byte+5) | modifier |  |
| `rsv6` | [48:56] (byte+6) | modifier |  |
| `xop_desc` | [56:64] (byte+7) | modifier |  |
| `data_desc` | [64:72] (byte+8) | modifier |  |
| `rsv9` | [72:80] (byte+9) | modifier |  |
| `rsv10lo` | [80:86] (byte+10) | modifier |  |
| `op` | [86:91] | opcode-select | `0x10`=add; `0x11`=and; `0x12`=cmpxchg; `0x13`=fadd; `0x14`=smax; `0x15`=smin; `0x16`=or; `0x1b`=sub; `0x1c`=umax; `0x1d`=umin; `0x1e`=xchg; `0x1f`=xor |
| `op_hi_rsv` | [91:96] | modifier |  |

*THREADGROUP (shared-memory) atomic read-modify-write. byte0 0x67 load/store family, threadgroup variant byte+1==0x03 (device atomics are byte+1 0x11/0x01, 14 B). Operation = the SAME 5-bit op enum used by the device atomic_mem/atomic_rmw, here at bits[86:91] (16 add, 17 and, 18 cmpxchg, 19 fadd, 20 smax, 21 smin, 22 or, 27 sub, 28 umax, 29 umin, 30 xchg, 31 xor). byte+3 = return-register descriptor (0x03 when the old value is consumed, 0x00 noret); byte+5/+8 = operand-register descriptors that step together (returning-RMW 0x02/0x22, noret-RMW 0x01/0x20, xchg&cmpxchg 0x00/0x02). byte+2==0x56 selects the direct-value amode for atomic_exchange (RMW ops use 0x54, i.e. an ALU/simd-reduced operand). A single native op preceded by a simd_reduce lane-combine, NOT a CAS retry loop.*

### `tile_read_mrt`

- **Length:** 12 bytes  ·  **Match:** byte+0==0x67, byte+1==0x06, byte+2==0x54  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [24:32] (byte+3) | register |  |
| `b4` | [32:40] (byte+4) | raw/unmapped |  |
| `rt_index` | [40:48] (byte+5) | immediate |  |
| `b6` | [48:56] (byte+6) | raw/unmapped |  |
| `fmt` | [56:64] (byte+7) | raw/unmapped |  |
| `tail` | [64:96] (byte+8) | raw/unmapped |  |

*fragment tilebuffer / attachment READ (byte+1==0x06). The plain-read sibling of tile_read (0x0e programmable-blend) and imageblock_load (0x16 first-access). byte+3 = destination GPR, byte+5 = render-target / imageblock-slice selector, byte+7 = slot format.*

### `tex_addr_setup`

- **Length:** 12 bytes  ·  **Match:** byte+0==0x17, bits[16:17]==0x0, bits[18:24]==0x15  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `form` | [8:16] (byte+1) | opcode-select | `0x1`=coord-proj; `0x5`=sample-addr/grad; `0x7`=raw-coord passthrough; `0xd`=sample-addr/grad (alias of 5) |
| `cache` | [17:18] | modifier |  |
| `op_reg` | [24:32] (byte+3) | register |  |
| `op_hi` | [32:40] (byte+4) | modifier |  |
| `op_reg2` | [40:48] (byte+5) | register |  |
| `rsv6` | [48:56] (byte+6) | modifier |  |
| `op_mode` | [56:64] (byte+7) | modifier |  |
| `src_desc` | [64:72] (byte+8) | enum | `0xf0`=register-operand (hi-nibble 0xf required) |
| `op_desc9` | [72:80] (byte+9) | modifier |  |
| `op_cnt` | [80:88] (byte+10) | modifier |  |
| `rsv11` | [88:96] (byte+11) | modifier |  |

*texture COORDINATE-PROJECTION / sample-address / gradient SETUP feeding a following tex_sample. 12-byte form of the 0x17 group. HW-VALIDATED (splice, A18 EXP-M4-14, own-MSL k_lod texture2d.sample with explicit level(), 4x4x3 mip texture texel=1000*L+100*y+x): form (byte+1) is a genuine opcode/form select -- 0x01 = coordinate projection (no explicit LOD; samples level0), 0x05 = sample-address + explicit LOD/gradient, 0x07 = raw-coordinate passthrough (returns the U coord itself), 0x0d = alias of 0x05. cache (byte+2 bit1, 0x54/0x56) is a source-cache/last-use scheduling hint -- the WHOLE byte+2 is INERT to the sampled result (0x54/0x56/0x55/0x50/0x74/0x14 all identical output). op_reg (byte+3) = the LOD/coordinate SOURCE REGISTER selector: only 0x06 tracks the LOD input (lod=1->1100, lod=2->2000); every other value reads a zero register (-> level0=201). op_hi (byte+4) = operand high-bits/flags (bit6 inert, low bits corrupt the operand). op_reg2 (byte+5) = secondary operand-register selector affecting the sampled LOD. rsv6 (byte+6) = near-reserved (inert 0x00..0x40, only 0xff perturbs). op_mode (byte+7) = operand-present/mode gate (bit2 gates the operand: set -> active, clear -> reads 0). src_desc (byte+8=0xf0) = source-operand MODE descriptor, hi-nibble 0xf = 'operand is a register' (matches the ibfins/b_alu10 0xf0 convention; corrupting it makes the operand read 0). op_desc9 (byte+9) = structured operand descriptor (hi-nibble in {c,e,f} AND low-nibble in {0,2,4,6} preserve the operand; encodes operand class + low operand bits). op_cnt (byte+10) = operand count/immediate that shifts the resolved mip level. rsv11 (byte+11) = RESERVED pad, fully inert (every value 0x00..0xff leaves the result unchanged). byte+5/+9/+10 exact register-index-vs-shift-vs-class bit-splits not isolated to a single clean field mapping (see unresolved).*

### `h_alu_hi`

- **Length:** 6 bytes  ·  **Match:** bits[0:4]==0x8, bits[18:21]==0x7  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `srcA` | [8:16] (byte+1) | register |  |
| `opsel` | [16:19] (byte+2) | opcode-select | `0x4`=hadd; `0x5`=hmul; `0x6`=hfma |
| `opflags` | [19:24] | modifier |  |
| `srcB` | [24:32] (byte+3) | register |  |
| `ctrl` | [32:40] (byte+4) | modifier |  |
| `mods` | [40:48] (byte+5) | modifier |  |

*d.hi(half) = op(a, b) ; NATIVE fp16 float ALU writing the HIGH 16-bit half of the destination register (the .y lane of a packed half2). byte0 low-nibble 0x8 is the high-half sibling of the 0x10 low-half half_alu; byte0 high nibble = dst reg. op-select byte+2 low-3 bits (0x1c hadd / 0x1d hmul / 0x1e hfma) is the SAME enum as the 0x09/0x10 float families.*

### `h_alu_hi_ext`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x8, bits[18:21]==0x7  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `srcA` | [8:16] (byte+1) | register |  |
| `opsel` | [16:19] (byte+2) | opcode-select | `0x4`=hadd; `0x5`=hmul; `0x6`=hfma |
| `opflags` | [19:24] | modifier |  |
| `srcB` | [24:32] (byte+3) | register |  |
| `ext` | [32:40] (byte+4) | modifier |  |
| `srcC` | [40:48] (byte+5) | register |  |
| `tail` | [48:64] (byte+6) | raw/unmapped |  |

*d.hi(half) = a*b + c (fma) or op(a,b) with an extended saturate/abs source tail, writing the HIGH 16-bit half. 8-byte member of the low-nibble-8 half ALU: byte+4 low-2 bits set selects the extended encoding (fma addend srcC at byte+5), like the 0x09 fp32 polymorphism.*

### `h_coord_hi`

- **Length:** 6 bytes  ·  **Match:** bits[0:4]==0x8, bits[16:19]==0x6, bits[21:22]==0x1  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `srcA` | [8:16] (byte+1) | register |  |
| `opsel` | [16:24] (byte+2) | opcode-select | `0x26`=hmul_coord; `0x2e`=hfma_coord |
| `srcB` | [24:32] (byte+3) | register |  |
| `ctrl` | [32:40] (byte+4) | modifier |  |
| `mods` | [40:48] (byte+5) | modifier |  |

*d.hi(half) = fused-multiply[-add] coordinate op writing the HIGH 16-bit half; op-select 0x26 (hmul_coord, 2-source) / 0x2e (hfma_coord, fused mul-add). Emitted by half-precision geometry / interpolation. 6-byte 2-source form.*

### `h_coord_hi_ext`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x8, bits[16:19]==0x6, bits[21:22]==0x1  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `srcA` | [8:16] (byte+1) | register |  |
| `opsel` | [16:24] (byte+2) | opcode-select | `0x26`=hmul_coord; `0x2e`=hfma_coord |
| `srcB` | [24:32] (byte+3) | register |  |
| `ext` | [32:40] (byte+4) | modifier |  |
| `srcC` | [40:48] (byte+5) | register |  |
| `tail` | [48:64] (byte+6) | raw/unmapped |  |

*d.hi(half) = fused-mul[-add] coordinate op (0x26/0x2e) writing the HIGH 16-bit half, 8-byte extended form (byte+4 low2==1: 3rd source / ext tail at byte+5). See h_coord_hi.*

### `packed_half2_hi`

- **Length:** 6 bytes  ·  **Match:** bits[0:4]==0x8, byte+2==0x24  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `srcA` | [8:16] (byte+1) | register |  |
| `opsel` | [16:24] (byte+2) | opcode-select | `0x24`=hpack2_alu |
| `srcB` | [24:32] (byte+3) | register |  |
| `mods` | [32:48] (byte+4) | modifier |  |

*d(half2) = op(a, b) on a PACKED 2xfp16 register (both lanes in ONE op), op-select 0x24. The low-nibble-8 member (byte0 high nibble = dst) of the packed-half2 ALU already sized by the packed-half2 length rule; this descriptor names it.*

### `rtq_pred`

- **Length:** 4 bytes  ·  **Match:** byte+0==0x06, byte+1==0xc2, bits[16:32]==0x0  ·  **Provenance:** mixed

*Ray-query traversal predicate/condition word. Byte-INVARIANT 4-byte token (06 c2 00 00) the intersection_query compiler emits immediately after the candidate-status compare (icmp_pred, byte0 0x0a) and before its consumer (if_push conditional branch, or a predicated iadd2). Exclusively emitted inside intersection_query / ray-query traversal loops. Exact micro-op NOT-YET-CHARACTERIZED; documented as a fixed encoding + length only.*

### `sfu_marker`

- **Length:** 2 bytes  ·  **Match:** byte+0==0x06, byte+1==0x02  ·  **Provenance:** mixed

*SFU / transcendental helper marker word. Byte-INVARIANT 2-byte token (06 02) the compiler emits adjacent to special-function-unit and varying/mesh output ops -- after a 6-byte low-nibble-2 min/max range-reduction op and before an fspecial (2f/af) SFU op or a 0x80 output word. Fixed control token with no operand bits; exact micro-op NOT-YET-CHARACTERIZED. Per clean-room rule 5 the adjacent range-reduction coefficient words are left raw.*

### `ray_move_copy6`

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0xb, byte+2==0x41  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `src` | [8:16] (byte+1) | register |  |
| `form` | [16:24] (byte+2) | enum | `0x41`=copy_b6(b3=0x08) |
| `optype` | [24:32] (byte+3) | modifier | `0x8`=reg32 |

*RAY register-marshalling MOVE, bit6 copy form (4B). dst=byte0 hi nibble, src=byte+1, byte+2==0x41, byte+3==0x08 (32-bit register operand). The dominant move in the ray-struct marshalling grid after rt_intersect. R9 typed the former b3 raw byte.*

### `ray_move_zero6`

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0xb, byte+2==0x40  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `src` | [8:16] (byte+1) | register |  |
| `form` | [16:24] (byte+2) | enum | `0x40`=zero_b6(b3=0x00) |
| `b3` | [24:32] (byte+3) | raw/unmapped |  |

*RAY register-marshalling MOVE, bit6 zero form (4B). byte+2==0x40 -> writes a zero/const component in the bit6 source-class (the no-source counterpart of the 0x41 copy form).*

### `ray_move_zinit`

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0xb, byte+2==0x80  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `src` | [8:16] (byte+1) | register |  |
| `form` | [16:24] (byte+2) | enum | `0x80`=zero_init |
| `b3` | [24:32] (byte+3) | raw/unmapped |  |

*RAY register-marshalling MOVE, zero-init form (4B). byte+2==0x80 -> zero/const component (e.g. const origin float3(0,0,0)) in the bit7 source-class. Sibling of ray_move (0x81).*

### `rtq_state_move`

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0xb, byte+2==0x09, byte+3==0x00  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `src` | [8:16] (byte+1) | register |  |
| `form` | [16:24] (byte+2) | enum | `0x9`=query_state_read |
| `b3` | [24:32] (byte+3) | raw/unmapped |  |

*Intersection-query compact register move (4B). byte+2==0x09, byte+3==0x00, byte+1 = source selector. Emitted once per intersection_query kernel, reading a fixed query-state / result register into a GPR.*

### `funary_imm`

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0xb, byte+2==0x0f  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `src` | [8:16] (byte+1) | register |  |
| `form` | [16:24] (byte+2) | enum | `0xf`=modifier_imm |
| `srcB` | [24:32] (byte+3) | register |  |
| `lut_a` | [32:40] (byte+4) | modifier |  |
| `mod` | [40:48] (byte+5) | modifier |  |
| `modtail` | [48:80] (byte+6) | modifier |  |

*Float source-modifier / integer-logic move with an immediate/operand tail (10B, byte+2==0x0f). src (byte+1) = primary source register: byte+1 low bit = size (b32=1) is set in 760/763 corpus instances (OWN-MSL+thirdparty), the (reg<<1)|size register convention -- so byte+1 is the source operand, not byte+3. srcB (byte+3) = secondary operand/immediate (mostly 0x00). lut_a/mod (byte+4,+5) = LUT/source modifier. modtail (byte+6..+9) = immediate/modifier tail (byte+8,+9 observed 0x00 corpus-wide). OWN-MSL orimm (a|0x100) reproduces the byte+2==0x0f form byte-exact.*

### `b_alu10_lo7`

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0xb, bits[16:20]==0x7  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `src_reg` | [8:15] (byte+1) | register |  |
| `src_flag` | [15:16] | modifier | `0x0`=gpr; `0x1`=uniform/class |
| `opsel_hi` | [20:24] | enum | `0x0`=0x07; `0x1`=and_mask(0x17); `0x2`=tex/operand_setup(0x27); `0x4`=0x47; `0x5`=0x57; `0x6`=0x67; `0x7`=0x77; `0xc`=0xc7; `0xd`=0xd7; `0xe`=0xe7 |
| `srcA` | [24:32] (byte+3) | register |  |
| `modA` | [32:40] (byte+4) | modifier |  |
| `modB` | [40:48] (byte+5) | modifier |  |
| `z6` | [48:56] (byte+6) | immediate |  |
| `outmod` | [56:64] (byte+7) | modifier |  |
| `ext8` | [64:72] (byte+8) | immediate |  |
| `ext9` | [72:80] (byte+9) | immediate |  |

*0x?b 10-byte modifier/convert/setup ALU, byte+2 low-nibble 0x7. dst = byte0 high nibble (reg-sweep PROVEN). src_reg (byte+1 bits0-6) = source register; src_flag (byte+1 bit7) = source-class / uniform flag (covaries with dst across the subgroup-matrix load/store sweep: byte+1 low = 0x0c/0x0a/0x06/0x04 tracks srcA reg 6/5/3/2 as dst steps r2/r2/r1/r1). opsel_hi (byte+2 high nibble) = the op-select family: 0x27 tex/operand-setup (dominant), 0x17 `& mask`, 0x07 base, 0x47/0x57/0x67. srcA (byte+3) = second source descriptor (0x81 = single-source marker). modA/modB (byte+4/+5) = modifier/mode words (0x10/0x02 dominant). z6 (byte+6) = reserved/pad (const 0 across all 919 corpus instances) -- TYPED imm. outmod (byte+7) = output/rounding modifier (bit7/nibble). ext8 (byte+8) = operand/output-extension coefficient (0x00 dominant, 0x10 in 176/919) -- TYPED imm; ext9 (byte+9) = reserved/pad (const 0) -- TYPED imm. EXP-M4-13 R8: z6/ext8/ext9 RE-TYPED raw->imm (pad/operand-coefficient words per the schema convention). Exact per-op-select tail coefficient meanings NOT characterised (family-level; convert/setup coefficient words not reconstructed).*

### `b_alu10_loe`

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0xb, bits[16:20]==0xe  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `src_reg` | [8:15] (byte+1) | register |  |
| `src_flag` | [15:16] | modifier | `0x0`=gpr; `0x1`=uniform/class |
| `opsel_hi` | [20:24] | enum | `0x2`=0x2e; `0x3`=0x3e; `0x6`=0x6e |
| `srcA` | [24:32] (byte+3) | register |  |
| `modA` | [32:40] (byte+4) | modifier |  |
| `modB` | [40:48] (byte+5) | modifier |  |
| `z6` | [48:56] (byte+6) | immediate |  |
| `outmod` | [56:64] (byte+7) | modifier |  |
| `ext8` | [64:72] (byte+8) | immediate |  |
| `ext9` | [72:80] (byte+9) | immediate |  |

*0x?b 10-byte modifier/logic ALU, byte+2 low-nibble 0xe (funary/ilogic/shift-prep base with a non-zero dst register; named forms funary(0x0e)/ilogic(0x1e) win by specificity, this covers 0x2e/0x3e/0x6e). SAME 10-byte operand layout as the HW-family sibling b_alu10_lo7 (differs only in the byte+2 op-family low-nibble): dst = byte0 high nibble (reg); src_reg (byte+1 bits0-6) = source register; src_flag (byte+1 bit7) = source-class / uniform flag (=0 gpr in all 25 corpus instances); opsel_hi (byte+2 high nibble) = op-select family (0x2e dominant); srcA (byte+3) = second source descriptor (bit7 = single-source marker, set in 11/25); modA/modB (byte+4/+5) = modifier/mode words; z6 (byte+6) = reserved/pad (const 0, all 648) -- TYPED imm; outmod (byte+7) = output/rounding modifier; ext8/ext9 (byte+8/+9) = operand/coefficient tail (const 0 in-corpus) -- TYPED imm (pad/coefficient words). EXP-M4-13 R8: z6/ext8/ext9 RE-TYPED raw->imm. Per-op-select tail semantics NOT characterised (family-level; convert coefficient words not reconstructed).*

### `b_alu10_lof`

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0xb, bits[16:20]==0xf  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `src_reg` | [8:15] (byte+1) | register |  |
| `src_flag` | [15:16] | modifier | `0x0`=gpr; `0x1`=uniform/class |
| `opsel_hi` | [20:24] | enum | `0x1`=0x1f; `0x3`=0x3f; `0x4`=0x4f; `0x6`=0x6f; `0x8`=0x8f; `0xc`=0xcf |
| `srcA` | [24:32] (byte+3) | register |  |
| `modA` | [32:40] (byte+4) | modifier |  |
| `modB` | [40:48] (byte+5) | modifier |  |
| `z6` | [48:56] (byte+6) | immediate |  |
| `outmod` | [56:64] (byte+7) | modifier |  |
| `ext8` | [64:72] (byte+8) | immediate |  |
| `ext9` | [72:80] (byte+9) | immediate |  |

*0x?b 10-byte modifier/logic ALU, byte+2 low-nibble 0xf (funary_imm 0x0f / ilogic 0x1f base with a non-zero dst; named forms win by specificity, this covers 0x1f/0x3f/0x4f/0x6f/0x8f/0xcf). SAME 10-byte operand layout as the HW-family sibling b_alu10_lo7 (differs only in the byte+2 op-family low-nibble): dst = byte0 high nibble (reg); src_reg (byte+1 bits0-6) = source register; src_flag (byte+1 bit7) = source-class / uniform flag (=0 gpr in all 484 corpus instances); opsel_hi (byte+2 high nibble) = op-select family (0x4f dominant, then 0xcf/0x8f/0x3f); srcA (byte+3) = second source descriptor (bit7 = single-source marker, set in 10/484); modA/modB (byte+4/+5) = modifier/mode words (byte+4 0x22 dominant); z6 (byte+6) = reserved/pad (const 0, all 491) -- TYPED imm; outmod (byte+7) = output/rounding modifier (0x10/0x04/0x80); ext8/ext9 (byte+8/+9) = operand/coefficient tail (const 0 in-corpus) -- TYPED imm (pad/coefficient words). EXP-M4-13 R8: z6/ext8/ext9 RE-TYPED raw->imm. Per-op-select tail semantics NOT characterised (family-level).*

### `reg_move_c0`

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0xb, bits[16:20]==0x0  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `src_reg` | [8:15] (byte+1) | register |  |
| `src_flag` | [15:16] | modifier | `0x0`=gpr; `0x1`=uniform/class |
| `src_class` | [20:24] | enum | `0x0`=0x00 const-zero/scope-prep; `0x2`=0x20; `0x6`=0x60 |
| `op_desc` | [24:32] (byte+3) | enum | `0x0`=plain; `0x2`=src-class-0x02 (std140 uniform->storage); `0x4`=size/type-04 |

*Compact 4-byte register move, byte+2 low-nibble 0 (const-zero / scope-prep source-class family). dst = byte0 high nibble (reg). src_reg (byte+1 bits0-6) = source register -- ALWAYS 0 in all 1545 corpus instances (this low-nibble-0 form is the const-zero / scope-prep move; src_flag byte+1 bit7 also always 0). src_class (byte+2 high nibble) = source register-bank / operand-class selector: 0x0 (const-zero, dominant), 0x2, 0x6. op_desc (byte+3) = operand/size descriptor (0x00 plain dominant; 0x02 is the std140 uniform->storage matrix-column variant; 0x04 a size/type code) -- located operand-descriptor field, per-value size/type meaning inferred.*

### `reg_move_c1`

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0xb, bits[16:20]==0x1  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `src_reg` | [8:15] (byte+1) | register |  |
| `src_flag` | [15:16] | modifier | `0x0`=gpr; `0x1`=uniform/class |
| `src_class` | [20:24] | enum | `0x0`=0x01; `0x2`=0x21; `0x6`=0x61; `0xa`=0xa1; `0xc`=0xc1; `0xe`=0xe1 |
| `op_desc` | [24:32] (byte+3) | enum | `0xc`=desc-0c; `0x4`=desc-04; `0x8`=desc-08; `0x0`=plain; `0x2`=src-class-0x02 |

*Compact 4-byte register move, byte+2 low-nibble 1. dst = byte0 high nibble (reg). src_reg (byte+1 bits0-6) = source register; src_flag (byte+1 bit7) = source-class / uniform flag (set for uniform-bank sources, e.g. byte+1 0x80/0x82). src_class (byte+2 high nibble) = source register-bank / operand-class selector: 0x2 (0x21, dominant), 0x0, 0x6, 0xa, 0xc, 0xe. op_desc (byte+3) = operand/size descriptor: 0x0c dominant, then 0x04/0x08/0x00/0x02 -- tightly covaries with src_class (src_class 0x2 -> op_desc {0c,04,08}). Located operand-descriptor field; per-value size/type meaning inferred.*

### `reg_move_c9`

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0xb, bits[16:20]==0x9  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `src_reg` | [8:15] (byte+1) | register |  |
| `src_flag` | [15:16] | modifier | `0x0`=gpr; `0x1`=uniform/class |
| `src_class` | [20:24] | enum | `0x0`=0x09; `0x2`=0x29; `0x4`=0x49; `0x6`=0x69; `0x8`=0x89; `0xc`=0xc9 |
| `op_desc` | [24:32] (byte+3) | enum | `0x4`=desc-04; `0x8`=desc-08; `0x2`=src-class-0x02; `0x0`=plain |

*Compact 4-byte register move, byte+2 low-nibble 9 (RT-query / matrix-marshalling source-class family). dst = byte0 high nibble (reg). src_reg (byte+1 bits0-6) = source register; src_flag (byte+1 bit7) = source-class / uniform flag. src_class (byte+2 high nibble) = source register-bank / operand-class selector: 0x2 (0x29, dominant), 0x0, 0x4, 0x8, 0xc, 0x6. op_desc (byte+3) = operand/size descriptor: 0x04 dominant, then 0x08/0x02 -- covaries with src_class (src_class 0x2 -> op_desc {04,08}). Located operand-descriptor field; per-value size/type meaning inferred.*

### `reg_move_cb`

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0xb, bits[16:20]==0xb  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `src` | [8:16] (byte+1) | register |  |
| `form` | [16:24] (byte+2) | raw/unmapped |  |
| `b3` | [24:32] (byte+3) | raw/unmapped |  |

*Compact 4-byte pack / bitcast / convert move, byte+2 low-nibble 0xb (0x0b/0x1b/0x2b/0x3b). Appears in conversions_pack / bitcast_vec / pack_norm and the 64-bit int helpers. Family-level.*

### `tg_atomic_prep`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0xb, byte+2==0x06  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `src` | [8:16] (byte+1) | register |  |
| `form` | [16:24] (byte+2) | enum | `0x6`=tg_atomic_rmw_prep |
| `body` | [24:64] (byte+3) | raw/unmapped |  |

*Threadgroup-atomic RMW descriptor prep (8B). byte0 low-nibble 0xb, byte+2==0x06; sets up the atomic-value / descriptor for a threadgroup atomic RMW. dst=byte0 hi nibble (scope/reg).*

### `b_alu14_c83`

- **Length:** 14 bytes  ·  **Match:** bits[0:4]==0xf, bits[7:8]==0x0, byte+2==0x83  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `form` | [4:7] | enum | `0x3`=form_3f |
| `reg_a` | [8:16] (byte+1) | register |  |
| `reg_b` | [24:32] (byte+3) | register |  |
| `fmt4` | [32:40] (byte+4) | modifier |  |
| `src_lo` | [40:48] (byte+5) | modifier |  |
| `fmt6` | [48:56] (byte+6) | modifier |  |
| `srcB_reg` | [56:64] (byte+7) | register |  |
| `rsv8` | [64:72] (byte+8) | modifier |  |
| `rsv9` | [72:80] (byte+9) | modifier |  |
| `fmt10` | [80:88] (byte+10) | modifier |  |
| `rsv11` | [88:96] (byte+11) | modifier |  |
| `srcU_reg` | [96:104] (byte+12) | register |  |
| `srcU_desc` | [104:112] (byte+13) | modifier |  |

*Low-nibble-0xf 14-byte integer/simd ALU (byte+2 == 0x83 form), distinct from the iadd2/imad 0x9f/0x1f family (byte+2==0x54). ENCODING (typed, no traversal recipe): form-selector (byte0 hi), a register PAIR naming one register in-place (byte+1/+3), a GPR source (byte+7), a uniform/traversal-state source operand (byte+12/+13), fixed format bytes (byte+4/+6/+10 = 03/80/03) and reserved const-0 slots (byte+5/+8/+9/+11). Appears back-to-back in RT-traversal coordinate/index getters and the log2(N) shuffle+multiply integer simd-prefix/product reduction trees. Exact arithmetic NOT resolved (needs splice); operand/format bit TYPES resolved.*

### `if_push_pred`

- **Length:** 4 bytes  ·  **Match:** byte+0==0x0f, bits[8:12]==0x5  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `pred` | [12:16] | raw/unmapped |  |
| `scope` | [16:24] (byte+2) | raw/unmapped |  |
| `level` | [24:32] (byte+3) | raw/unmapped |  |

*Execution-mask PUSH / if-enter, PREDICATE variant (4B). byte0 0x0f, byte+1 low nibble == 5 with a non-zero HIGH nibble selecting a predicate/condition register (the plain 0x05 base is if_push). byte+2 = CF marker (0x54 outer / 0x56 last-use), byte+3 = nesting level. Pairs with the following 0f 01 jump_cond as the if/loop test-and-branch in the RT-query and integer simd-prefix kernels; paired with a later 0f 06 pop_reconverge.*

### `b_alu14_prep2`

- **Length:** 2 bytes  ·  **Match:** bits[0:4]==0x2, bits[8:9]==0x1  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `sel` | [8:16] (byte+1) | raw/unmapped |  |

*2-byte compact PREP word preceding a b_alu14 (byte+2==0x83 int/simd ALU). byte0 low nibble 2, high nibble = dst reg; byte+1 = (dst<<1)|1 (the compact register field, size bit set). A per-operand register declaration / high-half select emitted right before the 14-byte ALU op in the RT getter and integer simd-reduction trees. Distinct from the 6-byte low-nibble-2 min/max (whose byte+2 is a min/max op-select, not a b_alu14 leader).*

### `int_alu_ehi`

- **Length:** 10 bytes  ·  **Match:** byte+0==0xef, byte+2==0x54, byte+9==0x40  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `flags` | [8:16] (byte+1) | modifier |  |
| `dst` | [24:32] (byte+3) | register |  |
| `opmode` | [32:40] (byte+4) | modifier |  |
| `b5` | [40:48] (byte+5) | modifier |  |
| `srcdesc` | [48:56] (byte+6) | modifier |  |
| `srcB` | [56:64] (byte+7) | modifier |  |
| `srcC` | [64:72] (byte+8) | modifier |  |

*Integer address/index ALU (0xef, 10B), the std140 uniform->storage matrix-copy form. dst=byte+3 (reg). All other bytes are LOCATED but role-typed 'mod' (flag/op-select/source-descriptor): flags (byte+1, {0x00,0x10,0x20}), opmode (byte+4, 6 op-select values), b5 (byte+5, {0x02,0x0a}), srcdesc (byte+6, {0x21,0x27,0x29,0x2d}), srcB (byte+7, low nibble always 0x2 = a source-descriptor+register nibble), srcC (byte+8, operand/immediate). NEGATIVE reproduction result: own hand-written MSL emits 0x9f (iadd) for equivalent integer address math -- 0xef could NOT be own-MSL-reproduced, so the operand bytes are typed by LOCATED role only (from committed permissive Dawn/Tint std140 shaders), NOT own-MSL single-toggle. srcB/srcC register interpretation needs splice.*

### `vtx_out_pos`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0xb, byte+1==0x00, byte+2==0x26, byte+3==0x00, byte+4==0x40, byte+5==0x00, byte+6==0x00  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `slot` | [56:64] (byte+7) | immediate |  |

*Vertex-stage output-position / attribute op. byte0 high nibble = dst reg; byte+7 = varying/output slot (0x04/0x08/0x0c/0x10/0x14). Bytes +4..+7 (`40 00 00 SS`) were the dominant spurious 0x40 root desync before this op was lengthed 8.*

### `vary_slot`

- **Length:** 4 bytes  ·  **Match:** byte+0==0x00, byte+2==0x40  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `sel` | [8:16] (byte+1) | raw/unmapped |  |
| `slot` | [24:32] (byte+3) | immediate |  |

*Vertex varying-output SLOT descriptor emitted immediately before each `57 SS 54 ..` vary_store; byte+3 = the varying slot (monotone, tracks the store slot). byte+1 (sel) in {0x04,0x0a,0x0c} = the output-class form.*

### `vtx_coord_xform`

- **Length:** 10 bytes  ·  **Match:** byte+0==0x17, byte+2==0xa2, byte+3==0xb0  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `mode` | [8:16] (byte+1) | raw/unmapped |  |
| `sel` | [32:40] (byte+4) | raw/unmapped |  |
| `operand` | [40:80] (byte+5) | raw/unmapped |  |

*VERTEX-stage coordinate / position transform op. Reads a vertex-array / constant-indexed coordinate and produces the clip-space position or a varying coordinate. byte+2==0xa2, byte+3==0xb0 are the fixed operand-selector pair that statically distinguish it from the compute-stage 0x17 simd_ballot (byte+2==0x54/0x56) with which it shares byte0 and length (10). The operand bytes are left raw (the coordinate-select sequence is not reconstructed, clean-room rule 5).*

### `mesh_out_src`

- **Length:** 2 bytes  ·  **Match:** byte+0==0x04  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `sel` | [8:16] (byte+1) | raw/unmapped |  |

*MESH-stage compact source op feeding the immediately-following device store (byte+2==0xe7) of a mesh vertex/primitive output. Occupies the same structural slot as the 8-byte sr_read_wide (mesh_point `04 88 06 ..`) but is a distinct 2-byte compact encoding (byte+1 < 0x80). byte+1 left raw.*

### `isel8`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x2, bits[16:19]==0x7  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `cmpA` | [8:16] (byte+1) | register |  |
| `opsel` | [19:24] | opcode-select | `0x4`=sel(0x27); `0x5`=sel(0x2f); `0x1`=sel(0x0f); `0x3`=sel(0x1f); `0x0`=sel(0x07) |
| `cmpB` | [24:32] (byte+3) | register |  |
| `cmp_mode` | [32:40] (byte+4) | modifier |  |
| `selTrue` | [40:48] (byte+5) | register |  |
| `cc` | [48:56] (byte+6) | enum | `0x2`=fcmp_gt; `0x3`=fcmp_lt; `0x4`=ucmp_gt; `0x5`=ucmp_lt; `0x6`=scmp_gt; `0x7`=scmp_lt; `0x0`=eq_form |
| `flags` | [56:64] (byte+7) | modifier |  |

*d = (cmpA CC cmpB) ? selTrue : <folded-false> ; register-operand integer/float compare-SELECT, NARROW 8-byte form (no trailing false-operand word -- the false value is implicit/folded, e.g. a 0/1 result or a reused comparand). byte0 low-nibble 2 = group; byte0 HIGH nibble = dst r0..r15; byte+1/+3 = the two compare/predicate SOURCE registers (cmpA/cmpB); byte+2 low 3 bits == 0b111 identifies the register-select forms (op variants 0x07/0x0f/0x1f/0x27/0x2f, upper 5 bits = opsel); byte+4 = compare-mode descriptor; byte+5 = selTrue register; byte+6 = condition-code selector; byte+7 = control/scheduling flags. The 0x25 8-byte sibling (isel_reg8) and 0x2f 10-byte sibling (isel_reg) are more-specific and still win their signatures.*

### `isel10`

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0x2, bits[16:19]==0x7  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `cmpA` | [8:16] (byte+1) | register |  |
| `opsel` | [19:24] | opcode-select | `0x4`=sel(0x27); `0x0`=sel(0x07); `0x1`=sel(0x0f); `0x3`=sel(0x1f); `0x7`=sel(0x3f) |
| `cmpB` | [24:32] (byte+3) | register |  |
| `cmp_mode` | [32:40] (byte+4) | modifier |  |
| `selTrue` | [40:48] (byte+5) | register |  |
| `cc` | [48:56] (byte+6) | enum | `0x2`=fcmp_gt; `0x3`=fcmp_lt; `0x4`=ucmp_gt; `0x5`=ucmp_lt; `0x6`=scmp_gt; `0x7`=scmp_lt; `0x0`=eq_form |
| `flags` | [56:64] (byte+7) | modifier |  |
| `selFalse_file` | [64:72] (byte+8) | modifier |  |
| `selFalse` | [72:80] (byte+9) | register |  |

*d = (cmpA CC cmpB) ? selTrue : selFalse ; register-operand compare-SELECT, WIDE 10-byte form carrying the trailing false-operand word (byte+8:9). byte+2 low 3 bits == 0b111. byte+1/+3 = compare source registers; byte+4 = compare-mode descriptor; byte+5 = selTrue; byte+6 = condition code; byte+7 = scheduling flags; byte+8:9 = false-operand descriptor (byte+9 = selFalse register, or a small immediate in the 0/1-const select sub-form). The already-named 0x2f (isel_reg) and 0x27/0x81/0x22 (rt_transform_test) forms are more-specific and still win.*

### `isel10_c`

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0x2, bits[16:19]==0x5  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `cmpA` | [8:16] (byte+1) | register |  |
| `opsel` | [19:24] | opcode-select | `0x4`=sel(0x25); `0x5`=sel(0x2d); `0x0`=sel(0x05); `0x2`=sel(0x15); `0x1`=sel(0x0d) |
| `cmpB` | [24:32] (byte+3) | register |  |
| `cmp_mode` | [32:40] (byte+4) | modifier |  |
| `selTrue` | [40:48] (byte+5) | register |  |
| `cc` | [48:56] (byte+6) | enum | `0x2`=fcmp_gt; `0x3`=fcmp_lt; `0x4`=ucmp_gt; `0x5`=ucmp_lt; `0x6`=scmp_gt; `0x7`=scmp_lt; `0x0`=eq_form |
| `flags` | [56:64] (byte+7) | modifier |  |
| `selFalse_file` | [64:72] (byte+8) | modifier |  |
| `selFalse` | [72:80] (byte+9) | register |  |

*d = (cmpA CC cmpB) ? selTrue : selFalse ; register/immediate-operand compare-SELECT, WIDE 10-byte form with byte+2 low 3 bits == 0b101 (op variants 0x05/0x0d/0x15/0x25/0x2d). Structurally identical to isel10 (same field layout): byte+1/+3 = compare sources, byte+4 = compare-mode, byte+5 = selTrue, byte+6 = condition code, byte+7 = flags, byte+8:9 = false-operand word (byte+9 = selFalse register, or a small immediate). 0x25 = the wide (immediate-operand) select; 0x2d = the integer division/modulo QUOTIENT correction select. The division algorithm is NOT reconstructed (rule 5).*

### `n2_compact2`

- **Length:** 2 bytes  ·  **Match:** byte+0==0x02, byte+1==0x00  ·  **Provenance:** mixed

*2-byte compact low-nibble-2 helper `02 00` (dst r0, byte+1 == 0x00). A compiler-internal select/predicate/frame marker emitted between other ops (e.g. after a fence before a frame-marker, or between a subgroup-shuffle and an iadd). Distinct from the b_alu14_prep2 compact word (byte+1 bit0 == 1) and the 6-byte iminmax (real op-select in byte+2). Length-only; semantics deliberately NOT reconstructed (clean-room rule 5).*

### `n2_op8`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x2  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `srcA_desc` | [8:16] (byte+1) | raw/unmapped |  |
| `opsel` | [16:24] (byte+2) | raw/unmapped |  |
| `body` | [24:64] (byte+3) | raw/unmapped |  |

*Generic 8-byte low-nibble-2 op (dst = byte0 high nibble), catch-all for 8-byte forms that are NOT the register-operand SELECTs (isel8, byte+2 low3==7) nor the 0x25 isel_reg8. In practice the transcendental SFU RANGE-REDUCTION select (byte+1 == 0xc2, byte+2 in {0x19,0x29,0x49,0x59}, tail `.. 80 08`): a compiler-generated argument-reduction step. Length-classified only; SFU per-op-select semantics deliberately NOT reconstructed (clean-room rule 5).*

### `n2_op10`

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0x2  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `src` | [8:16] (byte+1) | register |  |
| `opsel` | [16:24] (byte+2) | enum | `0x21`=sfu_roundmode_marshal; `0x0`=zero_pad_overread |
| `opdesc` | [24:32] (byte+3) | modifier |  |
| `immword` | [32:80] (byte+4) | immediate |  |

*10-byte low-nibble-2 op (dst = byte0 high nibble), the catch-all for 10-byte forms not covered by the named selects (isel10/isel10_c/isel_reg/rt_transform_test). Dominant real member: the SFU transcendental range-reduction / round-mode MARSHALLING op (byte+2==0x21) -- byte+1 = source register, byte+3 = sub-op descriptor, byte+4:9 = a coefficient/marshalling immediate word. Also absorbs the all-zero `X2 00 00 ..` OVER-READ artifact (byte+2==0x00) of the byte0==0x22 default-to-10 length rule. The SFU / RT-getter marshalling SEQUENCE is deliberately NOT reconstructed (rule 5).*

### `cvt_i2f_src`

- **Length:** 8 bytes  ·  **Match:** byte+0==0xa7, byte+1==0x17  ·  **Provenance:** inferred

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `src_cache` | [16:24] (byte+2) | modifier |  |
| `dst_desc` | [24:32] (byte+3) | register |  |
| `src_class` | [32:40] (byte+4) | modifier |  |
| `src` | [40:48] (byte+5) | register |  |
| `cvtop` | [48:56] (byte+6) | opcode-select | `0xac`=int2f[32->32]; `0xa0`=i2f[16->16]; `0xa4`=i2f[16->32]; `0xa8`=i2f[32->16]; `0xb4`=i2f[8->32]; `0x8e`=i2f[sibling]; `0x8c`=i2f[sibling2] |
| `signflag` | [56:64] (byte+7) | modifier |  |

*d = float(a) ; integer/uint -> float/half convert (round to nearest even). The byte+1==0x17 sibling of cvt_i2f (byte+1==0x07): byte+1 bit4 marks the SOURCE-CONSUMED-BY-A-FOLLOWING-ALU-OP routing (byte+2==0x54 result-consumed vs 0x56 standalone/last-use); the convert itself and the byte+6 width / byte+7 sign (bit6=signed i2f vs unsigned u2f) fields are IDENTICAL to the HW-VALIDATED cvt_i2f.*

### `copysign`

- **Length:** 4 bytes  ·  **Match:** byte+0==0x07, byte+1==0xc2, byte+2==0x88  ·  **Provenance:** inferred

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `operands` | [24:32] (byte+3) | raw/unmapped |  |

*d = copysign(a, b) = |a| with the sign bit of b (float). 4 bytes: 07 c2 88 <ops>. byte0 0x07 low-nibble-7 sign-combine ALU op; byte+3 carries the src/dst register operand descriptor. The half (fp16) copysign is a separate byte0-0x0f op, not this one. MORE SPECIFIC than scoreboard_fence (24 vs 9 match bits) so decode_one prefers it for `07 c2 88 xx`; semantically it is ALU, not a memory fence.*

### `ibfe_mesh_attr`

- **Length:** 12 bytes  ·  **Match:** byte+0==0x27, byte+1==0x00, byte+2==0x66  ·  **Provenance:** inferred

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `operands` | [24:64] (byte+3) | raw/unmapped |  |
| `opdesc` | [64:72] (byte+8) | enum | `0xf0`=reg-operand; `0xc0`=imm-operand |
| `tail` | [72:96] (byte+9) | raw/unmapped |  |

*d = extract_bits(packed_attr, off, cnt) -- bitfield-extract of a packed flat PER-PRIMITIVE mesh attribute in the fragment stage (source-address mode byte+2==0x66). 12-byte operand form (byte+8==0xf0 register-operand tail), the same bitfield-extract family as the 0xa7 ibfe / 0x27 ibfins but with the mesh packed-attribute source mode.*

### `ret_luse`

- **Length:** 4 bytes  ·  **Match:** byte+0==0x8f, byte+2==0x56  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `linkmode` | [8:16] (byte+1) | enum | `0x2`=leaf; `0x12`=nonleaf_restore_link; `0x4`=cf_merge; `0x5`=cf_merge_push |
| `tail` | [24:32] (byte+3) | raw/unmapped |  |

*function RETURN / CF merge, LAST-USE variant: `8f <lm> 56 <t>` (4 B). Identical to ret except byte+2 == 0x56 (0x54 | bit17): bit17 is the source cache/last-use hint the compiler sets when the merge consumes a value for the last time -- a scheduling hint, not an op change (same bit toggles 0x54<->0x56 on simd_reduce / rt_ray_mem / if_push). byte+1 selects leaf/nonleaf/cf-merge exactly as ret. NO encoded target.*

### `mem_fence8`

- **Length:** 8 bytes  ·  **Match:** byte+0==0x07, byte+1==0x00, byte+2==0x54, byte+4==0x80  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `mask` | [24:32] (byte+3) | modifier |  |
| `tail` | [40:64] (byte+5) | raw/unmapped |  |

*8-byte 0x07-family memory / scoreboard FENCE, device/traversal-buffer scope (`07 00 54 <mask> 80 00 00 00`). Same fence/ordering family as threadgroup_barrier (6B, byte+1 0x04) and link_save_restore (8B, byte+4 0x81); this is the byte+4==0x80 scope form the intersection_query traversal emits to order accesses to the ray-query state buffer around its address arithmetic. byte+3 = a scope/mask selector (0x14/0x0c observed).*

### `rtq_dualsrc`

- **Length:** 12 bytes  ·  **Match:** byte+0==0x17, byte+1==0x02, byte+2==0x00  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b3` | [24:32] (byte+3) | modifier |  |
| `opA` | [32:64] (byte+4) | register |  |
| `opB` | [64:96] (byte+8) | register |  |

*intersection_query traversal dual-source op (12 B): reads two operands (opA at +4..+7, opB at +8..+11), each a 4-byte source-operand descriptor, and updates ray-query state inside the `while(q.next())` loop. byte0/1/2 = `17 02 00` opcode; byte+3 a mode byte (0x00, rarely 0x86/0x88). The two operand words vary as register indices across the get_committed_* / candidate / commit kernels. Exact operand sub-fields and precise semantics (which traversal quantity) need an isolating splice; NOT the traversal record layout, just this single op's encoding.*

### `n4_cf_word`

- **Length:** 4 bytes  ·  **Match:** byte+0==0x04, byte+1==0x01, byte+2==0x00  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b3` | [24:32] (byte+3) | raw/unmapped |  |

*4-byte compute/intersection_query compact control word `04 01 00 00`. Emitted immediately before a pop_reconverge / rt_ray_mem / threadgroup_barrier in the divergent-CF and ray-query kernels -- a reconverge/predicate-prep marker in the 0x04 group. (The flat 0x04->8 centroid rule previously over-read it by 4 and hid the following op.) Precise role needs a splice; length 4 is anchored (+4 lands on the next op leader in every corpus occurrence).*

### `n4_rt_word`

- **Length:** 4 bytes  ·  **Match:** byte+0==0x04, byte+2==0x20, byte+3==0x80  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [8:16] (byte+1) | register |  |

*4-byte intersection_query-context compact op `04 <d> 20 80` (byte+1 = 0x22/0x42 destination selector). Emitted before an if_push / frame_marker / reg_move in the ray-query traversal setup. (The flat 0x04->8 rule previously over-read it by 4.) byte+3==0x80 distinguishes it from the fragment reads (byte+3==0x00). Role needs a splice; length 4 anchored (+4 -> next op leader in all occurrences).*

### `n1_word`

- **Length:** 2 bytes  ·  **Match:** byte+0==0x01, byte+1==0x00  ·  **Provenance:** mixed

*2-byte compact control/scheduling word `01 00` (low-nibble-1 group). Appears between full ops before a wide variety of leaders (jump / convert / frame_marker / falu / fspecial / store / icmp) -- a no-op-like scheduling / predicate-reset word, the low-nibble-1 sibling of pad_operand. byte+1==0x00 invariant (no decoded payload). Exact role needs a splice.*

### `n3_word`

- **Length:** 2 bytes  ·  **Match:** byte+0==0x03, byte+1==0x02  ·  **Provenance:** mixed

*2-byte compact word `03 02` (low-nibble-3 group). The SFU range-reduction / predicate operand marker the transcendental and select paths emit between full ops (byte+1==0x02 invariant). Named as a 2-byte token ONLY -- its coefficient payload (in the longer SFU forms) is intentionally NOT bit-decoded (clean-room rule 5: no range-reduction recipe). Sibling of pad_operand.*

### `falu_compact4`

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0x9  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `src` | [8:16] (byte+1) | register |  |
| `opsel` | [16:19] (byte+2) | opcode-select | `0x4`=fadd; `0x5`=fmul; `0x6`=fma; `0x7`=fmul_interp |
| `opmode` | [19:24] | modifier |  |
| `operand` | [24:32] (byte+3) | register |  |

*4-byte COMPACT float ALU (accumulate / move; arithmetic-enable bit clear). The compiler emits it interleaved with the 6-byte falu2 forms for reductions and fast-math seeds. byte+2 = compact-op mode selector (0x18/0x38/0x19/0x21/0x30/0x31/0x39 observed; the 0x30/0x31 pair carries the source cache/last-use hint bit). dst=b0 hi nibble, src=byte+1, operand=byte+3. Sibling of the HW-VALIDATED falu_acc (EXP-0025), covering the compact modes falu_acc's specific match does not.*

### `falu2_srcmod10`

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0x9, bits[17:18]==0x0, bits[18:19]==0x1  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `srcA_size` | [8:9] (byte+1) | enum | `0x1`=b32; `0x0`=b16 |
| `srcA_reg` | [9:16] | register |  |
| `opsel` | [16:19] (byte+2) | opcode-select | `0x4`=fadd; `0x5`=fmul; `0x6`=fma; `0x7`=fmul_interp |
| `opflags` | [19:24] | modifier |  |
| `srcB_size` | [24:25] (byte+3) | enum | `0x1`=b32; `0x0`=b16 |
| `srcB_reg` | [25:32] | register |  |
| `ctrl` | [32:39] (byte+4) | modifier |  |
| `srcB_imm` | [39:40] | modifier |  |
| `mod_lo` | [40:43] (byte+5) | modifier |  |
| `srcB_neg` | [43:44] | modifier |  |
| `mod_hi` | [44:48] | modifier |  |
| `ext_srcmod` | [48:80] (byte+6) | modifier |  |

*10-byte EXTENDED 2-source float ALU (abs-source form): the falu2 op in bits [0:48] (opsel 4=fadd / 5=fmul, bit17=0/bit18=1 -- identical to the 8-byte falu2_ext) plus a 32-bit source-modifier / trailing-operand word (byte+6..+9). Length 10 = base 6 + 4 modifier bytes (HW model 6+2*(byte+4&3), byte+4 low2==2 => abs source slot). The abs()-around-a-source sibling of falu2_ext.*

### `falu3_srcmod12`

- **Length:** 12 bytes  ·  **Match:** bits[0:4]==0x9, bits[17:18]==0x1  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `srcA_size` | [8:9] (byte+1) | enum | `0x1`=b32; `0x0`=b16 |
| `srcA_reg` | [9:16] | register |  |
| `opsel` | [16:19] (byte+2) | opcode-select | `0x4`=fadd; `0x5`=fmul; `0x6`=fma; `0x7`=fmul_interp |
| `opflags` | [19:24] | modifier |  |
| `srcB_size` | [24:25] (byte+3) | enum | `0x1`=b32; `0x0`=b16 |
| `srcB_reg` | [25:32] | register |  |
| `ctrl` | [32:39] (byte+4) | modifier |  |
| `srcB_imm` | [39:40] | modifier |  |
| `mod_lo` | [40:43] (byte+5) | modifier |  |
| `srcB_neg` | [43:44] | modifier |  |
| `mod_hi` | [44:48] | modifier |  |
| `ext_srcmod` | [48:96] (byte+6) | modifier |  |

*12-byte float ALU: the fma op in bits [0:48] (bit17=1 3-source form, as falu3/falu3_ext) plus a 48-bit third-source + source-modifier region (byte+6..+11) -- fma with abs/saturate source modifiers, and the extended coordinate fma. Length 12 = base 6 + 6 bytes (3rd source operand + modifier), the longest float-ALU form.*

### `rt_query_traverse2`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0xf, byte+1==0x80, byte+2==0x86  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `getter` | [24:32] (byte+3) | modifier |  |
| `sel` | [32:40] (byte+4) | enum | `0x7`=sel0; `0xf`=sel1 |
| `b5` | [40:48] (byte+5) | immediate |  |
| `b6` | [48:56] (byte+6) | modifier |  |
| `b7` | [56:64] (byte+7) | immediate |  |

*8-byte low-nibble-f ray-query TRAVERSAL getter, the byte+5==0x02 sibling of rt_query_traverse (byte+5==0x22). Emitted in intersection_query traversal/getter loops (byte+1==0x80, byte+2==0x86 SFU-datapath marker). dst = byte0 high nibble (r0..r15, family convention). getter (byte+3) = the traversal step / property selector; sel (byte+4) = the sel0/sel1 result-lane selector (same enum as rt_query_traverse). b5/b6/b7 = operand/descriptor words (values partial, need splice).*

### `half_alu_ext8`

- **Length:** 8 bytes  ·  **Match:** byte+0==0x10  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [8:16] (byte+1) | register |  |
| `opsel` | [16:19] (byte+2) | opcode-select | `0x4`=hadd; `0x5`=hmul; `0x6`=hfma |
| `opflags` | [19:24] | modifier |  |
| `srcA` | [24:32] (byte+3) | register |  |
| `srcB_desc` | [32:40] (byte+4) | modifier |  |
| `b5` | [40:48] (byte+5) | modifier |  |
| `rsv6` | [48:56] (byte+6) | modifier |  |
| `b7_lo` | [56:57] (byte+7) | modifier |  |
| `saturate` | [57:58] | modifier | `0x0`=no clamp; `0x1`=output-clamp/saturate ON (clamps to [0,1]) |
| `b7_mid` | [58:63] | modifier |  |
| `op_valid_marker` | [63:64] | modifier | `0x0`=op nulled (result 0); `0x1`=op valid (required) |

*8-byte EXTENDED native-half (fp16) float ALU, the length-polymorphic sibling of the 6-byte half_alu (byte0==0x10). dst = byte+1, opsel/opflags = byte+2 (reused from the HW-anchored half_alu layout, EXP-0033). HW-VALIDATED (splice, A18 EXP-M4-14, own-MSL pureh.metal k_pureaddsat `10 03 1c 02 01 00 00 82` a=8 b=1, and hfma.metal k_hfma `10 02 1e 03 81 04 00 c0`): opsel gains 6=hfma (byte+2=0x1e, half fma compiles to this 8-byte form with 3 sources in byte+3/+4/+5). srcA (byte+3) = srcA register (same as the 6-byte form). srcB_desc (byte+4) = srcB operand descriptor (required 0x01 in the add+sat instance; carries the fma srcA-negate too -- k_hfma_neg sets byte+7 0xc0->0xc8). b5 (byte+5) = largely inert (bits3/4 null in this instance). rsv6 (byte+6) = fully INERT/reserved in the add+saturate instance (every swept value 0x00..0xc0 kept the result). byte+7 carries the output-clamp and op-valid marker: saturate (byte+7 bit1) = the saturate/output-clamp that grows half_alu into this 8-byte form (0x82 clamps saturate(9)->1, 0x80 (bit1 clear) passes 9 unclamped); op_valid_marker (byte+7 bit7) is a required op-valid marker (clearing 0x80 nulls the ext8 op -> result 0). b7_lo/b7_mid = the remaining byte+7 bits (unresolved).*

### `half_alu_fma12`

- **Length:** 12 bytes  ·  **Match:** byte+0==0x10  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [8:16] (byte+1) | register |  |
| `opsel` | [16:19] (byte+2) | opcode-select | `0x4`=hadd; `0x5`=hmul; `0x6`=hfma |
| `opflags` | [19:24] | modifier |  |
| `srcA` | [24:32] (byte+3) | register |  |
| `ext` | [32:96] (byte+4) | raw/unmapped |  |

*12-byte fp16 form (byte0==0x10). HW-VALIDATED (splice, A18 EXP-M4-14, own-MSL hfma.metal k_hfma_abs): REFINES the prior pure-negative to a POSITIVE existence result -- fma(abs(a),b,c) genuinely compiles to a clean 12-byte 0x10 op `10 02 1e 03 83 04 00 00 00 80 01 00` cleanly FOLLOWED by the e7 store (a=[-8,-2,-4,-1] b=1 c=[1,2,4,8] -> [9,4,8,9]=fma(|a|,b,c)). The 0x10 family is length-polymorphic: 6B=add/mul, 8B=fma or add+saturate, 10B=fma+saturate (`10 02 1e 03 82 04 00 00 00 82`), 12B=fma+abs. opsel 6=hfma (byte+2=0x1e); srcA (byte+3) = srcA register (family-consistent); byte+4 carries the srcB descriptor + abs-modifier bit (0x81 plain-fma -> 0x83 abs). ext (byte+4..+11) is KEPT RAW: for the CLEAN own-compiled fma+abs it is the 3rd source + extended modifier region (partially resolved, entangled), but as a corpus DESCRIPTOR this 12-byte length OVER-CONSUMES -- own-MSL plain half fma is only 8B, and 121/126 corpus half_alu_fma12 instances embed a real op-leader byte (0x9f iadd, 0xa8, 0x54, 0xe7) inside ext (e.g. `10 29 22 00 9f 01 54 02 ...` embeds a whole iadd). So a fixed "always 12B for byte0==0x10" length rule is wrong; the length must be modifier/opsel-aware. ext RAW and FLAGGED for the length-rule owner (audit byte0==0x10 12-byte classification).*

### `falu2_ext8b`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x9, bits[17:18]==0x0, bits[18:19]==0x0  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `srcA_size` | [8:9] (byte+1) | enum | `0x0`=b16; `0x1`=b32 |
| `srcA_reg` | [9:16] | register |  |
| `opsel` | [16:19] (byte+2) | modifier |  |
| `opflags` | [19:24] | modifier |  |
| `srcB_size` | [24:25] (byte+3) | enum | `0x0`=b16; `0x1`=b32 |
| `srcB_reg` | [25:32] | register |  |
| `src2` | [32:40] (byte+4) | register |  |
| `exttail` | [40:64] (byte+5) | raw/unmapped |  |

*8-byte extended float-ALU op-select {0,1} sub-form (bit17==0 AND bit18==0 -- a DISTINCT op class from fadd/fmul). dst/srcA(byte+1)/srcB(byte+3) inherited from the HW-validated falu2_ext layout. src2 (byte+4) = a third source register: byte+4 low bit is set in every corpus instance ((reg<<1)|b32 convention, 22 distinct register values). exttail (byte+5..+7) is KEPT RAW -- HETEROGENEOUS (193/250 distinct 32-bit tails, several containing real op-leader bytes 0xa7/...), so it cannot be honestly typed as one coherent operand block without a per-sub-op splice (candidate over-match/over-consumption, flagged).*

### `falu_srcmod12b`

- **Length:** 12 bytes  ·  **Match:** bits[0:4]==0x9, bits[17:18]==0x0  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `srcA_size` | [8:9] (byte+1) | enum | `0x1`=b32; `0x0`=b16 |
| `srcA_reg` | [9:16] | register |  |
| `opsel` | [16:19] (byte+2) | modifier |  |
| `opflags` | [19:24] | modifier |  |
| `srcB_size` | [24:25] (byte+3) | enum | `0x1`=b32; `0x0`=b16 |
| `srcB_reg` | [25:32] | register |  |
| `ctrl` | [32:39] (byte+4) | modifier |  |
| `srcB_imm` | [39:40] | modifier |  |
| `mod_lo` | [40:43] (byte+5) | modifier |  |
| `srcB_neg` | [43:44] | modifier |  |
| `mod_hi` | [44:48] | modifier |  |
| `ext_srcmod` | [48:96] (byte+6) | modifier |  |

*12-byte EXTENDED 2-source float ALU, op-select bit17==0 sub-form. Identical byte layout to the HW-anchored falu3_srcmod12 but with bit17 clear (falu3_srcmod12 requires bit17==1) -- the fadd/fmul-family (opsel {0,1,4,5}) 12-byte extended form, vs the fma-family (bit17==1) falu3_srcmod12. dst/srcA/srcB HW-validated falu2 positions; opsel typed 'mod' (sub-op values partial). ext_srcmod (byte+6..+11) = 3rd source + modifier region (values need splice).*

### `compute_fence_scoped`

- **Length:** 4 bytes  ·  **Match:** byte+0==0x87  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `kind` | [8:16] (byte+1) | modifier |  |
| `scope` | [16:24] (byte+2) | modifier |  |
| `mask` | [24:32] (byte+3) | modifier |  |

*4-byte compute scoreboard / memory FENCE, 0x87 high-scope family, scoped variants NOT covered by dev_scoreboard_fence (which needs byte+1==0x02, byte+2==0x00). Observed byte+1 in {0x9e,0x8e,0x90,0x86,0x00} and byte+2 in {0x26,0x80,0x02}. 0x87 = the 0x07 scoreboard_fence family with bit7 set (wider memory/device scope). kind (byte+1) = wait/scope descriptor, scope (byte+2) = memory-scope operand, mask (byte+3) = scoreboard mask; the operand VALUE maps are partial (need splice, like the HW-anchored 0x07 scoreboard_fence).*

### `shift_amt_move`

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0xb, bits[16:20]==0xc  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `src_reg` | [8:15] (byte+1) | register |  |
| `src_flag` | [15:16] | modifier | `0x0`=gpr; `0x1`=uniform/class |
| `kind` | [16:24] (byte+2) | enum | `0x1c`=shift_amt; `0x3c`=rotate_amt |
| `op_desc` | [24:32] (byte+3) | modifier |  |

*4-byte compact low-nibble-b move that stages a SHIFT / ROTATE amount (byte+2 low nibble == 0xc; seen as 0x1c shift, 0x3c rotate). dst = byte0 high nibble (r0..r15, lo=b family convention); src_reg/src_flag = byte+1 (source register + gpr/uniform flag, reused from reg_move_c0); op_desc (byte+3) = operand descriptor. Sibling of the reg_move_cX compact-move family.*

### `reg_move_c2var`

- **Length:** 4 bytes  ·  **Match:** bits[0:4]==0xb, bits[20:24]==0x2  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `src_reg` | [8:15] (byte+1) | register |  |
| `src_flag` | [15:16] | modifier | `0x0`=gpr; `0x1`=uniform/class |
| `subform` | [16:20] (byte+2) | modifier |  |
| `op_desc` | [24:32] (byte+3) | modifier |  |

*4-byte compact low-nibble-b register move, byte+2 high-nibble==2 residual (observed byte+2 in {0x22,0x23,0x24,0x26,0x2a}). The (byte+2 hi-nibble 2) 'compact scalar / call-argument MOVE' the length rule already lengths (EXP-0036) but whose specific byte+2 low nibbles fell outside the reg_move_c0/c1/c9/cb set. dst=byte0-hi nibble, src_reg/src_flag=byte+1 (reg_move_c0 layout), subform (byte+2 low nibble) = move sub-class, op_desc (byte+3) = operand descriptor. Least-specific catch-all (8 match bits, appended after reg_move_cX so existing decodes keep the tie).*

### `bf_alu8_var`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x1  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `form` | [8:16] (byte+1) | modifier |  |
| `opsel` | [16:24] (byte+2) | modifier |  |
| `srcA` | [24:32] (byte+3) | register |  |
| `srcB` | [32:40] (byte+4) | register |  |
| `tail` | [40:64] (byte+5) | modifier |  |

*8-byte native-bfloat/half ALU, the byte+1 != 0x02 residual of the 0x11 group. dst=byte0-hi, form(byte+1)/opsel(byte+2) select the bf/half sub-op, srcA=byte+3, srcB=byte+4 (inherited from the HW-validated bf_add_dst operand layout). tail (byte+5..+7) = source-modifier/output-cache tail (same family as bf_add_dst's tail; the HW-validated bf_add scalar has tail byte+6=0xc0 cache, byte+7=0x81 bf-marker). Role-typed 'mod'; the byte+1/byte+2 op-select VALUE map and the per-bit tail map need splice.*

### `op04_len8`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0x4  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst` | [4:8] | register |  |
| `mode` | [8:16] (byte+1) | modifier |  |
| `body` | [16:64] (byte+2) | raw/unmapped |  |

*8-byte low-nibble-4 datapath-read RESIDUE (byte0 low nibble 4; more-specific get_sr / sr_read_wide / rt_intersect win first). RENAMED from the misleading 'frag_pos_read': this is NOT a fragment-position read. HW-VALIDATED NEGATIVE (splice, A18 EXP-M4-14 + census EXP-M4-13 R9): [[position]]/[[front_facing]] lower to get_sr (special-register read, 4B: sr_sel 0xa0/0xa1 position, 0xc5 front_facing) + iter (interpolation), splice-confirmed on live A18 -- see get_sr and iter. This 8-byte op materialises from NONE of 7 distinct own-MSL fragment provocations ([[position]]/[[front_facing]]/[[flat]]/[[centroid]]/[[sample]]/barycentric/sample_id); it appears only in COMPUTE / third-party byte streams (subgroup product/prefix reductions, SFU/transcendental helpers powr/cospi, intersection_query getters) that our own FRAGMENT compiler never emits. The 6-byte body (byte+2..+7) is HETEROGENEOUS: audited over the full corpus (EXP-M4-14 frag04_audit) this length-8 token fires 205x on own compute kernels + 618x on third-party, and byte+2 spans real op-leader bytes {0x00,0x9f iadd,0x1b,0x02,0xe7 store,0x20,0x80,0x62,0x72,0x52,0x39,...}. So the body CANNOT be honestly typed as one coherent operand block (typing it would fabricate a coherence the data contradicts) and the fixed 8-byte length for byte0==0x04 is a CANDIDATE OVER-CONSUMER of a following instruction leader. dst = byte0 high nibble (family convention); mode (byte+1) = per-context mode selector (0x02/0x00/0x42); body kept RAW. FLAGGED for the length-rule owner.*

### `operand_word_x2_h5`

- **Length:** 2 bytes  ·  **Match:** bits[0:4]==0x2, bits[8:9]==0x1, bits[13:14]==0x1  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b0` | [0:8] (byte+0) | immediate |  |
| `b1` | [8:16] (byte+1) | immediate |  |

*NOT A STANDALONE HARDWARE OPCODE. A 2-byte trailing operand / immediate / data WORD whose byte0 low-nibble is 0x2 and byte+1 is an OUT-OF-RANGE operand byte (>=0x20, i.e. one of bits 5/6/7 set). This out-specifies the loosely-matched b_alu14_prep2 (match low-nib-2 + byte+1 bit0=1, whose SEMANTIC invariant byte+1==(dst<<1)|1 forces byte+1<=0x1f), so a genuine compact PREP word (byte+1<=0x1f) still decodes as b_alu14_prep2 while these data words decode as pad. byte0 hi-nibble + byte+1 typed imm; value NOT decoded (rule 5).*

### `operand_word_x2_h6`

- **Length:** 2 bytes  ·  **Match:** bits[0:4]==0x2, bits[8:9]==0x1, bits[14:15]==0x1  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b0` | [0:8] (byte+0) | immediate |  |
| `b1` | [8:16] (byte+1) | immediate |  |

*NOT A STANDALONE HARDWARE OPCODE. A 2-byte trailing operand / immediate / data WORD whose byte0 low-nibble is 0x2 and byte+1 is an OUT-OF-RANGE operand byte (>=0x20, i.e. one of bits 5/6/7 set). This out-specifies the loosely-matched b_alu14_prep2 (match low-nib-2 + byte+1 bit0=1, whose SEMANTIC invariant byte+1==(dst<<1)|1 forces byte+1<=0x1f), so a genuine compact PREP word (byte+1<=0x1f) still decodes as b_alu14_prep2 while these data words decode as pad. byte0 hi-nibble + byte+1 typed imm; value NOT decoded (rule 5).*

### `operand_word_x2_h7`

- **Length:** 2 bytes  ·  **Match:** bits[0:4]==0x2, bits[8:9]==0x1, bits[15:16]==0x1  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b0` | [0:8] (byte+0) | immediate |  |
| `b1` | [8:16] (byte+1) | immediate |  |

*NOT A STANDALONE HARDWARE OPCODE. A 2-byte trailing operand / immediate / data WORD whose byte0 low-nibble is 0x2 and byte+1 is an OUT-OF-RANGE operand byte (>=0x20, i.e. one of bits 5/6/7 set). This out-specifies the loosely-matched b_alu14_prep2 (match low-nib-2 + byte+1 bit0=1, whose SEMANTIC invariant byte+1==(dst<<1)|1 forces byte+1<=0x1f), so a genuine compact PREP word (byte+1<=0x1f) still decodes as b_alu14_prep2 while these data words decode as pad. byte0 hi-nibble + byte+1 typed imm; value NOT decoded (rule 5).*

### `operand_word_a2_01`

- **Length:** 2 bytes  ·  **Match:** byte+0==0xa2, byte+1==0x01  ·  **Provenance:** mixed

*NOT A STANDALONE HARDWARE OPCODE. The single IN-RANGE (byte+1<=0x1f) low-nibble-2 odd operand word that occurs in the corpus (`a2 01`, byte0=0xa2 dst-nibble=10 but byte+1=0x01 which is the compact-reg for dst=0 -- inconsistent with b_alu14_prep2's byte+1==(dst<<1)|1=0x15, so it is NOT a valid prep word). Pinned on the full 16-bit signature (spec 16) so it stays pad without shadowing a legit b_alu14_prep2 (`a2 15`, which never occurs). Value NOT decoded (rule 5).*

### `operand_word`

- **Length:** 2 bytes  ·  **Match:** (none)  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `b0` | [0:8] (byte+0) | immediate |  |
| `b1` | [8:16] (byte+1) | immediate |  |

*NOT A STANDALONE HARDWARE OPCODE. Least-specific 2-byte trailing operand / immediate / SFU-coefficient / inter-op PAD WORD fallback. Reached only after every real 2-byte op (higher match specificity) fails to match, so real ops always win. b0 (byte0) and b1 (byte+1) are raw data bytes typed imm (ROLE is a data word; per-bit value NOT decoded, clean-room rule 5). Consolidates 419 of R9's per-signature operand_word_* descriptors.*

### `m5_reduce`

- **Length:** 10 bytes  ·  **Match:** byte+0==0x2f, byte+1==0x00, byte+4==0x27, byte+5==0x80  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `scope` | [16:24] (byte+2) | enum | `0x4`=simd / device-atomic; `0x0`=quad |
| `datapath` | [24:32] (byte+3) | enum | `0xa`=integer; `0x8`=float |
| `op` | [48:56] (byte+6) | opcode-select | `0xa0`=and; `0xa1`=or; `0xa2`=xor; `0xa3`=add; `0xa6`=min; `0xa7`=max; `0xac`=fadd; `0xae`=fmin; `0xaf`=fmax |
| `opmarker` | [56:64] (byte+7) | modifier |  |
| `b8` | [64:72] (byte+8) | modifier |  |
| `mode` | [72:80] (byte+9) | enum | `0x2`=reduce (full); `0x0`=exclusive-scan (prefix) |

*M5 SIMD-group / quad REDUCE or PREFIX-SCAN (and the device-atomic-on-uniform-address pre-combine, which lowers to the same op). Unified form `2f 00 <scope> <datapath> 27 80 <OP> 02 <b8> <mode>`. byte+2 (scope) = 0x04 SIMD-group / device-atomic, 0x00 quad. byte+3 (datapath) = 0x0a integer, 0x08 float. byte+6 (OP) = a0 and, a1 or, a2 xor, a3 add, a6 min, a7 max, ac float-add (byte+3=0x08 + byte+8=0x08 select the fp datapath). byte+9 (mode) = 0x02 full reduce, 0x00 exclusive prefix-scan. Replaces the A18 0xbf/0x3f/0xb7 reduce op. For a uniform-address atomic the RMW writeback is a separate following memory op; for a divergent per-lane atomic the compiler emits the full memory-family form.*

### `m5_shuffle`

- **Length:** 10 bytes  ·  **Match:** byte+0==0x2f, byte+1==0x00, byte+2==0x21, byte+3==0x1a, byte+4==0x20  ·  **Provenance:** HW-validated

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `op` | [48:56] (byte+6) | opcode-select | `0xa8`=simd_shuffle / broadcast; `0xa9`=simd_shuffle_xor; `0xa0`=quad_shuffle; `0xa1`=quad_shuffle_xor |
| `opmarker` | [56:64] (byte+7) | modifier |  |
| `lane` | [64:72] (byte+8) | immediate |  |
| `b9` | [72:80] (byte+9) | modifier |  |

*M5 SIMD-group / quad SHUFFLE / BROADCAST. Form `2f 00 21 1a 20 00 <OP> 02 <lane> 00`. byte+6 (OP) = a8 simd_shuffle / simd_broadcast, a0 quad_shuffle, a1 quad_shuffle_xor. byte+8 = lane index / xor mask. Distinct op-family from m5_reduce (byte+2==0x21 vs the reducer's scope byte); replaces the A18 0x47/0xc7 shuffle op.*

### `m5_iadd`

- **Length:** 12 bytes  ·  **Match:** byte+0==0x2f, byte+1==0x00, byte+2==0x04, byte+6==0xa3  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `src_form` | [24:32] (byte+3) | enum | `0x3a`=register source; `0x1a`=immediate source |
| `b4` | [32:40] (byte+4) | modifier |  |
| `op` | [48:56] (byte+6) | opcode-select | `0xa3`=add |
| `opmarker` | [56:64] (byte+7) | modifier |  |
| `b8` | [64:72] (byte+8) | modifier |  |
| `operand` | [72:96] (byte+9) | raw/unmapped |  |

*M5 (G17g) split-memory INDEX INTEGER ADD, 12-byte form `2f 00 04 <src_form> 21 00 a3 02 28 ..`. Emitted for the address-index arithmetic of the split memory model (e.g. gid+K feeding m5_addr_gen). byte+3 = 0x3a register-source / 0x1a immediate-source; byte+6==0xa3 = add. Distinct 12-byte opcode from the inherited 0x9f/0x1f iadd2 and from the 10-byte m5_reduce (which has byte+4==0x27). Fixes the fspecial(10) mis-length that desynced ld_2sum.*

### `m5_alu`

- **Length:** 12 bytes  ·  **Match:** byte+0==0x27, bits[52:56]==0xa  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `mode` | [8:16] (byte+1) | modifier |  |
| `sub` | [16:24] (byte+2) | modifier |  |
| `b3` | [24:32] (byte+3) | modifier |  |
| `b4` | [32:40] (byte+4) | modifier |  |
| `b5` | [40:48] (byte+5) | modifier |  |
| `op` | [48:56] (byte+6) | opcode-select | `0xa0`=and; `0xa1`=or; `0xa2`=xor; `0xa3`=add; `0xa6`=min; `0xa7`=max; `0xa8`=shift/shuffle-class (inferred); `0xa9`=op-a9 (inferred); `0xab`=op-ab (inferred); `0xac`=fadd; `0xae`=op-ae (inferred); `0xaf`=op-af (inferred) |
| `opmarker` | [56:64] (byte+7) | modifier |  |
| `operand` | [64:96] (byte+8) | raw/unmapped |  |

*M5 (G17g) general COMPUTE-ALU op, 12-byte form. byte0==0x27 = the integer/general datapath leader (sibling of the 0x2f reduce/shuffle/iadd leader). byte+6 = OPERATION selector, hi-nibble 0xa: a0 and, a1 or, a2 xor, a3 add, a6 min, a7 max, ac float-add -- the SAME enum HW-splice-validated for m5_reduce (EXP-M5-09). byte+1 = form/dst descriptor (0x00/0x01/0x02); byte+2..+5 = operand/mode descriptors; byte+7..+11 = operand/immediate word. This descriptor NAMES the family and its op-selector; the exact operand register/immediate bit-packing is byte-diff-located but NOT individually splice-validated (and the SFU/coefficient words are intentionally kept raw, clean-room rule 5).*

### `m5_tex`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0xf, byte+2==0x12, bits[36:40]==0x4, byte+5==0x80  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `result_reg` | [4:8] | register |  |
| `op` | [8:16] (byte+1) | opcode-select | `0x4`=sample (explicit-LOD); `0x5`=bias / sample_compare; `0x6`=sample (implicit) / gather / lod_query; `0x7`=sample (register-LOD) |
| `coord_reg` | [24:32] (byte+3) | register |  |
| `tex_desc_lo` | [32:36] (byte+4) | modifier |  |
| `samp_slot` | [40:47] (byte+5) | immediate |  |
| `samp_last` | [47:48] | modifier |  |
| `tex_slot` | [48:56] (byte+6) | immediate |  |
| `coord_ctl` | [56:64] (byte+7) | modifier |  |

*M5 (G17g) TEXTURE sample-class op (filtered sample / gather / lod-query / sample_compare / bias). EMITTABLE byte map (HW-VALIDATED EXP-M5-17 by agxrender fragment->pixel splice-and-observe; every field below flipped an observed pixel): off0 byte0 low-nibble 0xf = tex op, HIGH-nibble = RESULT register. off1 (op): 0x04 explicit-LOD sample, 0x05 bias/sample_compare, 0x06 implicit-LOD sample|gather|calculate_clamped_lod, 0x07 register-LOD sample. off2 (class): 0x12 compute sample, 0x16 fragment implicit-derivative sample, 0x1a image read. off3 = COORDINATE REGISTER (16-bit-half index = reg32<<1; adjacent float2 coords -> +0x04). **HW-CONFIRMED: splicing off3 0x00->0x04 switched the sampled texel (RED->BLUE).** off4 = texture/sampler descriptor-state word (single-texture form 0x41; low-nibble = sampler-present/array/MSAA; co-varies with the binding-table bank for dense slot>=2 -- partially raw). off5 bits[6:0] = SAMPLER slot index, bit7 = last-in-group/scoreboard flag (**HW-CONFIRMED: byte-diff samplers 0/1/2/3 -> 0x00/0x01/0x02/0x03; splice off5 0x00->0x01 switched sampler (BLUE->RED)**). off6 = TEXTURE slot selector (**HW-CONFIRMED: slot0=0x60, slot1=0x68 (+0x08 per dense binding slot); splice off6 0x60->0x68 switched which bound texture was read (RED->GREEN); an unbound slot faults**; slot>=2 also bumps the off4 bank). off7 = coordinate-producer scoreboard token (splice-proven INERT to the sampled value). off8..11 = 01 18 01 00 operand tail (off9 = 0x18 implicit-LOD / 0x00 explicit-LOD|bias). off12 = LOD/BIAS immediate = round(level*0x40) (Q?.6: level 0/1/2 -> 0x00/0x40/0x80) (**HW-CONFIRMED: splice off12 0x00->0x40 selected mip level 0->1 (RED->BLUE)**). off13..21 = 00 00 00 00 80 00 00 00 00 gradient/pad words. FULL LENGTH per variant (own-MSL, HW): fragment sample (implicit/explicit LOD/bias) = 22 B; gather = 14 B; compute const-coord sample = 22 B. The DB tokenizes only the 6-byte EMITTABLE LEADER (op-class + coord + descriptor markers); the coord/LOD/gradient operand words fall through as raw words (rule 5), which is <= every observed op length so it never over-reads.*

### `m5_tex`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0xf, byte+2==0x16, bits[36:40]==0x4, byte+5==0x80  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `result_reg` | [4:8] | register |  |
| `op` | [8:16] (byte+1) | opcode-select | `0x4`=sample (explicit-LOD); `0x5`=bias / sample_compare; `0x6`=sample (implicit) / gather / lod_query; `0x7`=sample (register-LOD) |
| `coord_reg` | [24:32] (byte+3) | register |  |
| `tex_desc_lo` | [32:36] (byte+4) | modifier |  |
| `samp_slot` | [40:47] (byte+5) | immediate |  |
| `samp_last` | [47:48] | modifier |  |
| `tex_slot` | [48:56] (byte+6) | immediate |  |
| `coord_ctl` | [56:64] (byte+7) | modifier |  |

*M5 (G17g) FRAGMENT-stage TEXTURE sample (byte+2==0x16 = compute 0x12 | derivative-LOD bit 0x04). Same emittable byte map as the m5_tex compute form (see the 0x12 descriptor): off3=coord reg, off5[6:0]=sampler slot, off6=texture slot, off12=LOD/bias imm -- all HW-VALIDATED EXP-M5-17. This is the most common texture op in real fragment shaders and was previously absent from the M5 leader gate (byte+2==0x16 not recognized).*

### `m5_tex_read`

- **Length:** 8 bytes  ·  **Match:** bits[0:4]==0xf, byte+2==0x1a, bits[36:40]==0x4, byte+5==0x80  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `result_reg` | [4:8] | register |  |
| `op` | [8:16] (byte+1) | opcode-select | `0x4`=read (MSAA / by-sample); `0x6`=read (image load) |
| `coord_reg` | [24:32] (byte+3) | register |  |
| `tex_desc_lo` | [32:36] (byte+4) | modifier |  |
| `samp_last` | [47:48] | modifier |  |
| `tex_slot` | [48:56] (byte+6) | immediate |  |
| `coord_ctl` | [56:64] (byte+7) | modifier |  |

*M5 (G17g) TEXTURE unfiltered READ (image load by integer coordinate). Form `<rr>f <op> 1a <coord> 40 80 60 <sb>` (8 bytes total; DB tokenizes the 6-byte leader, 2 operand bytes fall through raw). byte0 low-nibble 0xf, HIGH-nibble = RESULT register. byte+1 0x06 = texture.read, 0x04 = MSAA/by-sample read. byte+2==0x1a = image-READ class (no sampler). **off3 = integer COORDINATE register (HW-CONFIRMED EXP-M5-17: same coord-register field position as the sample form). off6 = TEXTURE slot selector (0x60=slot0, +0x08 per slot; HW-CONFIRMED).** byte+4==0x40 = no-sampler descriptor marker; byte+5==0x80 last/scoreboard. own-MSL tex_read is 8 bytes total (`0f 06 1a 00 40 80 60 29`).*

### `m5_store_texresult`

- **Length:** 4 bytes  ·  **Match:** bits[0:5]==0x1, bits[12:16]==0x2, byte+2==0x10  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `ncomp_m1` | [5:7] | immediate |  |
| `src_class` | [8:12] (byte+1) | modifier |  |
| `st_fmt` | [24:32] (byte+3) | modifier |  |

*M5 (G17g) STORE of a TEXTURE / sampled value to the output buffer. 4-byte store `<n>1 <2X> 10 <00|20>`: byte0 = 0x01|0x21|0x41|0x61 (1/2/3/4-component, here the sampled floatN), byte+1 = texture-result SOURCE CLASS (hi-nibble 0x2, low-nibble 4/6/c/e), byte+2==0x10 store-enable, byte+3 = store format (0x00/0x20). Distinct from the ALU/load-result m5_store (byte+1 hi-nibble 0/2 low 2/6, byte+3 in 0x40..0xe0). Completes the texture path: m5_tex(_read) produces the sampled value; this store writes it out. Address comes from the preceding m5_addr_gen.*

### `m5_const_move`

- **Length:** 10 bytes  ·  **Match:** bits[0:4]==0x4, byte+1==0x80, bits[16:18]==0x3, bits[19:24]==0x0, byte+3==0x0a  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dst_hi` | [4:8] | register |  |
| `variant` | [16:24] (byte+2) | modifier |  |
| `src_desc` | [24:32] (byte+3) | modifier |  |
| `imm_sel` | [32:40] (byte+4) | modifier |  |

*M5 (G17g) CONSTANT-MATERIALISATION MOVE. 10-byte `<r>4 80 <03|07> 0a <27|20> <src> a<x> <x> 00 00`. Loads a compile-time float/int constant into a register; emitted in ANY stage wherever an immediate is needed -- vertex [[position]] constants, fragment/compute immediate operands, and the color components of a texture2d.write(float4(1,2,3,4),..) CONST store. NOTE: this is the op the EXP-M5-16 report MIS-LABELLED an `24 80 03` image-store form -- HW-DISPROVEN here: k_wrbuf (texture2d.write of a BUFFER-sourced color) stores a texture with ZERO `?4 80` ops, and this op appears in a trivial passthrough VERTEX shader that does no image I/O. Operand packing kept raw (rule 5).*

### `m5_image_store`

- **Length:** 18 bytes  ·  **Match:** bits[0:4]==0x5, byte+4==0x24, byte+6==0xa0, byte+7==0x02, byte+9==0x80  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `fmt_class` | [4:8] | modifier |  |
| `data_reg` | [8:16] (byte+1) | register |  |
| `store_fmt` | [16:24] (byte+2) | modifier |  |
| `dim` | [24:32] (byte+3) | modifier | `0x4`=2d/3d; `0xc`=2d_array |
| `tex_desc` | [40:48] (byte+5) | modifier |  |
| `tex_desc_hi` | [64:72] (byte+8) | modifier |  |

*M5 (G17g) COMPUTE IMAGE STORE (texture2d/3d/2d_array<..,access::write>.write). 18-byte op `<fmt>5 <data> <sf> <dim> 24 <desc> a0 02 <descHi> 80 <..> 8c <..> 20 <..> 00 01 00`. STABLE 18B across 2d/3d/2d_array (array sets byte+3=0x0c, byte+11=0x84, else 0x04/0x8c); coordinate dimensionality does NOT change the length. byte0 low-nibble 0x5, hi-nibble = data-format class (float 0x3, uint 0x2). THE TEXTURE IS NOT A RAW SLOT FIELD: it is a compiler-allocated descriptor (byte+5/+8) -- writing the same color to slots 0..3 (k_wr4same) yields byte+5 {0x60,0xa0,0xe0,0x20} while another kernel writing slots 0..2 (k_wrbuf_t2) yields {0x20,0x60,0xa0}; and an argument-buffer write (k_wrab0 vs k_wrab2) is BYTE-IDENTICAL across the index (index lives in the preamble descriptor-setup op, byte 0xa0+index). SUPERSEDES the A18 0xd7 texture-write on the M5 compute path. Data/descriptor packing kept raw (rule 5).*

### `m5_atomic_div`

- **Length:** 12 bytes  ·  **Match:** byte+0==0x0f, byte+1==0x00, byte+2==0x03, byte+7==0xc0  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `idx_mode` | [24:32] (byte+3) | enum | `0x2`=per-lane RMW; `0x4`=compare-exchange |
| `opsel_a` | [32:40] (byte+4) | modifier |  |
| `opsel_b` | [40:48] (byte+5) | modifier |  |
| `opsel_c` | [48:56] (byte+6) | opcode-select | `0x4`=add/and/fadd/cmpxchg-class; `0xc`=min/max/or/xor-class |
| `datapath` | [64:72] (byte+8) | enum | `0x80`=integer; `0x90`=float; `0x0`=exchange |
| `operand` | [72:88] (byte+9) | raw/unmapped |  |
| `opsel_d` | [88:96] (byte+11) | modifier |  |

*M5 (G17g) DIVERGENT-ADDRESS device ATOMIC (per-lane `atomic_fetch_<op>(&buf[gid], x)` / exchange / compare_exchange). 12-byte op that REUSES the low-nibble-f address-gen leader (`0f 00 03`) but carries a memory/atomic descriptor (byte+7==0xc0) and a datapath byte (byte+8: 0x80 integer, 0x90 float). The A18 per-lane atomic (0x67 byte+1 0x11/0x01) is GONE on M5; only the UNIFORM-address atomic migrated to m5_reduce (simd pre-combine + single RMW). The RMW OP is a DISTRIBUTED encoding over byte+4 (0x00/0x20), byte+5 (0x06/0x0e), byte+6 (0x04 add/and/fadd/cmpxchg-class, 0x0c min/max/or/xor-class), byte+11 (0x20/0x30) -- HW byte-diff table (each cell one op, 9 single-op own-MSL kernels): add=(b4 00,b5 06,b6 04,b11 20), and=(20,06,04,20), min=(20,06,0c,30), max=(00,06,0c,30), or=(00,0e,0c,20), xor=(20,0e,0c,30), fadd=(20,0e,04,20;b8 90 fp), cmpxchg=(00,0e,04,20; byte+3 0x04; b8 90). exchange is the 10-byte sibling m5_atomic_xchg (byte+6==0x18). Op-selector bits kept as typed raw/mod fields (rule 5, distributed encoding not collapsed into a fabricated single enum).*

### `m5_atomic_xchg`

- **Length:** 10 bytes  ·  **Match:** byte+0==0x0f, byte+1==0x00, byte+2==0x03, byte+6==0x18, byte+7==0xc0  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `idx_mode` | [24:32] (byte+3) | modifier |  |
| `opsel_a` | [32:40] (byte+4) | modifier |  |
| `opsel_b` | [40:48] (byte+5) | modifier |  |
| `tail` | [64:80] (byte+8) | raw/unmapped |  |

*M5 (G17g) DIVERGENT-ADDRESS device atomic EXCHANGE, 10-byte sibling of m5_atomic_div (byte+6==0x18 = exchange selector; no datapath/writeback tail, so 2 bytes shorter). Form `0f 00 03 02 01 06 18 c0 00 20`. Same leader family; the swap value is positional (the preceding load's result).*

### `m5_matrix_mac`

- **Length:** 14 bytes  ·  **Match:** byte+0==0x2f, byte+2==0x05, byte+5==0x20  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `dtype_lo` | [8:16] (byte+1) | enum | `0x0`=fp32 / fp16 inputs; `0x2`=bf16 inputs |
| `ab_operands` | [24:32] (byte+3) | raw/unmapped |  |
| `b4` | [32:40] (byte+4) | modifier |  |
| `datapath` | [48:56] (byte+6) | enum | `0xaf`=fp32 accumulate (fp32/bf16); `0xab`=fp16 accumulate |
| `struct78` | [56:72] (byte+7) | raw/unmapped |  |
| `accum` | [72:80] (byte+9) | enum | `0x6`=multiply (no accumulate); `0x8`=multiply-accumulate (load C) |
| `struct1012` | [80:104] (byte+10) | raw/unmapped |  |
| `c_operand` | [104:112] (byte+13) | raw/unmapped |  |

*M5 (G17g) simdgroup_matrix MULTIPLY[-ACCUMULATE] (cooperative-matrix 8x8 tile MAC), R = +/-(A*B) + C. 14-byte op `2f <dt> 05 <AB> <b4> 20 <af|ab> .. <accum> .. <C>`. On A18 both simdgroup_matrix MAC and MPP matmul2d lowered to 0xcf; on M5 the simdgroup MAC DIVERGES to this `2f ?? 05` op (0xcf survives ONLY for the tiled MPP matmul2d path, EXP-M5-09). RESOLVED OPERAND FIELDS (EXP-M5-20 splice-and-observe, A=2I@r2 B=3I@r4 C=5I@r6): byte+9 (accum) 0x06 multiply / 0x08 multiply-accumulate; byte+6 (datapath) 0xaf fp32|bf16-accum / 0xab fp16; byte+1 0x00 fp32|fp16 / 0x02 bf16 inputs. byte+3 (ab_operands) carries the A and B operand TILE REGISTERS: spliced redirects drove A -> r4/r6 (product 3*3, 5*3) and B -> r2/r6 (2*2, 2*5), HW-proven that this byte selects the two multiplicands; the exact A/B sub-bit packing is DISTRIBUTED (co-encoded with byte+8/+12) and kept RAW (rule 5) -- canonical value 0x9a = A=r2,B=r4. byte+13 (c_operand) FULLY DECODED: bits[4:3] = C accumulator tile register (0=none/r0 -> R=A*B, 1=r2, 2=r4, 3=r6; C_tile = 2x field), and bit6 (0x40) = NEGATE the A*B product (R = -(A*B)+C, a HW capability). Canonical byte+13=0x19 -> C=r6, no negate. dtype/dest tile placed by the feeding m5_tile_ldst ops (byte0-hi = tile register). EMITTABLE: place A/B/C via tile loads (r2/r4/r6), emit this canonical MAC, adjust accum + c_operand as needed.*

### `m5_falu2`

- **Length:** 12 bytes  ·  **Match:** byte+0==0x29, byte+1==0x00, byte+2==0x04, bits[52:56]==0xa  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `src_form` | [24:32] (byte+3) | enum | `0x1a`=immediate source; `0x3a`=register source |
| `b4` | [32:40] (byte+4) | modifier |  |
| `op` | [48:56] (byte+6) | opcode-select | `0xa0`=op-a0; `0xa8`=op-a8; `0xa3`=add; `0xac`=fadd |
| `opmarker` | [56:64] (byte+7) | modifier |  |
| `operand` | [64:96] (byte+8) | raw/unmapped |  |

*M5 (G17g) 12-byte compute-ALU op on the byte0==0x29 (float-datapath) leader -- the sibling of m5_alu (0x27) and m5_iadd (0x2f). Form `29 00 04 <1a|3a> <b4> 20 <ax> 02 ..`; byte+3 = immediate(0x1a)/register(0x3a) source, byte+6 = op-selector (hi-nibble 0xa, same position as m5_alu/m5_reduce). Emitted for split-memory index / fp add2-family arithmetic feeding a following m5_addr_gen. Length 12 (the inherited low-nibble-9 float rule mis-lengths it 10, after which a phantom icmpsel swallows the following m5_addr_gen). Operand word kept raw (rule 5); the byte+6 op-selector meaning on this float leader is not individually splice-proven (the 0xa0/0xa8 codes are byte-diff-observed, not confirmed to match the integer and/shift semantics).*

### `m5_tile_ldst`

- **Length:** 12 bytes  ·  **Match:** bits[0:4]==0xf, byte+2==0x07, byte+9==0xc0  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `tile` | [4:8] | immediate |  |
| `addr_gpr` | [8:16] (byte+1) | immediate |  |
| `b3` | [24:32] (byte+3) | modifier |  |
| `b45` | [32:48] (byte+4) | raw/unmapped |  |
| `dir` | [48:56] (byte+6) | opcode-select | `0xb8`=tile load (simdgroup_load); `0xa1`=tile store (simdgroup_store) |
| `b7` | [56:64] (byte+7) | modifier |  |
| `kind` | [64:72] (byte+8) | enum | `0x10`=load; `0x18`=store |
| `tail` | [80:96] (byte+10) | raw/unmapped |  |

*M5 (G17g) simdgroup_matrix TILE LOAD / STORE -- the cooperative-matrix fragment load/store that places A/B/C tiles for m5_matrix_mac. Form `<T>f <A> 07 <..> <b8|a1> <..> <10|18> c0 <tail>`. RESOLVED (EXP-M5-20 splice-and-observe): byte0 HIGH nibble = the TILE REGISTER (destination for a load, source for a store) -- HW-proven by moving a load's dest off its tile (R lost the matrix). byte+1 = the MEMORY ADDRESS SOURCE GPR, encoded as gpr<<1 (gpr index = byte+1>>1) -- HW-proven: redirecting a load's byte+1 0x04->0x08->0x0c made A read gpr2->gpr4->gpr6 (=the next buffer), 0x00 read gpr0 (zeros). byte+6 0xb8 load / 0xa1 store; byte+8 0x10 load / 0x18 store; byte+9 0xc0 fp32 (0x80 fp16, not gated here). EMITTABLE: to load buffer whose base is in GPR g into tile register T set byte0=(T<<4)|0x0f, byte+1=g<<1, byte+6=0xb8, byte+8=0x10; store swaps 0xb8->0xa1, 0x10->0x18. Base op 12 bytes.*

### `m5_tile_ldst_ext`

- **Length:** 16 bytes  ·  **Match:** bits[0:4]==0xf, byte+2==0x07, byte+9==0xc0  ·  **Provenance:** mixed

| Field | Bits | Type | Enum / values |
|---|---|---|---|
| `tile` | [4:8] | immediate |  |
| `addr_gpr` | [8:16] (byte+1) | immediate |  |
| `b3` | [24:32] (byte+3) | modifier |  |
| `b45` | [32:48] (byte+4) | raw/unmapped |  |
| `dir` | [48:56] (byte+6) | opcode-select | `0xb8`=tile load (simdgroup_load); `0xa0`=tile load (inline-base); `0xa1`=tile store (simdgroup_store) |
| `b7` | [56:64] (byte+7) | modifier |  |
| `kind` | [64:72] (byte+8) | enum | `0x10`=load; `0x18`=store; `0x0`=inline-base load |
| `tail` | [80:128] (byte+10) | raw/unmapped |  |

*M5 (G17g) simdgroup_matrix TILE LOAD/STORE, 16-byte INLINE-BASE form. Identical to m5_tile_ldst plus a trailing 4-byte inline immediate (`80 00 00 00`). Selected when byte+10 bit 0x40 is SET (12B form has it clear); the compiler emits it for (at least) the last tile load of a group. The inline immediate is HW-INERT in EXP-M5-20 splice tests (splicing byte+12 80->00/40/c0/84 left the loaded matrix unchanged) -- the actual data address is still byte+1's GPR. tile register (byte0-hi) and address GPR (byte+1) fields identical to m5_tile_ldst. Kept raw where structural (rule 5).*

## Length rule (byte 0)

Parcels are 2 bytes (all lengths even). Length is a function of byte 0 plus a per-group length bit/signature. The authoritative rule is `instr_length()` in `tools/agx-isa-m5/isadb.py`; this table summarizes it:

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
| `0x60` | 4  [SPILL/FRAME-SETUP MARKER (spill_frame_marker): `60 00 00 00` right after the entry get_sr in high-register-pressure / SPILLING kernels. Runtime-inert for the computation (byte0/+1/+2 splices no-op), byte+3 live (0xff faults). Previously halted tokenization (no length rule). RT-1a-FIX HW: length 4; exact role a follow-up] |
| `device_load/store +5 index_reg (RT-1a-FIX)` | +5 is the INDEX GPR that supplies a[idx] (NOT `count`; sweeping +5 selects which GPR feeds the index); +6 is INERT; +1 = address space; the additive IMMEDIATE index-offset lives at +9 bit7 (+1) / +10 (+2/unit) / +11 low (+512/unit). Vector width/count is at +8 (dst_width) / +12 (elem_size). RT-1a-FIX HW-validated. |
| `iadd2 add/sub polarity (RT-1a-FIX)` | byte0 bit7 = ADD(1,0x9f) / SUBTRACT(0,0x1f) select. The DB previously had this INVERTED (labelled every add srcA_neg=1 and gave 0x1f d=srcA+srcB although 0x1f subtracts). Splice 0x9f->0x1f turns 10+20 into 10-20=-10. HW-validated. |
| `0x07 (byte+1==0x00, byte+2==0x54)` | 8  [LINK-REGISTER SAVE/RESTORE around a nested call in a non-leaf frame (link_save_restore); the byte+1 in {0x04,0x14} forms are the 6-byte threadgroup_barrier / pixel_order. EXP-0038] |
| `0x18 (M5 DISAMBIGUATED)` | byte0 0x18 has TWO meanings on M5 (G17g), disambiguated by signature (EXP-M5-07/11): (a) if byte+2==0x10 AND byte+1 in {0x02,0x0a,0x22,0x2a} it is the M5 device LOAD m5_load -- 10 bytes (or 4 if byte+3==0x40, the compact non-terminal m5_load_compact); byte0 0x18/0x38/0x58/0x78 = 1/2/3/4-component. (b) OTHERWISE (byte+1==0x05, byte+2 hi-nibble 1) it is the inherited A18 HALF-LANE PACK half_pack -- 4 bytes (assemble a half2's two fp16 lanes; byte0 hi nibble = dst reg). The m5_load rule is placed FIRST so the 10-byte load always wins its signature; the STALE flat `0x18 -> 4 half_pack` appendix line is hereby corrected. `18 00` (byte+1==0x00) = 2-byte compact half move. |
| `M5 SPLIT MEMORY MODEL (EXP-M5-07/11)` | The A18 monolithic 14-byte device_load(0x67)/device_store(0xe7) is SUPPLEMENTED on M5 by a SPLIT model: a 4-byte m5_addr_gen (low-nibble-f, byte+2==0x03; base = buffer[byte+1>>2], byte+3 idx_mode) + a LOAD (0x18/38/58/78, byte+2==0x10, 10B/4B) + a STORE (0x01/21/41/61, 4B/6B). BOTH models COEXIST on M5 (census EXP-M5-11: m5_addr_gen 1636 own / 2891 tp, m5_load 424, m5_store 520 DOMINANT; device_load 0x67 still 159 own / 54 tp, device_store 0xe7 21/22 -- retained for specific cases). The A18 device-ATOMIC forms (0x67 byte+1 0x11/0x01) are GONE on M5 (0 occurrences): uniform-address atomics migrated to m5_reduce. Index model: a[gid] = addr_gen idx_mode 0x02 + load amode 0x22; a[computed]/a[idx[gid]] = addr_gen idx_mode 0x00 + load amode 0x02 with the index GPR at load byte+5 (splice-proven); a[i+k] folds +k into a preceding m5_alu/m5_iadd add (NO immediate-offset field in addr_gen or load). Store/load DATA register is positional (byte-diff proven). |
| `M5 UNIFIED COMPUTE/REDUCE/ATOMIC op-selector (EXP-M5-09/11)` | On M5 the subgroup reduce/scan, quad reduce, device-atomic pre-combine, shuffle, and a broad integer/logic/min-max compute ALU all moved into the low-nibble-f `0x2f`/`0x27` op space with the OPERATION in an op-selector at byte+6 (hi-nibble 0xa): a0 and, a1 or, a2 xor, a3 add, a6 min, a7 max, ac float-add (byte+6 HW-splice-validated). Forms: m5_reduce `2f 00 <scope> <dp> 27 80 <op> 02 <b8> <mode>` (10B; scope byte+2 0x04 simd/0x00 quad, mode byte+9 0x02 reduce/0x00 scan; names the device-atomic-on-uniform pre-combine too); m5_shuffle `2f 00 21 1a 20 00 <op> 02 <lane> 00` (10B); m5_iadd `2f 00 04 <3a\|1a> 21 00 a3 02 28 ..` (12B split-memory index add); m5_alu `27 <..> <op=aX@+6> ..` (12B, the general compute datapath). These REPLACE the A18 0xbf/0x3f/0xb7 reduce, 0x47/0xc7 shuffle and the 0x67-atomic forms (which are ABSENT on M5). |
| `M5 TEXTURE (CHARACTERIZED, length OPEN -- EXP-M5-09/11)` | Leader byte0 in {0x0f,0x1f} + op-class byte+2 (0x12 sample-class / 0x1a image-read) + sampler marker `4X 80` at byte+4/+5; byte+1 = 0x04 sample / 0x05 sample_compare / 0x06 gather\|lodq\|read. Per-op LENGTHS byte-diffed from 6 isolated own-MSL kernels (read 8, scmp 8, lodq 10, gather 14, sample 22) DO NOT generalise (they over-read the following coordinate ops on real corpus kernels, net-regressing the census), so texture is left OUT of the length rule -- integrating it needs an agxrender coordinate splice. OPEN. |
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

*Rendered from `tools/agx-isa-m5/db.json` — 194 descriptors. The machine-readable source of truth is `db.json` / `isadb.py`; this document is its human-readable projection.*
