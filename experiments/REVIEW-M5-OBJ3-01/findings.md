# REVIEW-M5-OBJ3-01 — Adversarial validation of the M5 ISA findings (not-hallucinated)

Adversarial reviewer, tried to REFUTE the documented M5 findings against the full corpus + fresh HW
re-derivation. **VERDICT: PASS — findings are HW-real, not hallucinated.**

- **Claims verified: 7/7 load-bearing. Refuted: 0. Hallucinations: 0.**
- Census REPRODUCED EXACTLY (own 842 uniq: 93.42% named / 97.40% byte-cov; tp 708 uniq: 95.48% / 98.39%),
  round-trip ALL PASS, 180 descriptors. Dedup is legitimate (tp has 2386 byte-identical Dawn/Tint dups), not truncation.

## Claims re-derived from fresh HW bytes — all VERIFIED
- **C1 memory SPLIT** — `ld_st` decodes addr_gen→load→addr_gen→store; float4 → load byte0=0x78 / store byte0=0x61; base_slot=slot×4 re-derived.
- **C2 matrix SPLITS / ZERO 0xcf in simdgroup_matrix** (marquee) — "cf" appears 0× in all simdgroup MAC kernels; MAC `?f 0? 05` present in multiply, absent in load/store control; MPP matmul2d → real `0xcf`. No new neural opcode.
- **C3 m5_load byte+5 = index reg; store data-reg implicit** — DB field at bit40 splice-provenance; store has no data-reg field.
- **C4 reduce/shuffle/alu selector byte+6** — sg_and→a0, sg_xor→a2, sg_sum(f32)→ac; shuffle `2f 00 21`; device atomic-fadd byte-identical to sg_sum (m5_reduce unification confirmed).
- **C5 0x67/0xe7 coexist** — device_load 159/54, device_store 21/22 (exact BLOCKER-3 figures) alongside split model.
- **C6 m5_alu win** — 3353 own / 976 tp (≈ +8.28% named).
- **C7 no dedicated neural leader** — only unnamed buckets are the documented 0x17/0x01 unified-op families; no hidden mis-named op.

## Hallucination check — CLEAN
m5_alu/m5_iadd keep exactly one `raw` operand field (rule 5), not fabricated. Documented OPENS genuinely absent:
no callfn/vft descriptor (call ABI open), no tensor/matmul/neural/bvh descriptor (matrix-MAC/RT AS-load open,
decodes as fspecial/A18-0xdf, honestly unnamed not faked). Undecoded tail = orphaned operand words + documented
open families — honest choice is UNNAMED, never WRONG-named.

## Minor (none refute a claim)
1. On-device `db.json` is a stale 175-desc export; the live `isadb.py` + committed repo `db.json` are the current
   180-desc/"Apple M5" version (census/round-trip use isadb.py). Device-regen hygiene nit only.
2. `add2` fp-add `29 00 04 1a` lengthed 10B where 12B needed (sibling of the documented 0x2f..3a 12B open;
   round-trip still passes) — byte0=0x29, possibly not explicitly enumerated.
3. `m5_shuffle` shuffle_xor byte+6=`0xa9` (doc lists `a1`) — enum incomplete.
4. float `simd_max` byte+6=`0xaf` (= int `a7`|0x08) — fp-variant of the OP-selector, supports the model.

## Clean-room attestation
Every byte from own on-device-compiled MSL or bytes our own tools read from our own buffers, decoded with our
own fork. No Apple binary disassembled/introspected. Hard-timed; zero hangs/reboots.

**OBJ-3 gate: PASS.**
