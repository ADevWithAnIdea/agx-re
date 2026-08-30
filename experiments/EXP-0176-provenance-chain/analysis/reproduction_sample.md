# EXP-0176 — the reproduction sample: do the corpus's CLAIMS hold, not just its citations?

`EXP-0173` proved that **168 of 171** rows cite artifacts that exist, but could only mark
`claim_reproduced` for 9 of them; the other **162** were `not-mechanically-checkable`. Existence
was proven; **truth was not**. This is the first sample that tests truth.

## Method, and what it can and cannot show

- **Selection is blind and reproducible.** `analysis/sample_rows.py` seeds Python's RNG with the
  fixed constant `20260830` and draws 10 of the 174 logical table rows. The seed was fixed
  **before** any row was opened, so the sample is not the convenient rows.
  Selected lines: **25, 31, 43, 75, 89, 100, 137, 157, 170, 190.**
- **L89 is a glued line carrying TWO logical rows** (see `broken_rows.md` D-6), so it is scored as
  **L89-a** and **L89-b**. That makes 11 claims across the 10 drawn lines.
- **What "reproduces" means here.** This is pure analysis on the repo host: **no hardware was
  touched, so no `HW-VALIDATED` claim can be re-observed.** What was done instead, per row, is
  stronger than the audit's grep: the cited artifacts were opened, the row's *specific numbers,
  byte strings, addresses and arithmetic* were recomputed from them, and the row was scored on
  whether those recomputations agree. Where a row asserts a relationship (a ratio, a modulus, a
  formula), the relationship itself was checked, not just the presence of a literal.
- **Limitation, stated plainly.** A row can pass here and still be wrong about the hardware, if the
  underlying capture was wrong. This sample tests *the corpus against itself*.

## Verdict

| | count |
|---|---:|
| **REPRODUCES** — every specific number, byte string and relationship recomputed and agreed | **9 of 11** |
| **PARTIAL** — the load-bearing claim reproduces; a summary statistic is optimistically framed | **1** (L190) |
| **FAILS AS WRITTEN** — the claim is refuted in general, by our own later experiment | **1** (L75) |

**Read positively: the corpus's claims are in much better shape than its citations.** Nine of
eleven reproduced to the digit, including two that reproduce *arithmetically* (L157's exact 2.0
ratio and its `1 − b0 − b1` third component; L137's dense 2048-point monotone sweep). That is real
evidence that the underlying work is sound.

**Read as a warning: the two that did not are both the same failure mode — a claim that outran the
data it was measured on, and was never walked back in the log.** L75 generalized a bpp4
measurement to all bit depths and was refuted by `EXP-M4-07`; L190 reports a per-field cross-run
agreement that is the *best* of its arms, hiding two others. Neither is fabrication. Both are the
thing this audit exists to catch.

---

## Row-by-row

### ✅ L25 — EXP-0002, Metal capability limits — **REPRODUCES (12 of 12 values)**

Every value in the row was located in `experiments/EXP-0002-hw-identity-recon/raw/metal_caps.txt`:

| claimed | line | file value |
|---|---:|---|
| maxThreadsPerThreadgroup 1024³ | 22 | `(1024, 1024, 1024)` |
| maxThreadgroupMemoryLength 32 KiB | 23 | `0x8000 (32768)` |
| maxBufferLength 4 GiB | 18 | `0x100000000 (4294967296)` |
| arg-buffers Tier2 | 27 | `argumentBuffersSupport(0=T1,1=T2) = 1` |
| RW-textures Tier2 | 28 | `readWriteTextureSupport(0=None..2) = 2` |
| sparse tile 16 KiB | 49 | `sparseTileSizeInBytes = 0x4000 (16384)` |
| supportsRaytracing / FromRender / PrimitiveMotionBlur | 29-31 | all `YES` |
| function pointers, incl. from render | 32-33 | both `YES` |
| dynamic libraries, incl. from render | 34-35 | both `YES` |
| Apple1–9 + Metal3/4 | 53-68 | Apple1…Apple9 `YES`, Metal3 `YES`, Metal4 `YES`, and **no Apple10 row exists**, which is what makes "Apple9 max" a measurement rather than an assumption |

**Verdict: REPRODUCES.** The cited harness `metal_caps.m` is committed and reads capability
properties only, with no GPU work — consistent with the `HW-PROBE` label.

### ✅ L31 — EXP-0003, the splice testbed and "Metal runs tampered code" — **REPRODUCES**

- `tools/agxtest/agxrun.m` contains `FailOnBinaryArchiveMiss` **5 times**, which is the mechanism
  the row names for forcing instantiation from archived machine code rather than an AIR recompile.
- `raw/stage1_identity.log`: `PIPELINE_SOURCE archive`, `STATUS OK`,
  `RESULT 2 11 22 33 44 55 66 77 88` = `EXPECT`, `COMPARE 2 MATCH` — the identity round-trip.
- `raw/stage1b_noop_splice.log`: `SPLICE _agc.main@0x22: 1c -> 1c (abs file offset 7554)`,
  `MAIN_SPLICED` byte-identical to `MAIN_ORIG`, same correct result — the no-op splice, which is
  what proves write-path fidelity rather than merely that the program still runs.
- `PIPELINE_SOURCE archive` appears in **9 of the 9** raw logs, including all four fault cases, so
  the "no integrity check" claim is supported by the *tampered* runs, not only the identity one.

**Verdict: REPRODUCES.**

### ✅ L43 — EXP-0023, ray tracing is HYBRID — **REPRODUCES (every element)**

- `rt_intersect` at byte0 low-nibble `0x4` + byte+1 `0xea`, 8 bytes: five distinct instances in
  `RESULTS.md` §2, e.g. `d4 ea 90 a6 8b 00 00 00`, `94 ea 90 86 8b 00 00 00`,
  `e4 ea 90 a6 1b 00 00 00`.
- **The negative control is the load-bearing half and it holds:** `raw/rtops.txt` shows
  `intersect(X4/ea)=2` for every RT kernel and **`=0` for both hand-written software ray/triangle
  kernels** (`hand_trace`, `hand_one`) — so the ops are RT-specific, not generic.
- Traversal loop: `isect_*` kernels each show `back-jumps(loops)=1 offs=[-88]`.
- `rt_as_load` `0xdf`, 14 bytes: recorded in §2/§5 and absent from the software control.
- "6 known rays validated": `raw/hwval.txt` shows rays 0–4 hitting at `t=3.0000 prim=0` with
  distinct barycentrics and **ray 5 missing** (`t=-1.0000 prim=-1`) against a real
  `MTLAccelerationStructure` built from a known triangle — i.e. 5 hits + 1 designed miss.
- "DB 38 descriptors, round-trip 188 OK": `RESULTS.md:174` and `README.md:66`.

**Verdict: REPRODUCES.**

### ⛔ L75 — EXP-0017, lossless compression aux size — **FAILS AS WRITTEN**

The row states, unqualified: **`aux size = image_bytes/128 = 1 state byte per 8×4 block`**.

**Within EXP-0017's own data it is exact.** `RESULTS.md` §3b tabulates five rgba8 sizes — 64², 128²,
256², 512², 1024² — with aux of `0x80`, `0x200`, `0x800`, `0x2000`, `0x8000`, each `main/128`, and
`:142` states the formula.

**But every one of those measurements is bpp4, and the row generalizes to all formats.**
`EXP-M4-07` (TIL-5) refuted it: *"aux = 1 byte / 8×4-texel block = numTexels/32 =
paddedImageBytes/(32·bpp); formula A (÷128) refuted at bpp8/16"*. And
`docs/tiling/README.md:236-237` already carries the correction in the deliverable —
*"The old `aux_bytes = image_bytes / 128` formula is WRONG for bpp≠4 — it over-counts 2× at bpp8
and 4× at bpp16 (measured aux = 0x800 for a 256² rgba32f, where ÷128 would give 0x2000)."*

**Verdict: FAILS AS WRITTEN.** The row reproduces only as a bpp4 special case; as stated it is
false at bpp8 and bpp16, and it is a **memory-safety** formula — under-allocating an aux buffer is
not a cosmetic error.

**Why it is still standing.** `CODEX.md` §8 requires a corrected result to be marked `SUPERSEDED`
with the correcting experiment cited. That never happened here — and one reason is structural:
**`EXP-M4-07` has no `PROVENANCE.md` row at all**, so there was nothing in the log to cite. The
docs are right, the log is wrong, and the two were never reconciled. Corrected text: `broken_rows.md` D-8.

### ✅ L89-a — EXP-0024, PPP header and CDM config — **REPRODUCES**

`experiments/EXP-0024-usc-ppp-config/RESULTS.md`:

- "no present-mask; presence = monotonic length word … grow +0x400 when depth/stencil appended":
  `:104` VDM `+0x0c` state-alloc `0x4800 → 0x4c00` (**+0x400**), `:106` pool `0x58000+0x14`
  `0x4c19 → 0x5019` (**+0x400**), `:107` "the optional depth/stencil block adds 0x400 bytes".
- Per-packet enable bits, all four, at `:113-116`: depth `+0x34` bit18 (`0x00040000`); stencil
  `+0x34` bits[19:18] → `0x000c0000`; blend `+0x18` `0→1` and `+0x50` `0x200 → 0x20000200`;
  cull `+0x70` bits[1:0] (`0x480 → 0x482`).
- CDM config: `:24` `+0x00` is `0x00080000` (bit19 always set) with `:25` "bit23 = register/occupancy
  tier as the **only** variable", and the table at `:131-133` shows `add3/atom/barr/simd` all
  `0x00080000`, `heavy` `0x00880000` (bit23 set), and **tg-mem sweeps not touching it** — which is
  the control that makes "bit23 = occupancy" a measurement rather than a correlation.
- Threadgroup-mem size in the shader BO: `:27` `(tgmem_bytes << 2) | 0x80`, HW-validated over
  256…32768 B, static and dynamic; dynamic at `+0x4c` bits[31:16] (`:156`).

**Verdict: REPRODUCES.**

### ✅ L89-b — EXP-0021, TBDR tile size 32×32 fixed — **REPRODUCES**

`experiments/EXP-0021-tbdr-pipeline/RESULTS.md`:

- `:29-30` `+0x904 = 0x80000000 | (ceil(W_px/32) − 1)` and `+0x908 = ceil(H_px/32) − 1`, with an
  11-point RT-size sweep at `:35-51`; **the asymmetric 64×128 / 128×64 pair is the control that
  proves `+0x904` tracks width and `+0x908` height**, which is exactly the discriminator the claim
  needs.
- "does NOT scale with bpp": `:56-58` — a 16 B × 4-sample × 1024-pixel configuration needs a 64 KiB
  imageblock against 32 KiB of tile SRAM and **the grid stays 32×32**; the byte budget is handled by
  allocation, not by shrinking tiles. The row's "delta from G13/G14 shrink-tile" is stated in the
  same paragraph.
- Imageblock budget and record: `:68` tile = 1024 pixels with a 32 KiB on-chip budget; `:71`
  per-attachment **0x20-byte record**; `:83` bgra8 MRT stride HW-validated.

**Verdict: REPRODUCES.** ⚠ Both halves are true; the **line** they share is malformed (`broken_rows.md` D-6).

### ✅ L100 — EXP-O2D, compute/fragment tail — **REPRODUCES**

- **"64-bit atomics ENTIRELY absent from MSL"** — `raw/probe64.txt` shows **all nine** spellings
  failing at every language version: `atomic_fetch_add/min/max(signed and unsigned)/and/or/xor`,
  `atomic_exchange`, `atomic_load`, each `ALL-VER FAIL: no matching function`. The 32-bit controls
  in the same file compile and produce machine code, so the failure is specific, not environmental.
  The row's wording ("absent from **MSL**") matches what the artifact shows; `RESULTS.md:38` is
  equally careful — *"no reachable 64-bit atomic instruction … from the MSL path"* — so this is an
  API-surface negative, not a hardware-absence claim.
- Fence: `:20` `mem_device`, seq_cst → `07 04 54 84 0a 00`, byte+3 `0x84`.
- `simd_product` = `0xbf`, byte+1 `0x06`: `:66-67`, **HW-validated by splicing byte0 `0xbf → 0x3f`**
  and observing the 32-lane product flip. Integer `simd_product` has **no** native op and lowers to
  a log2(32)-step shuffle+imul tree with **zero** `0xbf` (`:72-73`) — a recorded negative.
- `simd_is_helper_thread` = `get_sr` SR `0x84` (`:79`); imageblock write/read `0xe7`/`0x67` with
  slice byte+5 = offset>>1, HW-proven on a 3-field imageblock (`:92-95`).

**Verdict: REPRODUCES.**

### ✅ L137 — EXP-0082, memory-operand field semantics — **REPRODUCES, recomputed from raw**

This row was checked against `raw/`, not against its own `RESULTS.md`.

- **"2164 cases ×2 runs, `04_results.jsonl` byte-identical":** both files have exactly **2164**
  lines and both hash to `b29f905a44de38ef4759a38c94fe45bfabdc668a6aa901b4942a3b8f12f9a76c`.
- **"`04_timing.jsonl` differs as designed":** the two timing files hash differently
  (`794fb5f6…` vs `d4aca82b…`) — so the gated/nongated split is real, exactly as the row says.
- **"MEM-03: unsigned 11-bit field, 0…2047, zero holes over a 2048/2048 dense sweep":** the raw
  contains **2048** `MEM-03` cases named `ld_range_f0`…`ld_range_f2047`, a **contiguous** range with
  no gaps, **all 2048 with `status: OK`**, and each record's `decoded.byte_offset` equals
  `4096 + 4·f` **for every single f** — a perfectly linear, monotone, hole-free mapping.
- **"signed model refuted exactly at f=1024":** recomputed. f=1023 → word 2047, **f=1024 → word
  2048**, f=1025 → word 2049, f=2047 → word 3071. Under a signed 11-bit reading, f=1024 would wrap
  to a negative offset; instead the sequence continues upward without a discontinuity. **The
  refutation point named in the row is exactly where the data shows it.**

**Verdict: REPRODUCES** — the strongest row in the sample, because its numbers were re-derived from
the append-only raw rather than read back out of its own prose.

### ✅ L157 — EXP-0137, the barycentric anomaly — **REPRODUCES, including its arithmetic**

Extracted from both runs' `04_results.jsonl`:

| variant | `c0` (run01 = run02) |
|---|---|
| `base`, `count3_const`, `count3_vary`, `attach3ctrl` | `0.243489, 0.134766, 0.621745` |
| `pos3`, `pos2`, `posread_noout` | `0.486979, 0.269532, 0.243489` |

All seven variants, both runs, byte-identical, and **the exact values the row quotes.** The row's
two derived claims also check out:

- **"ratio is exactly 2.0"**: `0.486979 / 0.243489 = 2.0000` and `0.269532 / 0.134766 = 2.0000`.
- **"the third derived as 1 − b0 − b1"**: `1 − 0.486979 − 0.269532 = 0.243489`, matching the
  observed third component to all six digits — which is what makes "unnormalized perspective
  numerators with the normalize-by-sum step absent" a derivation rather than a story.

The discriminating control is present and behaves as the row says: `count3_vary` sits in the
*correct* group, so "an rcp exists" is not the condition — the trigger is **reading `[[position]]`**,
including `posread_noout`, which only stores position to a device buffer and never emits it.

**Verdict: REPRODUCES.**

### ✅ L170 — EXP-0122, address wrap is exactly 2^43 — **REPRODUCES, recomputed from raw**

From `raw/m4-20260828-run01/guard.jsonl` (74 guard records; run02 identical in shape):

- `guard_read_p43_exact` carries `params.off_dec = "8796093022208"` — **2^43 exactly** — and
  `record.gated.obs_hex = "a5c0dbf6"`, with `cb_status 4`, `g1_ok`/`g2_ok` true and
  `main_unchanged` true. The same record's `main_after_hex` begins `a5c0dbf6112c4762…`, so the
  observation at offset 2^43 is **the first word of the main buffer** — the wrap lands on `base+0`.
- The full ladder is present and named as the row implies: `p43_minus_4096`, `p43_minus_4`,
  `p43_exact`, `p43_plus_4`, `p43_plus_60`, `p43_plus_64`, `p43x1p5`, `p43x5_plus_4`, `p44`,
  `neg2p43`, each with a read and a store case. **`p43x1p5` rules out a 2^42 period and
  `p43x5_plus_4` rules out anything larger than 2^43** — so "exactly" is earned, not assumed.
- **"OOB reads zero is NOT page-wide":** §2.2 (`H-GUARD2: confirmed`) shows the zero region is
  bounded, and `p43_plus_64` reading `00000000` while `p43_plus_60` reads live data
  (`f9142f4a`, which is at byte 60 of `main_after_hex`) is the boundary in the raw itself.

**Verdict: REPRODUCES.** One nuance worth carrying: `RESULTS.md` §2.3 scopes this to
*addressing-instruction* wraparound in the tested construction, and §7 flags that not every
addressing path was shown to share the period. The row's "Public-API only" is honest but slightly
tighter phrasing would help.

### ⚠ L190 — EXP-0168, `uniform_mov.dst` moved 214 times — **PARTIAL**

**The load-bearing claim reproduces exactly.** `analysis/field_verdicts.json` →
`uniform_mov.dst`: **`moved_total: 214`**, `label: "hardware-run"`, `is_declared_db_field: true`,
three carriers (`REGMOVE/consumer`, `REGMOVE/consumer9`, `REGMOVE/dump`), `dense_ok: true`,
`distinct_bytes: 224`, and cross-run agreement **100.0%** with `disagreements: 0` on every arm.
The row's explanation of *why* EXP-0164 saw zero — EXP-0140 built its read-back as
`device_store(data_reg = D)` where `D` was the swept `dst`, so field and observable co-varied — is
recorded in `RESULTS.md`, and the `r15` finding is carried in the verdict's own
`coverage.undecidable_why` field rather than only in prose.

Also confirmed: **13 fields merged at `hardware-run` are declared `db.json` fields**, and the three
whole-byte names the agent invented (`mov_imm.byte1`, `uniform_mov.form_b2`,
`uniform_mov.opdesc_b3`) all carry `is_declared_db_field: false`, so the merger refuses them by
intent. That matches the row exactly.

**What does not reproduce is the cross-run-agreement summary.** The row says *"cross-run agreement
100.000% on 23 of 24 names and 99.609% on `cvt_f2h.op`"*. Recomputed from the same file:

| field | scoring arm | other arms | aggregate over all arms |
|---|---:|---|---:|
| `cvt_f2h.op` | `CVTF2H/consumed` **99.609%** (1 disagreement / 256) | `CVTF2H/standalone` **99.219%** (2/256) | **99.414%** (3 / 512) |
| `pack_convert.b7` | `PACK/snorm2` **100.000%** (0/256) | `PACK/unorm2` **99.219%**, `PACK/unorm4` **99.219%** | **99.479%** (4 / 768) |

So **22 of 24 names are at 100% on every arm, not 23**, and `pack_convert.b7` is credited
100.000% because it was scored on its single best arm while two of its three arms disagree. The
99.609% figure is real — it is the scoring arm's number, and it is in the file — but it is the
*most favourable* of the two arms for that field.

**Verdict: PARTIAL.** The finding is sound and the row's headline is correct. The summary
statistic is a **best-arm** figure presented as a per-field one, which understates cross-run
disagreement by hiding three arms at 99.219%. This is the same defect class the corpus already
identified for itself — row L176 records the orchestrator withholding EXP-0155 fields precisely
because *"the rollup's single-representative-arm design was hiding real liveness"*. **Suggested
amendment:** *"cross-run agreement 100.000% on 22 of 24 names on every arm; `cvt_f2h.op` and
`pack_convert.b7` each carry one arm below 100% (99.219%, 2 of 256), giving per-field aggregates of
99.414% and 99.479%."*

---

## What the sample says about the other 163 rows

Do not over-read 11 rows. But the pattern in the two failures is specific enough to act on:

1. **Neither failure is a fabricated observation.** Both rows are backed by real, correct
   measurements. What failed is the *scope* the prose put around them — one generalized across a
   parameter it never varied (bit depth), the other summarized across arms by taking the best one.
2. **The corpus already knows how to catch both.** `EXP-M4-07` caught the first by varying bpp;
   the orchestrator caught the second class in `EXP-0155` by re-deriving per carrier. The gap is
   that neither correction propagated back into `PROVENANCE.md`.
3. **The cheapest high-yield follow-up** is therefore not more sampling but a targeted sweep:
   **grep the log for rows that state a formula or a percentage, and check each against the newest
   experiment that touched the same field.** L75 would have been caught by that in one pass.
4. **A mechanical guard is available for one whole class.** Every row that cites a
   `field_verdicts.json` can have its agreement figure recomputed as an aggregate over arms rather
   than trusted from prose — `analysis/sample_rows.py` plus the recomputation used for L190 is the
   template.

## Reproduce this sample

```
python3 experiments/EXP-0176-provenance-chain/analysis/sample_rows.py       # prints the same 10 lines
python3 experiments/EXP-0176-provenance-chain/analysis/table_integrity.py   # the structural defects
```

Per-row checks are the shell/Python one-liners quoted inline above; each reads only committed
artifacts of this repository and touches no device.
