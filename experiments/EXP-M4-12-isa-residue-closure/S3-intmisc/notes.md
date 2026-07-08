# EXP-M4-12 S3-intmisc — ISA residue closure (int/uint/half/64-bit/convert/mem)

CLEAN-ROOM: every byte analysed is the compiled form of MSL **we wrote** (OWN-SHADER),
extracted with our own `shdump`/`agxparse` and tokenised with our own `isadb`. No Apple
binary was disassembled. Method: isolate each operator into its own `k_iso`, compile,
extract, tokenise, and read the offending op's TRUE length from the anchored gap (the
byte count between two known-length ops that bracket it). Lengths verified by re-tokenising
the real corpus kernels with the proposed `instr_length` overrides (`work/regress.py`):
**all 5 target kernels close to 0 undecoded bytes, 0 regressions across the whole corpus.**

`iso_uint_full.metal` (the exact k_uint_arith expression) and `iso_cvt_pack_full.metal`
compile **byte-identical** to the corpus kernels — the isolation is faithful.

## Regression result (work/regress.py, all corpus hex)
```
k_cvt_pack    6->0   k_half_arith 10->0   k_int64 10->0   k_mem 4->0   k_uint_arith 16->0
BONUS: k_tex_atomic 14->12   r_blend_f 20->4      REGRESSIONS: 0
```

## Per-residue findings (see report for paste-ready predicates)

1. k_int64 @0xac  — cascade from op @0xa2 `92 8f 25 8b 85 19 07 00`. low-nibble-2 b2==0x25
   is length-POLYMORPHIC on srcC: register srcC (byte+4 bit1 clear, e.g. 0x85) = **8B**;
   immediate 0/1-select srcC (byte+4==0x22, `22 81 .. 20 80` tail) = 10B. DB returned 10 for
   both. dst=byte0 hi-nibble (r9).

2. k_uint_arith @0x118 — cascade: fence @0x114 `87 00 3a 80` is a **2-byte** bare fence
   (byte+2==0x3a is the NEXT op's byte0, not a scope operand); real ops are
   `3a 80 25 83 22 81` (icmp_pred low-nibble-a, 6B, existing rule) + `85 00 20 80` (**psel
   high-predicate-reg variant**, 0x05|0x80, 4B). Parallels k_int64@0x66 icmp_pred(b2=0x25)+psel.

3. k_uint_arith @0x142 — icmpsel @0x134 over-read: the div/mod-correction REGISTER-select
   `12 06 2d 80 26 80 07 02 22 81` is **10B**, not 14B. Genuine 14B icmpsel-to-const has
   b2==0x1d, b3==0x05 (`iso_int_cmp_bool`/`iso_int_gt`: `12 03 1d 05 22 81 .. 13 00 00 01`).
   Discriminator: b2==0x2d AND b3==0x80 (register operand) => 10.

4. k_uint_arith @0x19a — op @0x190 `12 0d 3f 11 81 0c 05 00` is **8B** (b0==0x12, op-select
   0x3f), NOT fminmax(6). Proof: the trailing `9f 01 54 00 02 00 08 a8 17 05` is a textbook
   iadd2 (final accumulate before store, byte+4==0x02), so 0x190 must consume the `05 00`.
   (fmin/fmax do NOT use 0x12/0x3f — `iso_fmin` => byte0 0x22/0x02, b2 0x26/0x3e — no collision.)
   NB semantic ambiguity: equivalently a 6B compare + 2B compact psel `05 00`; identical
   boundaries, single-branch 8B chosen. Not HW-spliced.

5. k_half_arith @0x2c — genuine single **10B** op `20 05 39 04 10 02 1e 03 80 04`
   (byte0 low-nibble 0, dst=hi-nibble r2, op-select byte+2==0x39). The half `(x+y)*(x-y)+x*y`
   combine op. Cleanly bracketed by half2 ALU(6B)@0x26 and device_store@0x36.
   Reproduced exactly by `iso_half_addmul`.

6. k_cvt_pack @0x34 — unpack_convert @0x2a/@0x32 (byte0==0x17, byte+1 low-nibble==0x04) is
   **8B**, not 10B. Two back-to-back 8B unpacks (unorm+snorm); DB's 0x17->10 (simd_ballot)
   swallowed the 2nd unpack's head. simd_ballot has byte+1 low-nibble==0x07 (stays 10) — the
   DB already discriminates these in DECODE; only the LENGTH rule conflated them.
   `iso_unpack_unorm`: lone unpack must be 8B or it eats the store.

7. k_mem @0xe — `5b 11 17 ff 10 02 00 00 00 00` is one **10B** low-nibble-b int-logic op
   (the `&255` array-index mask; byte+3==0xff = mask imm; `10 02 00 00 00 00` is its operand
   tail, NOT a half_alu — no halfs in this kernel). Sibling of the `0b 01 1f ff ..` ilogic
   (`iso_mem_mask`, decoded as 10B ilogic). New op-select: byte+2==0x17.

## Provenance
EXP-M4-12 OWN-SHADER isolated compile (M4). Lengths determined by anchored-gap / clean
re-tokenisation of our own compiled shaders (same tier as the DB's byte-diff entries), NOT
hardware-spliced. Semantics labelled only where the anchored structure is unambiguous;
operand bit-fields left undecoded where not cleanly separable.
