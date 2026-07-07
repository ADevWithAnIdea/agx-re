# RT-10 RESULTS — 2nd-pass red-team verification of the corrected ISA decode

**Bottom line:** the JUST-CORRECTED decode passes an independent 2nd pass. Ballot / shuffle /
`0x0f` exec-mask / matrix `0xcf` all decode correctly on fresh, different kernels and splice as
documented. The RT AS-select ⏳-inferred marking is **honest**. No new whole undecoded instruction
family. One nuance (matrix half-datapath) and one refinement (RT byte+4 instance value) recorded.
DB verified at **82 descriptors**, `roundtrip_test.py` = ALL PASS (DB unmodified).

Verdicts: **CONFIRMED** = corrected decode is right. All five families → CONFIRMED.

---

## Part 1 — Ballot / shuffle / unpack — **CONFIRMED** (no collision, no mis-decode)

Fresh kernels (different predicates/values than RT-ISA-FIX): `simd_ballot(lane>=16)`,
`simd_active_threads_mask`, `simd_broadcast(v,7)`, `simd_shuffle_xor(v,1)`, `_up(v,2)`, `_down(v,4)`,
dynamic `simd_shuffle`, `unpack_snorm2x16`, and one **combined** shader emitting all of them.

Tokenization (all distinct, byte+1/byte0 keys as documented):
| op | bytes (first 6) | decode | key |
|---|---|---|---|
| `simd_ballot(pred)` | `17 17 54 …` | **simd_ballot** | byte+1 low-nib **7**, hi-nib **1** |
| `simd_active_threads_mask` | `17 07 54 …` | simd_ballot (active form) | byte+1 = **0x07** |
| `unpack_snorm2x16` | `17 04 56 …` | **unpack_convert** | byte+1 low-nib **4** |
| `simd_broadcast` | `47 04 54 …` | **simd_shuffle** | byte0 0x47, **byte+2 = 0x54** |
| `simd_shuffle_xor` | `c7 04 54 …` | simd_shuffle | byte0 0xc7, **byte+2 = 0x54** |
| `simd_shuffle_up/down` | `47/c7 05 54 …` | simd_shuffle | byte+1=0x05, byte+2=0x54 |

**All three `0x17` forms coexist in the one combined shader with 0 collision** (`agxisa disasm`
of `1717…`→simd_ballot, `1704…`→unpack_convert, `4704…`/`c704…`→simd_shuffle).

HW splice confirmations (grid=tg=32, one simdgroup):
- ballot baseline = `0xFFFF0000` (lane>=16); active baseline = `0xFFFFFFFF` → the two forms are
  distinguishable and correctly named.
- **ballot byte+1 low-nibble `0x17→0x14` (family 7→4) ZEROES the ballot** (`-65536`→`0`) — the
  low-nibble is the load-bearing ballot/unpack separator (proves no collision).
- **broadcast lane** byte+6 `0x0e→0x06` (lane 7→lane 3): all lanes `22→10` (`v=lane*3+1`). ✓
- **shuffle_xor mask** byte+6 `0x02→0x06` (mask 1→3): pattern `i^1`→`i^3` exactly. ✓
- unpack functional: `unpack_snorm2x16(0x7FFF3FFF)` → `0xBF000000, 0x3F800000` (snorm floats, **not**
  a bitmask) — unmistakably an unpack.

**Nuance (not a discrepancy):** the byte+1 **high**-nibble (ballot-pred `0x17` vs active `0x07`) is a
compiler-emission distinction whose operand bytes co-vary; a *bare* byte+1 `0x17→0x07` splice is
**inert** (the predicate operand persists) — so it is not a clean splice-convertible field. The DB
naming (family = byte+1 low-nibble) is nonetheless correct and load-bearing.

## Part 2 — `0x0f` execution-mask family — **CONFIRMED** (if_push = 4B)

Fresh divergent CF: **switch**, nested loops w/ **multiple breaks**, **short-circuit &&/||**,
**ternary chains**, **do-while** (all new vs RT-ISA-FIX if/else/for/while).

- **`p2_switch` tokenizes 100%** with the full `0x0f` chain per case:
  `0f 05 54 01` = **if_push (len 4 — confirmed 4B, not 8)** · `0f 04 04 19` = mask_op (4) ·
  `0f 01 54 …` = jump_cond (10) · `0f 06 04 02 00 00` = pop_reconverge (6). An 8-byte if_push would
  desync the switch; the clean 100% tokenization *is* the 4B proof.
- `p2_multibreak`: all `0x0f` ops clean incl. **`0f 00 54 <off> …` back-edge jumps** (offsets −60, −152).
- `p2_ternary` emits **no `0x0f`** (select cascade — matches "simple divergence = predication").
- `p2_dowhile` was **optimized to closed-form** (Σ odd = n²) — no loop emitted (compiler opt, not a gap).

HW splices on `p2_switch` (in=tid → lanes diverge across cases; baseline `[7,3,-9,86,11,15,-5,82]` ✓):
- **jump_cond `0f 01→0f 00`** (cond→uncond): output collapses to `[7,1,2,3,11,5,6,7]` — divergence
  guard broken. ✓ (0f01 = conditional, 0f00 = unconditional.)
- **pop_reconverge `0f 06→0x00`**: `CMDBUF_ERROR` (GPU page fault) — reconverge is load-bearing. ✓
- **back-edge `0f 00` offset** (`p2_multibreak`, byte 0xc4→0x00): result `65→0` — the taken edge. ✓

**No `0x0f` form fails.** The lone `0f 02` seen in `p2_shortcircuit` is a **resync artifact** (that
kernel desyncs early on the known `0x0b` boolean-LUT / compare operand residue, then +2-steps onto a
mid-instruction `0f` byte). The cleanly-tokenized kernels contain no `0f 02`.

## Part 3 — Matrix `0xcf` operand map — **CONFIRMED** (different kernel + values)

Fresh fp32 matmul `D=A·B+C` with `A[i][j]=i+1, B[i][j]=j+1, C=500` (distinct from RT-5's `i`,`j`,1000),
`0xcf` op = `cf 02 56 02 00 04 08 09 d4 43 24 01` @ +0xba. All operand splices (via `persistrun`):

| splice | expected | observed | field |
|---|---|---|---|
| baseline `A·B+C` | 508,516,524; D77=1012 | **508,516,524; 1012** | 8(i+1)(j+1)+500 |
| **+5** `0x04→0x08` (A→B) | B·B: col-varying | **536,572,608; row-indep** | **byte+5 = A (left)** |
| **+6** `0x08→0x04` (B→A) | A·A: row-varying | **536,536,536; col-indep** | **byte+6 = B (right)** |
| swap +5/+6 | B·A = 204+500 | **704 everywhere** | non-commutative ✓ |
| **+11** `0x01→0x00` | A·B only (drop C) | **8,16,24; 512** | **byte+11 bit0 = accumulate** |
| **+7** `0x09→0x00` | C accumulator changes | **8,16,0,0** | **byte+7 = C source** |
| **+8** `0xd4→0xd6` | dst changes | **508,515,522…** | **byte+8 = dst** |

byte+1 dtype confirmed by byte-diff: fp32 `cf 02 …` vs half `cf 00 …`; `p3_matmul_noacc` (D=A·B)
independently pins accum: byte+7 `0x09→0x00` **and** byte+11 `0x01→0x00` both clear vs the accumulate
version. All of A=+5/B=+6/C=+7/dst=+8/accum=+11 re-confirmed.

**Nuance recorded:** the **half datapath** (`p3_matmul_half`, byte+1=0x00) — although a
`multiply_accumulate` — encodes byte+10=`0x8c`/byte+11=`0x00`, *not* fp32's byte+10=`0x24`/byte+11=`0x01`.
So the documented op-enable/accumulate byte values are **fp32-specific**; the half datapath's
accumulate signalling is not the same byte and is **not yet characterized**. (Doc claims EXP-O2C
validated on fp32/`mad_f32`, so this is a follow-up, not a contradiction.)

## Part 4 — RT `rt_intersect` byte+4 AS-select — **CONFIRMED ⏳-inferred is HONEST**

Built **both** a primitive AS **and** an instance AS (top-level over an instanced bottom-level prim
AS, identity transform) via `rtrun2.m`. First `rt_intersect` (@+0x054) differs by AS type:
- primitive: `e4 ea 90 a6 **8b** 00 00 00`   ·   instance: `f4 ea 90 a6 **6b** 00 00 00`

So **byte+4 is a real byte-diff correlate** of AS type — **0x8b (primitive) / 0x6b (instance)**. This
**corrects** the old (already-retracted) "instance = 0x1b" value: the compiler emits **0x6b**, not 0x1b.

**But byte+4 is NOT the load-bearing selector** — splicing it is inert on both paths:
| path (bound AS) | byte+4 splice | result |
|---|---|---|
| prim code / prim AS | 0x8b (base) | hit `1 3 0 0.2` |
| prim code / prim AS | 0x8b→0x6b (inst val) | **`1 3 0 0.2` (inert)** |
| prim code / prim AS | 0x8b→0x1b (old claim) | **`1 3 0 0.2` (inert — re-falsifies the old claim)** |
| prim code / prim AS | 0x8b→0x00 | `1 3 0 0.2` (inert) |
| prim code / prim AS | 0x8b→0xff | GPU hang (out-of-range → parsed, but not AS-select) |
| inst code / inst AS | 0x6b→0x8b / 0x00 | **`1 3 0 0` (inert)** |

byte+2 mode (`0x90→0x10/0xd0`) also inert (re-confirms RT-5). The **real** prim-vs-instance
distinction is **structural**: the instance kernel emits a 2nd `rt_intersect` (`04 ea 10 …`, byte+2=0x10
dynamic-origin, @+0x690) plus ~2× the `0xdf` ray-transform loads. **Cross-bind proves it:** prim
traversal code on an instance AS → **MISS** (`0 inf 0 -9`); instance code on a primitive AS → **MISS**.
The AS-type handling lives in the whole compiled traversal path, not in byte+4.

⇒ The doc's `⏳-inferred` marking on the rt_intersect sub-fields is **honest and correct**. Refinement
for the doc: the observed instance byte+4 is **0x6b** (not the retracted 0x1b) — still ⏳ (does not
splice-validate).

## Part 5 — Large-shader census — big compute ≥90%, aggregate matches doc

Resync-tokenizer census over the repo DB (`tools/agx-isa/isadb.py`, 82 descriptors):

| shader | bytes | tokenized | named |
|---|---|---|---|
| **p5_bigcompute** (subgroup+matrix+CF+texture+atomics) | 934 | **94.6%** | 82.2% |
| p5_bigfrag fragment (varying+tex+deriv+CF+discard) | 1478 | 88.1% | 77.3% |
| p5_bigfrag vertex | 170 | 89.4% | 75.3% |
| **AGGREGATE (all 22 kernels)** | 8438 | **88.5%** | **77.9%** |

Big compute clears the ≥90% bar (94.6%); the fragment stage sits at 88.1% (denser interp/texcoord
operand residue). Aggregate **88.5% tok / 77.9% named** matches the doc's stated **88.0% / 77.1%**.

**No remaining undecoded byte0 group is a whole instruction family.** Every undecoded leader appears
only as scattered 2-byte fragments; ranked by bytes in the two big shaders: `0x00` (62B — a non-leader
mid-instruction byte = pure resync), `0x80`/`0x03`/`0x01` (mid-instruction bytes), then the
doc-acknowledged operand residue `0x2b`/`0x3b` (shift-prep), `0x25`/`0x54`/`0x56` (byte+2 markers seen
mid-stream after a desync), `0x92` (derivative-axis byte). All = operand sub-fields + resync artifacts,
exactly as the README claims.

---

## Discrepancies / follow-ups for the orchestrator
1. **(refinement)** RT `rt_intersect` byte+4 instance value is **0x6b** (observed by building a real
   instance AS), which corrects the stale/retracted "0x1b". Still ⏳ (splice-inert). byte+2 mode split
   `0x90` (top-level) vs `0x10` (transformed bottom-level) is real but also splice-inert.
2. **(nuance)** matrix `0xcf` **half** datapath encodes op-enable/accumulate differently (byte+10=0x8c,
   byte+11=0x00) than fp32 (0x24/0x01); the documented operand-byte values are fp32-specific — half's
   accumulate byte is uncharacterized.
3. **(nuance)** subgroup byte+1 **high**-nibble (ballot-pred vs active-mask) is not a clean
   splice-convertible field (operands co-vary); the DB naming (low-nibble family key) is correct.

None of these contradict a stated HW-validated claim. **The ISA tex/simd/matrix/RT/fragment cluster
passes its 2nd clean pass.**
