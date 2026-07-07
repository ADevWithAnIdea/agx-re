# RT-ISA-FIX RESULTS — batched ISA-DB fix + 0x0f exec-mask family decode

All HW results are from spliced/compiled bytes run on the real **A18 Pro / G17P, macOS 26.6** via
`tools/agxtest` (archived-code path, `FailOnBinaryArchiveMiss`). Compiles used `--no-fast-math`. Raw:
`raw/all_hex.txt` (extractions), `raw/hw_revalidation.log` (runs+splices). Round-trip test: **GREEN**
throughout (`tools/agx-isa/roundtrip_test.py` = ALL PASS). DB grew **77 → 82 descriptors** (+5).

---

## A. DB decode-bug fixes (RT-5) — each independently re-proven

### A1. Ballot `0x17` — CONFIRMED, fixed
- **Re-proof:** `simd_ballot(lane<5)` compiles to `17 17 54 00 02 00 14 48 22 0c` (byte+1=**0x17**, byte+2=0x54)
  and runs = **0x1F (=31)** all lanes. The **current DB mis-decoded it as `unpack_convert`** (verified).
- **Nuance found (RT-5 was incomplete):** `simd_active_threads_mask()` uses byte+1=**0x07** (which the DB
  already matched), while `simd_ballot(predicate)` uses byte+1=**0x17**. And `unpack_convert` uses byte+1=**0x04**
  and appears with BOTH byte+2=0x56 AND 0x54 (corpus line 177) — so byte+2 can **not** separate ballot from
  unpack.
- **Fix:** gate `simd_ballot` on byte+1 **low nibble == 0x7** (covers 0x07 AND 0x17); gate `unpack_convert` on
  byte+1 low nibble == 0x4. The two are now **mutually exclusive** (ballot=7 vs unpack=4), regardless of byte+2.
  Both `17 07 54` (active-mask) and `17 17 54` (predicate ballot) now decode as `simd_ballot`; `17 04 56` and
  `17 04 54` still decode as `unpack_convert`.

### A2. Shuffle gate — CONFIRMED, fixed
- **Re-proof:** `simd_broadcast(lane*10+5, 3)` = `47 04 54 00 02 00 06 2c 04 00` runs = **35** all lanes;
  `simd_shuffle_xor(v,3)` = `c7 04 54 ..` runs = **(lane^3)*10+5** = `35 25 15 5 75 65 55 45`. Both carry
  **byte+2=0x54**; the DB gated `simd_shuffle` on byte+2==**0x56** → both threw **"no descriptor matches"**.
- **Fix:** relax the `simd_shuffle` match byte+2 **bit1 to don't-care** (accept 0x54 & 0x56, like `simd_reduce`);
  add a `cache` field. Gate stays byte0 low-7==0x47 so the `0x37` derivative-vs-quad-reduce disambiguation in
  `instr_length` is **untouched**. Round-trip proves both the 0x54 and 0x56 forms decode + re-assemble byte-exact.

### A3. Reduce `byte+7` dtype — **RED-TEAMER WAS WRONG (RT-5 does not reproduce); NO CHANGE**
- **Independent compile** of the exact ops:
  - `simd_sum(int)` → `bf 11 54 00 02 00 14 **03**` (byte+7=**0x03**, not 0x01)
  - `simd_min/max(int)` → byte+7=**0x07**
  - `simd_prefix_inclusive_sum` → byte+7=**0x09**
  - `simd_prefix_exclusive_sum` → byte+7=**0x0b** (not 0x09)
  - `simd_sum(float)` → byte+7=**0x12**
  These are **exactly the current DB enum**. RT-5's claim ("int-reduce=0x01; exclusive-scan=0x09") did **not**
  reproduce on a fresh compile.
- **HW splice falsifies RT-5 further:** the working `byte+7=0x03` reduce (=496) with byte+7 spliced to **0x01**
  → still **496**; to **0x07** → still **496**. RT-5's "splicing to 0x03/0x07 breaks it (only lane 0 keeps 496)"
  did not reproduce — byte+7 is inert for the sum. Semantics of scan confirmed: inclusive=`[0,1,3,6,10,15,21,28]`,
  exclusive=`[0,0,1,3,6,10,15,21]`.
- **Verdict: leave the DB enum unchanged.** Applying RT-5's proposed change would have broken the decode of a
  real compiled reduce.

---

## B. The `0x0f` execution-mask family — DECODED (HW-validated)

Compiled if/else, while, for, break, continue, and nested-divergence kernels (`kernels/cf_*.metal`). The
`byte+1` sub-op and length were derived by tokenizing to clean termination (anchored by known-length ops) and
confirmed by HW splice. **New/fixed length rules + descriptors:**

| byte+1 | mnemonic | len | role | evidence |
|---|---|---|---|---|
| `0x00` | `jump` | 10 | unconditional PC-relative jump (loop back-edge / block skip) | back-edge off=−58 in cf_for; splice offset→0 = **CMDBUF_ERROR** |
| `0x01` | `jump_cond` (NEW) | 10 | conditional PC-relative jump — `else`-skip / `while`/`for` loop-exit guard | splice byte+1 `0x01→0x00` (cond→uncond) ⇒ **every lane skips the loop body → all-zero output** |
| `0x05` | `if_push` (NEW; was mis-lengthed 8) | **4** | execution-mask push (if-enter); byte+2 0x54 outer / 0x04 inner | required for clean tokenization; 14B `call` (byte+4==0x8f) keeps its gate |
| `0x06` | `pop_reconverge` (NEW) | 6 | mask pop / reconverge (block/loop end); byte+3 = level | splice byte+1 `0x06→0x00` ⇒ **CMDBUF_ERROR** |
| `0x80` | `call_indirect` (kept) | 6 | computed-target branch (indirect call / break-to-exit) | EXP-0035 |
| `0x04` | `mask_op` (NEW, ⏳ inferred) | 4 | inner mask op in deep nesting (continue-edge re-mask) | single occurrence in cf_big, anchored by a following `0f 01` |

Plus the `0x8f` sibling (`8f 04/05 54 ..`) is a 4-byte **CF merge/reconverge** marker at if/else and loop joins
(same op as `ret` `8f 02/12 54` with a different byte+1 — enum extended). And the **`0x07` fence byte+2∈{0x00,0x02}**
variant is now a 4-byte `scoreboard_fence` (`07 22 02 00` precedes an out-of-line call; `07 02/00 00` around
divergence) — closes the RT-1b census halt. **`0x32` carry-gen** was already merged (`length 6`, match byte+2==0x35);
verified it tokenizes + decodes.

**Do they tokenize now?** Yes — **42/42** `0x0f` ops across the CF corpus decode (was: only `0f 00`/`0f 05`-call/
`0f 06`/`0f 80` had descriptors; the family halted strict tokenization). Per-kernel: cf_for 91.9% named,
cf_ifelse 93.9%, cf_nested 79.4%, cf_while 86.0%, cf_big 69.9% — remaining un-named bytes are the pre-existing
`0x2b`/`0x3b`/`0x5b` register/shift-prep family (out of scope), **not** `0x0f`.

---

## C. Descriptor count, round-trip, census

- **Descriptors: 77 → 82** (+`jump_cond`, `if_push`, `pop_reconverge`, `mask_op`, `scoreboard_fence`).
- **Round-trip: ALL PASS** (real-instr A, synth B, whole-program tokenize C, imm codec D). Added 12 real
  HW-byte entries (ballot 0x17, active-mask, shuffle 0x54 bcast/xor, jump/jump_cond/if_push/pop_reconverge/
  cf_merge, two fences) — all decode to the correct mnemonic and re-assemble byte-exact.
- **Census (regenerated `db.json`):** EXP-0036 subcorpus **90.6%** byte coverage (was EXP-0039's 87.9%),
  combined corpus **86.9%**. CF corpus: `0x0f`-family decode **0→42/42**; byte coverage 73.7%→78.2%.

## D. Doc corrections applied (`docs/isa/README.md`)
1. **Uniform source (RT-7):** now documents **BOTH** valid encodings — uniform-srcB via **byte+2 bit4 + byte+5 bit1**
   AND uniform-srcA (`falu2_uni`) via **bit39** — selected by operand position. Removed the wrong "byte+2-bit4 was
   superseded/wrong" framing.
2. **r96+ (RT-7):** r0–r95 = **96 distinct GPRs, a hard silicon boundary**; r96–r127 **FAULT** as a memory index,
   **read 0** as an ALU source, never alias live data.
3. **Occupancy tier (RT-7):** softened "≤11/≥12 GPRs" to **interpolated, not measured** (only f0=8 clear / f0=14 set captured).
4. **threadgroups_per_grid (RT-7):** `get_sr 0xa8` **+ load + divide**; a bare `get_sr 0xa8` returns threads_per_threadgroup.
5. **Texture (RT-5):** op+4 texture-slot folds to a bit7 2-way flip under **direct** binding (indexes only via the
   Tier-2 argument-buffer path, caveat noted); op+6 is **NOT** the filter selector (filter is sampler-controlled — splice no-op).
6. **rt_intersect (RT-5):** the op is HW-validated & load-bearing, but its AS-select sub-fields
   (byte+4 `0x8b/0x1b/0xbb`, byte0 result-reg, byte+2 mode) are re-marked **⏳ inferred, not HW-validated** —
   RT-5 found EXP-O2C's "0x8b→0x1b HW-validated" did **not** reproduce (all splices inert on the primitive path);
   the motion-blur `0xbb` byte is likewise inferred.
7. **Subgroup section + census note:** updated to the corrected ballot/shuffle/reduce facts.

## Clean-room status
Clean. Only our own MSL compiled; only our own compiled bytes inspected/spliced/executed. Reused
`shdump`/`agxparse`/`agxrun`/`agxtest` + `tools/agx-isa`. Did not edit `tools/iotrace/`, other `docs/*`,
`PROVENANCE`, `ROADMAP`, `reviews/`. Did not commit. `raw/` holds text logs only.
