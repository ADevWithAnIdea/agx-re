# EXP-M5-11 — M5 ISA-semantics integration (OBJ-1 BLOCKER-1/2/3 + MAJOR-4/5)

**Device:** Apple M5 / G17g / T8142. Integrate the EXP-M5-09 M5 ISA findings into the emittable DB, closing
the REVIEW-M5-OBJ1-01 blockers. Worked on a copy; validated non-regressing on both census corpora before
delivery. Zero hangs / zero reboots. No Apple binary disassembled.

## Validation gate PASSED (independently re-confirmed on device)
| corpus | named % | UNDEC % | byte-cov % |
|---|---|---|---|
| own | 85.14 → **93.42** (+8.28) | 3.39 → **2.60** | **97.40** |
| tp  | 91.19 → **95.48** (+4.29) | 1.83 → **1.61** | **98.39** |

named UP + desync DOWN on BOTH corpora, ZERO new desync-regressions, ZERO hangs, round-trip ALL PASS,
`db.json` = **180 descriptors** (9 M5-specific: addr_gen/load/load_compact/store/store_ext/alu/iadd/reduce/shuffle).

## Closed
**BLOCKER-1 (core):** integrated 4 descriptors + 1 length rule:
- **m5_reduce** (10B) — subgroup/quad reduce+scan AND device-atomic-on-uniform pre-combine (byte-identical:
  `a_iadd`==`s_sum`). op byte+6 (a0/a1/a2/a3/a6/a7/ac), scope byte+2, mode byte+9. Was mis-named `fspecial`.
  A18 0x67-atomic forms **GONE** on M5.
- **m5_shuffle** (10B) — `2f 00 21 …`, op byte+6 (a8/a0/a1).
- **m5_alu** (12B) — the M5 general compute ALU (byte0=0x27, op-selector byte+6 hi-nibble 0xa). Largest
  lengthed-but-unnamed bucket (~3350 own / ~970 tp) → the +8.28% named win. Descriptor-only (no length change →
  provably cannot introduce desync). Operand packing kept raw (rule 5).
- **m5_iadd** (12B) — split-memory index add `2f 00 04 <3a|1a> 21 00 a3 …`; length rule (gated byte+4==0x21 &
  byte+6==0xa3) fixes the `fspecial(10)` desync (the own UNDEC drop).

**BLOCKER-2 (HW splice + byte-diff):** m5_load **byte+5 = index register (SPLICE-PROVEN** — 0x20→0x00 forces
every lane to read a[0]); immediate offset `a[i+k]` has **no field — folded into a preceding m5_alu add**
(byte-diff, a first-class negative vs A18); store/load **data register is IMPLICIT/positional** (byte-diff:
st_sum and st_mul7 emit byte-identical stores; byte+1 = source *class*, not a reg number).

**BLOCKER-3:** census answered — **0x67/0xe7 still occur on M5** (device_load 159/54, device_store 21/22)
alongside the dominant split model (m5_addr_gen 1636/2891, m5_load 424, m5_store 520); A18 atomics migrated to
m5_reduce. Fixed the stale `0x18` length appendix (disambiguates m5_load 10B vs half_pack 4B by signature) +
added M5 split-memory / unified-op / texture appendix blocks; `isa` string names M5.

## Opens (honest)
- **MAJOR-4 (call ABI) NEGATIVE, path identified:** whole-`__text` extraction of a visible_function_table caller
  yields a 4-byte stub — the call resolves at *pipeline-link* time, not in the standalone archive. Needs a shdump
  extension that builds a pipeline with `linkedFunctions` and dumps that variant.
- **MAJOR-5 (RT AS-load) OPEN:** `rt_intersect` confirmed present (survives A18); the AS-load migrated off 0xdf
  into the memory family, but isolating the AS-load opcode needs an AS-bound splice testbed (real BVH, known node).
- Matrix MAC/tile length+operands; texture lengths (a regressing length variant was **reverted** per the gate,
  −42 tp/−50 own — recorded open, leader/op-class documented); m5_alu operand bit-packing (raw); next NOMATCH
  families (byte0==0x01 len-10 op@+8, byte0==0x17 len-10) identified as more unified-op, unnamed to avoid speculation.

## Deliverables
`isadb.py.EXP-M5-11.patch` (applies -p0, roundtrip ALL PASS, 180 desc), `kernels/*.metal` + `hex_extractions.txt`
(BLOCKER-2 provocations + byte-diff evidence; vft* = MAJOR-4 negative), census/analysis harnesses.

## Clean-room attestation
Every byte inspected/spliced is our own on-device-compiled MSL or bytes our own agxrun read from our own buffers.
No Apple binary introspected; no compiler *sequence* lifted (only per-op encoding facts + op-selector positions);
operand words kept raw where unproven (rule 5). All integration validated non-regressing on both corpora; the one
regressing variant was reverted and recorded open.
