# EXP-M5-20 — M5 simdgroup_matrix cooperative-matrix MAC operands + tile 12/16 length rule

**Device:** Apple M5 / Apple10 / G17g / T8142. Splice-and-observe on OUR OWN MSL; every field is a **numeric
matrix output read back from real HW** (one simdgroup, A=2·I B=3·I C=5·I → R=A·B+C on the diagonal). No Apple
binary inspected. 0 hangs/reboots across ~1900 splice dispatches.

## Verdict: coop-matrix is EMITTABLE — A/B/C tiles placeable, MAC operands located.
## Tile LOAD/STORE (placement) — FULLY PROVEN
`<T>f <A> 07 .. <b8|a1> .. <10|18> c0`: tile register = **byte0 hi-nibble** (moving LOAD_C off r6 dropped C, R→6);
memory address GPR = **byte+1** (=gpr<<1; LOAD_A byte+1 04→08→0c read gpr2→4→6 = next buffer, R 11→14→20; 00→R=5);
load/store dir = byte+6 (0xb8/0xa1) + byte+8 (0x10/0x18); datapath byte+9 (0xc0 fp32 / 0x80 fp16).
**Emit:** load GPR *g*'s buffer into tile *T* → `byte0=(T<<4)|0x0f, byte+1=g<<1, byte+6=0xb8, byte+8=0x10, byte+9=0xc0`.

## Tile 12-vs-16 length — DETERMINED: `16 if (byte+10 & 0x40) else 12`
12B: byte+10∈{0x00 fp32, 0x80 fp16}; 16B: {0x41,0xc1}+trailing inline `80 00 00 00` (HW-INERT — splicing it left
the matrix unchanged; real data addr is byte+1). Consistent 6/6 own tile ops. Replaces the conservative always-12 rule.

## MAC operands — `2f <dt> 05 <AB> <b4> 20 <af|ab> .. <accum> .. <C>` (14B)
A&B regs = **byte+3** (byte proven: A→r4/r6 gave R=14/20, B→r2/r6 gave 9/15, both→r6 gave 30; canonical 0x9a=A=r2,B=r4;
A/B sub-bit split raw, rule 5). C reg = **byte+13[4:3]** (00 none R=6/01 r2 8/10 r4 9/11 r6 11; C_tile=2×field).
**byte+13 bit6 = negate A·B product** (latent capability → hypotheses.md). accumulate byte+9; datapath byte+6
(0xaf fp32/bf16, 0xab fp16); input dtype byte+1 (0x00 fp32/fp16, 0x02 bf16 — fixes the old byte+1==0x00 gate that MISSED bf16).

## DB patch (validated non-regressing)
m5_tile_ldst length `16 if byte+10&0x40 else 12`; m5_matrix_mac drop byte+1==0x00 gate (catches bf16 MAC 2f 02 05);
typed operand fields on both + new m5_tile_ldst_ext (len-16). Round-trip ALL PASS; all 5 simdgroup_matrix streams
tokenize 0-leftover/0-unknown with correct 12/16 lengths + tile/C regs; census FLAT (own 93.44/97.41, tp 95.51/98.41);
DB 189→192 (via 191 after the call patch). Concrete gain: NEW DB names the bf16 MAC + lengths 16B tiles correctly.

## Raw (rule 5)
Exact A/B sub-bit packing within MAC byte+3; the 16B inline immediate (HW-inert); MAC structural mode bytes.

## Clean-room attestation
Every byte is our own on-device-compiled MSL; every field a numeric matrix delta observed on real HW with our own
agxrun/agxparse + our own fork. No Apple binary introspected; no compiler sequence lifted; unresolved sub-fields raw.
