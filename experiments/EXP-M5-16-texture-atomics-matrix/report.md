# EXP-M5-16 — close the OBJ-1 texture BLOCKER + divergent-atomics + matrix-MAC (+ M-8 + OBJ-3 polish)

**Device:** Apple M5 / G17g / T8142. Integrate the texture sample family, divergent-address atomics, and the
`simdgroup_matrix` MAC into the emittable DB — census-validated, non-regressing. Zero hangs/reboots. No Apple
binary introspected; operands raw where unproven (rule 5).

## Validation gate PASSED (device-confirmed)
| corpus | named % | UNDEC % | byte-cov % |
|---|---|---|---|
| own | 93.42 → **93.43** | 2.60 → **2.59** | **97.41** |
| tp  | 95.48 → **95.51** | 1.61 → **1.59** | **98.41** |

named UP both, UNDEC DOWN both, ZERO new desync, round-trip ALL PASS, **DB 180→188 descriptors**.

## Texture BLOCKER — CLOSED
Root cause of the prior (reverted) attempt: texture-op length is **genuinely variable** — the same `0f 06 12`
gather is 14B with inline const coords, 22B with register coords — not derivable from the leader, and
`byte+2∈{0x12,0x1a}` also fires on operand-word landings (→ over-read → regress). **Fix:** gate tightly on the
sampler-descriptor marker **byte+4 hi-nibble 0x4 + byte+5==0x80** (~24 bits, disjoint from landings), length =
the **6-byte emittable LEADER** (`m5_tex` sample-class / `m5_tex_read`), letting coord/LOD operands fall through
as raw words (rule 5). 6 ≤ every observed length → never over-reads; for gather/read it's already the stream's
length → zero tail shift. Added `m5_store_texresult` (`61 2e 10 00`, sampled-value store, previously desynced).
**tex_write (M-1):** `0xd7` image-write **survives on M5** (19 tp, correctly lengthed) — retained; the extra M5
`24 80 03` image-store form documented open.

## M-2 divergent-address atomics — CLOSED
A18 per-lane `0x67` GONE; M5 uses `0f 00 03 … c0 …` (reuses addr-gen leader + memory descriptor byte+7==0xc0 +
datapath byte+8): **`m5_atomic_div`** (12B) / **`m5_atomic_xchg`** (10B). Op-selector = distributed-nibble
(byte-diff of 9 single-op kernels). **Splice-CONFIRMED** on da_add (b=0, x=10..17 → b=x): leader `0f`→`00`
zeros output (load-bearing); byte+7 `c0`→`00` zeros output (the gate discriminant is HW-proven); byte+4
`00`→`20` gives AND (op-selector load-bearing); byte+8 inert for int-add (honest negative).

## M-3 matrix MAC — CLOSED
**`m5_matrix_mac`** (`2f 00 05`, 14B, byte+9 accumulate flag) + **`m5_tile_ldst`** (`?f ..07..`) — control-ladder
byte-diff + EXP-M5-09 splice. 12/16B tile variant handled conservatively. Operand packing raw (rule 5).

## M-8 + OBJ-3 polish
Superseded-on-M5 caveats appended to all 8 retained A18 descriptors (tex_sample, tex_write, matrix_mac,
atomic_rmw/mem, rt_as_load, rt_ray_mem, call/call_indirect). OBJ-3 folds: shuffle enum +0xa9; reduce fp enum
+0xae/0xaf; byte0==0x29 12B **`m5_falu2`** (fixes a phantom-icmpsel `m5_addr_gen` swallow, non-regressing).

## Remaining opens (honest)
Texture operand bit-packing (raw — needs agxrender coord splice); M5 `24 80 03` image-store length; matrix
operand packing + tile 12-vs-16 determinant (raw); atomic op-selector not per-bit exhaustively spliced; RT
AS-load / call-ABI unchanged (documented-open MAJOR-4/5, with fallbacks in porting-guide §8).

## Clean-room attestation
Every byte inspected/spliced is our own on-device-compiled MSL or bytes our own agxrun read from our own buffers,
decoded with our own fork. No Apple binary disassembled; no compiler sequence lifted. Validated non-regressing on
both corpora before delivery.
