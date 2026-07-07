# EXP-0038 Results — half pack/unpack `0x18/0x30/0x38`, u64 carry `0x32`, non-leaf frame `0x6f`/`0x07`, `0x54` cache-bit

Clean-room category: **OWN-SHADER + HW-PROBE** (+ PUBLIC for the applegpu *shape*). Every byte
inspected/spliced/executed is the compiled form of MSL we wrote. No Apple binary was disassembled.
Device: Apple A18 Pro / G17P, SoC T8140, macOS 26.6 (25G5043d), Metal 4 / Apple9. **No faults, no reboots.**

Legend: ✅ HW-validated (behaviour matched on hardware) · 🔬 splice-proven (byte spliced + observed) ·
📐 byte-diff / structural (inferred from differential compile / anchored tokenization).

---

## 1. Half pack/unpack — `0x18` (compute), `0x30`/`0x38` (siblings)

Native fp16 arithmetic is the `0x10` half-ALU group (EXP-0033). A `half2` computes **both lanes in one
`0x10` op**, then a **`0x18` pack op assembles the two fp16 lanes into one packed 32-bit register** for the
store. Anchored segmentation of our own half kernels (the pack region is exactly the residual after the
known get_sr/loads/`0x10` half_alu/store/stop):

| kernel | `0x10` half ALU | **`0x18` pack** | len |
|---|---|---|---|
| `k_h2add` (`a+b`) | `10 04 1c 02 00 c0` (hadd) | `18 05 18 03` | 4 B ✅📐 |
| `k_h2mul` (`a*b`) | `10 04 1d 02 00 c0` (hmul) | `18 05 19 03` | 4 B ✅📐 |
| `k_h2fma` (`a*b+c`) | `10 04 1e 02 81 06 00 c0` (hfma, 8 B) | `18 05 1b 07` | 4 B ✅📐 |

- **`0x18` half-pack = 4 bytes** (compute), confirmed across add/mul/fma. `byte0` HIGH nibble = destination
  register nibble (r0..r15), so the **same op appears as `0x08`/`0x18`/`0x28`/`0x38` for dst r0/r1/r2/r3** —
  which is why the EXP-0036 census (broad corpus, higher registers, vertex/frag/tex) shows `0x38`
  (`38 82 24 84 …`, dst r3) while our low-register compute shows `0x08`/`0x18`. `byte+2` = source register
  `(reg<<1)|hint` (`0x18`/`0x19`/`0x1b` track the half_alu result reg / op). 📐
- **HW-validated round-trip (✅):** `k_h2roundtrip` (float2 → fp16 **pack (`0x18`)** → store → load → **unpack** →
  float2) returns **exact** for all 8 test values (`1.5, 2.25, 0.5, 10.0, 3.5, 7.0, 0.0625, 30.0`) —
  `raw/hw_validation.txt`. This proves the pack/unpack semantics end-to-end.
- **`0x30`/`0x38`** are the **sibling half-pack forms** (`0x30 = 0x10|0x20`, `0x38 = 0x18|0x20`) for half4 /
  higher-lane packs (census `38 82 24 84 00 c8  30 83 24 85 00 08`, `byte+2==0x24`). In our own `half4`
  compute kernels the pack region uses `byte0` `0x00`/`0x08`/`0x18` (low registers). Same family structure
  (`byte0` hi = dst, `byte+2` = src reg). Exact length (4 vs the census 6-byte high-register form) and the
  low-nibble-0 (`0x30`) vs low-nibble-8 (`0x18`/`0x38`) role are **inferred (📐), a documented follow-up.**
- **Contrast (EXP-0033 corroborated):** `as_type` half↔uint bitcast is **free** (no op); `short2/short4`
  (int16) does **NOT** pack — two separate 32-bit `0x9f` adds. Only fp16 has the packed 2-lane datapath.

## 2. u64 carry-generate — `0x32` (6 bytes) + how it chains

The compiler lowers 64-bit **ADD** to an explicit carry chain (64-bit **SUB** is a single native `0x1f`,
EXP-0033). For `ulong c = a + b` (`k_u64add`):

```
9f 01 56 00 03 04 1a a8 15 05   iadd2   sum_lo = a_lo + b_lo
32 01 35 03 22 81               CARRY-GEN (0x32, 6 B)  -- detects carry-out of sum_lo
05 00 20 80                     psel    carry = overflow ? 1 : 0
9f 01 54 02 03 08 20 a8 17 05   iadd2   sum_hi = a_hi + b_hi
9f 01 54 02 02 0c 08 88 17 05   iadd2   sum_hi += carry
```

- **`0x32` carry-generate = 6 bytes**, an **unsigned-overflow compare** in the integer compare / min-max
  family (`byte0 0x32 = base 0x02 | 0x30`; `byte+2 == 0x35` marker; `byte+4 == 0x22` = the icmpsel
  ordered-compare mode, EXP-0013). It computes "did `sum_lo` carry" (`sum_lo < operand`, unsigned); the
  predicate feeds the `0x05` psel that materializes the carry as `{0,1}`, which the following high-word
  `0x9f` add consumes. 📐
- **Siblings:** `byte0 0x12` (the `a + const` variant, `k_u64addk`) and `byte0 0x22` (the intermediate carry
  of a 3-operand add, `k_u64add3`) share the `byte+2 == 0x35` signature — all 6-byte carry compares.
- **✅ HW-validated behaviour:** low→high carry (`0xFFFFFFFF + 1 → lo=0, hi=1`), full carry-out
  (`0xFFFF…FFFF + 1 → 0`), both-word carry, and the 3-operand two-chain add — all exact (`raw/hw_validation.txt`).
- **🔬 SPLICE-PROVEN load-bearing:** neutralizing the `0x32` op — either `byte0 0x32→0x00` **or** the
  compare-mode `byte+4 0x22→0x26` — **drops the carry**: `0xFFFFFFFF + 1` returns `lo=0, hi=0` instead of
  `hi=1`, while the low word stays correct (contained, STATUS OK). So the `0x32` op is exactly the carry
  source for the high-word chain.

## 3. Non-leaf function frame — `0x6f` prologue + `0x07` link save/restore + `8f 12` ret

The `0x6f` prologue lives in the **helper (callee) region**, not `_agc.main` (so it's invisible to a
`_agc.main`-only extract). Extracting every symbol region of `k_chain` (main → `mid()` non-leaf →
`leaf_add`/`leaf_mul`) shows the full non-leaf frame in the `mid()` region:

```
6f 03 04 00 00 20              PROLOGUE (0x6f, 6 B)               -- establish scratch frame
07 00 54 00 81 00 00 00        LINK SAVE (0x07, 8 B)  before call
0f 05 54 1a 8f 10 54 6a …      call leaf_add
07 00 54 00 81 ff 1f 00        LINK RESTORE (0x07, 8 B) after call
… (repeat save/call/restore for leaf_mul) …
8f 12 54 00                    RET (non-leaf: byte+1 = 0x12)
```

- **`0x6f` non-leaf prologue = 6 bytes** (`6f 03 04 00 00 20`; the census also shows `6f 03 54 00 00 10`).
  Present verbatim in **every** non-leaf helper (`mid`/`mid2`/`outer`/`bigmid`) and **absent from every
  leaf** helper (leaf = arithmetic op then `8f 02 54 00`). `byte+1 == 0x03` sub-op (constant); `byte+2` =
  `0x04`/`0x54` marker; `byte+5` = candidate **frame/scratch-size field** (`0x20` here vs `0x10` in census)
  — 📐 **inferred**; it did **not** move in a controlled spilling test (`k_bigframe`) because the extra
  temporaries stayed within the 96-GPR file (spill scratch is separate, in `__GPU_METADATA`, EXP-0020).
- **`0x07` link save/restore = 8 bytes**, gated by `byte+1 == 0x00` — an 8-byte member of the `0x07`
  fence/ordering family (cf. the 6-byte threadgroup_barrier `byte+1==0x04` and pixel_order `byte+1==0x14`).
  `byte+4 == 0x81` = scratch/stack scope; `byte+5..+7` = SAVE (`00 00 00`) vs RESTORE (`ff 1f 00`) offset.
  It spills the return/link register because each nested CALL clobbers the hardware link register (RET
  encodes no target — EXP-0035). ✅ role, 📐 fields.
- **✅ HW-validated:** `k_chain` (`(a+b)+(a*b)`) → `23,5,11,9` for `a={3,1,2,4} b={5,2,3,1}`; the 3-level
  `k_deep` (`(a+b)*2+1`) → `17,61` — both exact (`raw/hw_validation.txt`). Confirms EXP-0035's inference.
- The `8f 12 54 00` **non-leaf RET** (already in the DB as `ret` linkmode `0x12`) is confirmed at the tail of
  every non-leaf helper; leaf helpers use `8f 02 54 00`.

## 4. `0x54 ↔ 0x56` cache-bit — meaning + gating fix

`byte+2` bit 1 (**instruction bit 17**; `0x54 = 0101_0100`, `0x56 = 0101_0110`, XOR `0x02`) is a **source
CACHE / LAST-USE scheduling hint**, NOT an opcode/operation change. Proven:

| context | op | `byte+2` |
|---|---|---|
| standalone `simd_max` (`k_rmax`) | max | **0x56** |
| standalone `simd_min/and/or/xor/sum/fadd` | — | **0x56** |
| `simd_max` as the **2nd consumer** of a shared source (`k_reduce_two`) | max | **0x54** |
| `simd_sum` (either 1st or 2nd consumer) | sum | 0x56 |

The **same** `simd_max` op is `0x56` standalone but `0x54` as a later consumer of a still-live source — so
the bit tracks source liveness/caching, not the op. The current DB **gates `simd_reduce` (and the
byte+2-gated `unpack_convert`/`pack_convert`) on `byte+2 == 0x56` only**, so the `0x54` variants fall
through with no length/name — this is exactly the census `bf 00 54` / `17 04 54` gap.

**Fix (verified, `verify_fixes.py` → 0 leftover, and the variants now NAME):**
- **Length rule:** for `simd_reduce` (`0xbf`/`0x3f`/`0xb7`), gate on `(byte+2 & ~0x02) == 0x54` (accept
  `0x54` and `0x56`), not `== 0x56`. (Length stays 8. `0x17` unpack is already length-8-independent of byte+2.)
- **Descriptor match:** for `simd_reduce`, `unpack_convert`, `pack_convert`, replace the exact `(16,8,0x56)`
  match tuple with `(16,1,0)+(18,6,0x15)` — i.e. make bit 17 a **don't-care** so both variants name.
- After the fix, `bf 03 54 …` names `simd_reduce` and `17 04 54 …` names `unpack_convert`.

⚠ **Caveat for the orchestrator:** `0x37`/`0xb7` are shared with the fragment **derivative** op (10 B) vs
quad-reduce (8 B); keep the derivative's existing disambiguation (it does not carry the `0x56` reduce
marker). The masked gate is applied only to the `0xbf`/`0x3f`/`0xb7` reduce leaders where it is unambiguous.

---

## HW-validated vs inferred (summary)

| Finding | Status |
|---|---|
| `0x18` half-pack = 4 B; half2 pack→store→unpack round-trip exact | ✅ (round-trip) · 📐 (4 B segmentation, fields) |
| `0x18` byte0-hi = dst nibble → 0x08/0x18/0x28/0x38 family; `0x30/0x38` siblings; 6-B high-reg form | 📐 inferred (follow-up) |
| `0x32` carry-generate = 6 B, compare-family, `byte+2==0x35` | 📐 (structure) |
| `0x32` generates the carry for the u64-add chain; chain order | ✅ (all carry cases) · 🔬 (splice drops carry) |
| `0x6f` non-leaf prologue = 6 B; present in non-leaf, absent in leaf | ✅ (role) · 📐 (fields, frame-size byte+5) |
| `0x07` link save/restore = 8 B (`byte+1==0x00`); brackets each nested call | ✅ (role) · 📐 (fields) |
| `8f 12` non-leaf ret vs `8f 02` leaf ret | ✅ (confirmed at every helper tail) |
| `0x54↔0x56` = byte+2 bit1 source cache/last-use hint (not op) | ✅ (same op both values) · 📐 (exact semantics) |
| Length-rule + match-gating fixes tokenize all 6 problem streams to 0 leftover | ✅ (verify_fixes.py) |

## Deliverables
- `new_descriptors.json` — **4 new descriptors** (`carry_gen`, `frame_prologue`, `link_save_restore`,
  `half_pack`) + **6 length-rule additions** (`0x6f`, `0x07` link-vs-barrier, `0x32`, `0x18`, simd_reduce
  cache-bit, `0x22` byte+2==0x35) + **3 match-gating relaxations** (simd_reduce / unpack_convert /
  pack_convert accept the cache bit), all in the `tools/agx-isa` db.json schema. Orchestrator merges.
- Harness (ours): `kernels/*.metal`, `analyze.py`, `dumpregions.py`, `verify_fixes.py`.
- `raw/` — text logs only (`tokenize_dumps.txt`, `hw_validation.txt`, `verify_fixes.txt`).

## Recommended next
1. **Re-run the census** with the merged DB — these fixes convert the flagged `0x18/0x30/0x38`, `0x32`,
   `0x6f`, `0x07`-link, and `0x54`-reduce/unpack undecoded regions into named/lengthed ops (the largest
   remaining compute gaps). Then the residual frontier is the vertex/mesh varying-emit `0x05/0x06/0x57`
   and texture-address math `0x2e/0xb0/0x92/0x26`.
2. Isolate the `0x6f` frame-size field (byte+5) with a callee that spills scratch *around* a call.
3. The `0x30/0x38` half-pack length/role and the 6-byte high-register `0x18` form.
4. The `0x73` (`73 00 00 01`) second frame/call marker seen alongside `0x43` in the census.

## Clean-room status
Clean. Only our own MSL was compiled; only our own compiled bytes were inspected/spliced/executed. Reused
OWN-SHADER tools (`shdump`, `agxparse.py`, `agxrun`, `agxtest.py`) and READ-ONLY `tools/agx-isa` for
tokenizing. No `docs/`, `PROVENANCE`, `tools/agx-isa/`, `tools/iotrace/`, or `reviews/` were edited; nothing
was committed. `.bin`/`.metallib` archives stayed on the device under `~/cleanroom_work/exp0038/`.
