# EXP-M5-07 — M5 ISA semantics: splice-and-observe on the memory & delta families

**Device:** Apple M5 / Apple10 / G17g / T8142 / macOS 27.0. Every field resolution is HW-evidenced by
an observed output delta from a splice-and-observe dispatch (`agxtest.py`) or a byte-diff of our own
compiles (marked). No Apple binary introspected.

## Headline: the M5 memory model is SPLIT (not A18's monolithic device_load)
A18's single 14-byte `device_load`(0x67)/`device_store`(0xe7) becomes **three ops** on M5 (G17g):
```
<reg>f <slot<<2> 03 <idxmode>        ADDRESS-GEN  (4B)   base[slot] + index -> addr reg
0x18|(n-1)<<5 <amode> 10 <esize> …   LOAD         (10B/4B)  0x18/0x38/0x58/0x78 = 1/2/3/4-component
0x01|(n-1)<<5 <dsrc> <b2> <fmt> …    STORE        (4B/6B)   0x01/0x21/0x41/0x61 = 1/2/3/4-component
```
**This CORRECTS the EXP-M5-02 census guesses:** the "0x41/0xc1 store" (census ranks 2-3) are the *tail
bytes of the 10-byte load*, not a store — the real store leader is **0x01**. The "0x78/0x58/0x50
typed/sample" family (rank 10) are the **vec4/vec3/vec2 LOAD** leaders (component count = byte0 bits[5:6]),
not texture samples. The "0x0f jump" the census saw was the load **address-gen** op mis-lengthed.

## Resolved (HW splice evidence)
- **Address-gen `?f <slot<<2> 03 <idx>`:** `byte+2==0x03` = family signature (jump uses 0x54).
  `base_slot`=byte+1(=slot×4) **PROVEN** (ld_2sum load#2 byte+1 0x04→0x00 reads buf0=2·a not buf1;
  ld_buf3 a/b/c/out=0x00/04/08/0c). `idx_mode`=byte+3 **PROVEN** (0x02→0x00 reads index 0 for all threads).
  byte0-hi = dest addr reg (proven by misroute). Load-bearing (zeroing → all-zero out).
- **LOAD 0x18/38/58/78:** `elem_size`=byte+3 **PROVEN** (0xc0→0x80 = a[4i] 16B stride; 0xc0→0xa0 = a[i/4]
  1B stride; reproduced on ld_2sum b-load). byte+2==0x10 + byte+4 load-bearing; byte+5/6/7 inert (negative).
  4-byte non-terminal form (byte+3==0x40) when the result feeds an ALU.
- **STORE 0x01/21/41/61:** byte+1(`dsrc`) + byte+3(`st_fmt`) load-bearing; data register implicit (like A18).
  **LOAD vs STORE is NOT a direction bit — distinct opcodes** (task's direction question, negative result).
  **Immediate-move `04 <imm>`** proven (byte+1 0x2a→0x37 changes stored constant 42→55).

## Open / partial (honest — recorded, not guessed)
- **Short-ALU `0xNe` (0x3e/5e/9e/be/fe):** 4B compact ALU/move, byte+3==0x0e marker; byte+1=source operand
  **HW-proven load-bearing**; byte+2 op-select map (add/mul/mov) **OPEN** (these callfn instances are
  register-marshalling moves; needs a single-op isolation kernel).
- **`0xb7`:** **OPEN, could not provoke** — quad_shuffle_xor/quad_max/simd_sum lower to byte0 `0x2f`
  (byte+6=0xa7/0xa3/0xa1), not 0xb7. Negative recorded.
- **Call `0xef`/`0xff` (`43` marker):** **OPEN** — the `noinline` helper inlined; `43 00 00 01` is the
  call/frame marker (present, inert when inlined). Needs a `visible_function_table` provocation.
- **Inherited-op spot-check:** 0x2f imad, 0x27 iadd, 0x29 ffma behave as A18-documented (ld_2sum a+b
  dispatched correct on HW). One delta: `2f 00 04 3a …` integer add is 12B on M5 but the inherited rule
  lengths it 10B — separate integer-ALU item.

## Validation
- **Round-trip: ALL PASS** on the integrated DB.
- **Census (both corpora, hard-timed):** own 96.55%→**96.59%** (named 85.14→85.30%), tp 97.98%→**98.17%**
  (named 90.86→91.19%). No regressions, 0 hangs.
- **M5 fault behavior (first-class):** all ~40 splices, incl. deliberately-broken encodings, returned
  STATUS OK with graceful recovery. **Zero hangs, zero reboots — M5 memory-op faults are fully contained;
  splice-and-observe is low-risk here.**

## Integration
Patch applied to `tools/agx-isa-m5/isadb.py` (5 new descriptors + 3 length rules before the R9 closure +
`mask_op` narrowed so it no longer captures the store addr-gen); `db.json` regenerated (175 descriptors).

## Known follow-ups
1. **vec3/vec4 STORE naming:** 0x41/0x61 byte-collide with the inherited `cvt_f2h_dst` at length 6 —
   length/coverage/round-trip are correct but those two stores *name* as cvt_f2h (scalar/vec2 name
   correctly). A byte0-specific len-6 override for 0x41/0x61 closes it. **[tracked, low-risk]**
2. Op-select map for `0xNe`; provoke `0xb7`; call ABI via visible_function_table; the 0x2f 12B integer-add delta.

## Files
`isadb.py.EXP-M5-07.patch` (reviewable unified diff), `hex_extractions.txt` (24 kernels' `_agc.main`),
`kernels/*.metal` (24 own-MSL provocations). Clean-room: own-MSL + our tooling, HW-evidenced field-by-field;
no Apple binary disassembled; negatives/opens recorded.
