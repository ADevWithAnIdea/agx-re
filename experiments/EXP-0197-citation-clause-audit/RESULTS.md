# EXP-0197 — RESULTS

## 0. Headline

**Twenty-seven of the thirty clauses are FALSE. Three are TRUE. None is unresolved.**
Twenty-six of the twenty-seven false clauses sit on emitter-grade fields (16 `hardware-run`,
10 `isolated-byte-diff`); the twenty-seventh, `stop.reserved`, is `untested` and already
withheld.

`EXP-0196` had verified six of the thirty. All six re-verify as FALSE — but **two of them
need their evidence re-attributed**, because the records `EXP-0196` named do not vary the bits
the row now labels (§4).

**The mechanism is one step larger than `EXP-0196` reported.** `EXP-0196` found a field-name
index that cannot see `field: null` or `__`-prefixed records. The larger cause is **file
format**: `EXP-0189`'s collector reads only `.jsonl` files whose records carry a string
`instr` **and** a string `field`. Re-running that exact admission filter over the 27
originally-cited directories:

| | directories | detail |
|---|---:|---|
| zero records admissible to `EXP-0189`'s collector | **24 of 27** | 14 have a `raw/` tree with no `.jsonl` in it at all (`.txt`, `.log`, `.hex`, per-case `.json`); 3 have no `raw/` at all; 7 have `.jsonl` whose records carry no `instr`/`field` key |
| some records admissible | 3 | `EXP-0161` (24 373), `EXP-0180` (29 180), `EXP-0171` (636 of 72 238 — the other 71 602 carry `field: null`) |

So for 24 of the 27 originals the clause **could not have come out any other way**. It is a
restatement of the collector's input filter, not a measurement of the experiment.
`analysis/collector_blindspot.py`, `work/collector_blindspot.txt`.

**And the repairs removed nothing.** At the repair commit `1f763864`, over all 30 rows:
**0 original citations removed, 28 citations added, 0 labels changed.** The damage is
entirely in the prose — a false statement about where a row's evidence lives, standing next
to, and in nine cases directly contradicting, the row's own `range` string.

---

## 1. The three CLAUSE-TRUE rows

Stated first, because they are what shows the criterion can fail.

### 1.1 `call_indirect._instruction` — one encoding, never varied

Original citation `EXP-0035-function-abi`. Searched: **K1/K2** — the experiment has no
`.jsonl` raw at all. **K3** — no grouping string names the descriptor. **K4** — over all 20
files, contiguous *and* space-separated hex harvesting yields exactly **one** encoding
satisfying `call_indirect`'s match (`byte0 0x0f`, `byte1 0x80`):

> `experiments/EXP-0035-function-abi/raw/fptr_table_and_vft.txt:13`
> `| 4b 03 3b11 190d 380b 5b01 3c09 020b | `**`0f 80 86 02 07 02 80 06`**` | e7...  (0f 80 = INDIRECT CALL leader)`

`analysis/descriptor_scan.py`: 75 blobs, **`distinct_encodings = 1`**. No byte of the
descriptor ever takes a second value. `EXP-0035`'s own `README.md:62` and `RESULTS.md:137`
list the operand bit-decode as an open follow-up "needs an indirect-call splice testbed".
*(Aside: under the current `db.json` those bytes tokenize as `rt_query_traverse2`, an 8-byte
descriptor sharing the `0f`/`80` leader. Either way there is nothing to vary.)*

### 1.2 `spill_frame_marker._instruction` — absent, exactly as the note itself says

Original citations `EXP-M4-14-a18-splice` and `EXP-0041-scratch-helper-abi`. **K1/K2** —
neither has `.jsonl` raw. **K3** — nothing. **K4** — `EXP-M4-14` has no `raw/` at all and its
`splice_results.json` describes `link_save_restore` and `frame_prologue`, never
`spill_frame_marker`; `EXP-0041` yields, over **2 468 unique hex blobs**, exactly one
clean-tokenization hit for `60 ..`, and it is
`experiments/EXP-0041-scratch-helper-abi/analysis/code_census.py:20` — the script's own search
literal, not an observation. (71 `matchfit` hits exist but an 8-bit match fits by chance and
none anchors.) Consistent with the row's own note: *"EXP-0041 found this exact word ABSENT
from all nine retained M4 own mains"*.

### 1.3 `tex_deriv.axis` — the values are named in prose, the instruction is not in the raw

Original citation `EXP-0016-texture-isa`. **K1/K2** — no `.jsonl`. **K3** — nothing. **K4** —
over all 13 files, **zero** windows anywhere have `byte0 == 0x37` (`tex_deriv`'s entire
match), anchored or matchfit; confirmed independently by a regex for a 10-byte `0x37` run,
which returns 0 in `raw/mains.txt`, `raw/field_map.txt`, `raw/hw_validation.txt`, `README.md`
and `RESULTS.md`. The `0x92`/`0x90` axis values appear only as prose at
`EXP-0016/RESULTS.md:85-89`, and that prose attributes both the four instruction instances and
the hardware run to **`EXP-0008`**, not to `EXP-0016`.

---

## 2. The twenty-seven CLAUSE-FALSE rows

Full evidence text per row: `analysis/verdicts.json`. `record_form` grades how the per-value
records are committed; `iso` says whether the field's bits were changed alone.

| row | label | original citation | per-value records found in the original | first record | form |
|---|---|---|---|---|---|
| `call.offset` | isolated-byte-diff | EXP-0035 | **4 distinct 48-bit offsets** (−104, −158, −552, −458) each with a verified target and `OK`; 3 of them also as full committed encodings | `raw/call_offset_verify.txt:5`; encodings at `raw/abi_and_frames.txt:18,19` and `raw/direct_call.txt:10,17` | textlog |
| `device_load.base_slot` | hardware-run | EXP-0083 | **256 per-slot splices, 257 distinct `slot` values**, each with `probe_word` + `witness_ok`; both gated runs | `raw/m4-20260827-run01/04_results.jsonl:1` (`c31_load_slot_0`) | jsonl |
| `device_load.idx_off` | hardware-run | EXP-0082 **and** EXP-0100 | **2 048 distinct values = the complete 11-bit range**, twice: 2 133 records / 2 100 encodings (device space) and 2 454 / 2 443 (threadgroup space); `changed_bytes` {9,10,11} = the field's own span | `EXP-0082/raw/m4-20260828-run01/04_results.jsonl:1`, sweep at `:56–2103`; `EXP-0100/raw/m4-20260828-run01/04_results.jsonl:406–2456` | jsonl |
| `falu_srcmod12b.ctrl` | hardware-run | EXP-0119 **and** EXP-0089 | EXP-0119: two spliced mains differing at **exactly one byte** (main+12, `0x03`→`0x07` = ctrl bit 2 = absolute bit 34), each with `observed`/`oracle`, both runs. EXP-0089: **336-record `CTRL_SWEEP`, 8 distinct ctrl values** ×7 kernels ×3 reps, incl. the `NO_STATUS` GPU hang | `EXP-0119/raw/m4-20260828-run01/01_results.jsonl:35` and `:77`; `EXP-0089/raw/m4-lifecycle-20260828-run01/04_results.jsonl:25`, hang at `:463–465` | jsonl |
| `falu_srcmod12b.opsel` | hardware-run | EXP-0119 | **8 per-value spliced programs**, `work/pilot_run_sm12b_opsel0…7/arch_5a5209636c49_spliced.bin`, differing only at file byte **7354** taking `0x00`…`0x07`; per-value outcomes stated at `RESULTS.md:485` and `:214–227` | `work/pilot_run_sm12b_opsel0/` | **work-pilot + prose** |
| `frag_color_pack.src_present_mask` | hardware-run | EXP-M4-14 | **7 spliced values on 2 pack ops** with per-value pixel outcomes and an illegal-value GPU fault (`0xff` → `CMDBUF_ERROR`) | `splice_results.json`, group `frag`, `resolved[0]` | **root-evidence-json** |
| `frag_color_store.rt_index` | isolated-byte-diff | EXP-0029 | isolated splice `0x00`→`0x02` of byte+5 with the observed pixel and `STATUS OK`; 9 committed encodings over 4 values | `raw/validations.log:146–148`; encodings `raw/out_mrt.frag.hex:1` off 96 | textlog |
| `frag_color_store.src` | isolated-byte-diff | EXP-0029 | **3 distinct byte+3 values across dispatched programs** (0x0, 0x4 blend_read, 0x6 interp_flat); 6 over the whole corpus | `raw/imageblock.frag.hex:1` off 96, `raw/blend_read.frag.hex:1` off 98, `raw/interp_flat.frag.hex:1` off 56 | textlog |
| `fspecial_est.subop` | hardware-run | EXP-0171 | **256 records × 3 carriers × 2 runs = 1 536**, 256 distinct `bytes` **and** 256 distinct subop values per arm | `raw/g17p_20260830_run01/sweep.jsonl:20154` (SYNTH), `:21179`, `:22204` | jsonl |
| `half_alu.dst` | hardware-run | EXP-0180 | **16 records × 2 carriers × 2 gated runs**, arm `DSTNIB`, 16 distinct `bytes` **and** 16 distinct values of byte0 bits 4..7 | `raw/g17p_run02/sweep.jsonl:1` (C_LO) and `:17` (C_HI); run03 `:16704`, `:16720` | jsonl |
| `iadd2.srcA` | hardware-run | EXP-0171 | 256 × 3 carriers × 2 runs = 1 536; 256 distinct bytes and values per arm | `raw/g17p_20260830_run01/sweep.jsonl:23229` | jsonl |
| `ibfe.srcA` | hardware-run | EXP-0171 | 512 (NAT) + 256 (SYNTH) per run × 2 runs; 256 distinct values per arm | `raw/g17p_20260830_run01/sweep.jsonl:33132` | jsonl |
| `icmp_pred.dst_pred` | hardware-run | EXP-0115 | **27 records over 16 distinct `dst_pred` values 0..15 — EXHAUSTIVE**, each with its own splice string and verdict; both gated runs | `raw/m4_20260828_run01.jsonl:191` (`pred_dst0_ifp0`) | jsonl |
| `ilogic.lut_a_z` | hardware-run | EXP-0171 | 1 280 (NAT) + 256 + 256 per run × 2 runs; **8 distinct values of the 3-bit field — exhaustive** | `raw/g17p_20260830_run01/sweep.jsonl:770` | jsonl |
| `ilogic.outmod` | hardware-run | EXP-0171 | 1 280 (NAT, 1 280 distinct bytes) + 256 + 256 per run × 2 runs; 256 distinct outmod values | `raw/g17p_20260830_run01/sweep.jsonl:1282` | jsonl |
| `iter.mode` | isolated-byte-diff | EXP-0029 | **3 distinct byte+6 values across dispatched programs** (0x0 interp_noperspective, 0x3 interp_centroid + interp_sample, 0x4 interp_smooth + persp_smooth), each with a 4×4 pixel dump; 4 over the corpus | `raw/interp_noperspective.frag.hex:1` off 0 (`2f0d5400030000021000`), `raw/interp_centroid.frag.hex:1` off 16 (`2f055400030003020900`), `raw/interp_smooth.frag.hex:1` off 0 (`2f0d5400030004021000`); dispatches `raw/validations.log:21–96` | textlog |
| `iter.src_slot` | isolated-byte-diff | EXP-0029 | isolated splice `0x00`→`0x02` with **baseline and spliced corner dumps**; 5 distinct values across dispatched programs | `raw/validations.log:112–122`; encodings `raw/interp_centroid.frag.hex:1` off 16/36/46/56/74 | textlog |
| `mov_zext16.src_reg` | hardware-run | EXP-0161 | **257 records × 2 carriers × 2 gated runs, 256 distinct `bytes`, 16 distinct values of byte0 bits 4..7** | `raw/g17p_20260829_run01/sweep.jsonl:3111` (SYNTH) and `:4011` (INPLACE) | jsonl |
| `simd_shuffle.lane` | hardware-run | EXP-0115 | **60 records over 42 distinct `lane_raw` values** (0..6, 8, 10, 14, 30, 60…128, 140…255), both gated runs | `raw/m4_20260828_run01.jsonl:218` (`sshuf_raw_000`) | jsonl |
| `simd_shuffle.mode` | isolated-byte-diff | EXP-0018 | **6 distinct byte+1 values over 31 distinct encodings**, each contributing kernel carrying a `[PASS]` | `raw/mains.txt:2` (0x04), `:32` (0x05), `:34` (0x06), `:37` (0x00), `:57` (0x01), `:20` (0x14); `raw/hwval.txt` | textlog |
| `stop.reserved` | untested | EXP-0003 | the trailing word spliced to `ffffffff` (reserved = `0xffffff`) with `GPUTIME_NS 8041 / STATUS OK / RESULT` matching; baseline `0x000000` dispatched throughout | `raw/fault2_stop_ff.log`, `raw/fault1_stop_zeroed.log`; tabulated `RESULTS.md:92–93` | textlog |
| `tex_sample.result_desc` | isolated-byte-diff | EXP-0034 | **7 distinct companion+3 values over 27 encodings**; 4 of them with a per-value gather observation | `raw/mains.txt:3` (0xa4), `:5` (0xac), `:6` (0xb4), `:7` (0xbc); `raw/hw_validation.txt` §4 | textlog |
| `tex_sample.samp_slot_offset` | isolated-byte-diff | EXP-0016 **and** EXP-0034 | EXP-0016: isolated splice `0x01`→`0x00` with a before/after 8×8 dump, "55 / 64 pixels changed". EXP-0034: **5 distinct values**. EXP-0106: 12 per-case gather-offset records + a dynamic case | `EXP-0016/raw/hw_validation.txt` §4, encodings `raw/mains.txt:2,9`; `EXP-0034/raw/mains.txt:8,9,10,11` | textlog |
| `tex_sample.tex_slot` | hardware-run | EXP-0114 **and** EXP-0016 | EXP-0114: **16 per-value splices of one byte (`case_tex_nibble_0..f`) + 12 low-nibble cases**, each with its own `out_word_hex`, in two non-quarantined runs. EXP-0016: 4 distinct values + a slot splice with pixel readback | `EXP-0114/raw/m4-20260828f-run01/case_tex_nibble_*.json`; `EXP-0016/raw/hw_validation.txt` §3 | **per-case json** |
| `tex_sample.variant` | hardware-run | EXP-0016, EXP-0034 **and** EXP-M4-10 | **10, 12 and 8 distinct values respectively**; EXP-M4-10's eight are each "HW-confirmed by correct read + dim-splice break" | `EXP-0016/raw/mains.txt:2,3,4,5,13,27,28,29,31,37`; `EXP-0034/raw/mains.txt:2,3,8,11,12,14,15,16,20,21,22,23`; `EXP-M4-10/isa6-texcoord/logs/EVIDENCE.txt:8–16` | textlog |
| `vary_store.out_slot` | isolated-byte-diff | EXP-0037 | **3 isolated byte+4 splices** with observed corner pixels (`0x80→0x00`, `0x80→0xa0`, `0xc0→0x80`) + 2 position-store cases; **all 8 slot values** in the committed mains | `raw/hw_validations.txt` PART 1; `raw/vertex_mains.txt:7` offsets 156/164/206/214/222/230/238/246 | textlog |
| `vary_store.src` | isolated-byte-diff | EXP-0037 | **2 isolated byte+3 splices** with observed pixels (`0x08→0x00`, `0x08→0x0c`) + a position-source case; 8 values in the mains | `raw/hw_validations.txt` PART 1; `raw/vertex_mains.txt:7` | textlog |

### 2.1 Nine rows whose `note` contradicts their own `range`

On these the clause does not merely mis-state a fact — it contradicts a sentence in the same
JSON object, which is what makes them checkable without hardware:

* `device_load.base_slot` — `range`: *"0x00..0xFF EXHAUSTIVE: slots 1..30 return their own
  distinct bound buffer, slot 0 is anomalous, 31..127 read 0x00000000, 128..255 mirror
  0..127"* = EXP-0083's 256-case census, verifiable line by line in `04_results.jsonl`.
* `device_load.idx_off` — `range`: *"0..2047 FULL DENSE sweep (device space) **and** a second
  full 0..2047 dense sweep in threadgroup space"* = EXP-0082 + EXP-0100, the two experiments
  the clause calls empty.
* `falu_srcmod12b.ctrl` — `range` names *"the SAME bit inside a loop produced a genuine GPU
  HANG in EXP-0089"*, the experiment the clause calls empty.
* `falu_srcmod12b.opsel` — `range`: *"opsel_mod 0..7 exhaustive"* = EXP-0119's pilot table.
* `frag_color_pack.src_present_mask` — `range` lists the exact seven values EXP-M4-14 spliced.
* `half_alu.dst` — the note's own preceding sentence sources its 16-of-16 figure to *"the
  DSTNIB arm"*, i.e. to EXP-0180; the appended clause then says EXP-0180 has no records.
  `EXP-0189`'s own `RESULTS.md` §4 R1 says the same thing a third time: *"EXP-0180 records the
  ONLY sweep of `half_alu_ext8.dst` … under `field: "__dst_nibble"`"*.
* `icmp_pred.dst_pred` — `range`: *"0..15 EXHAUSTIVE"* = EXP-0115's 16-value CF-05 arm.
* `simd_shuffle.lane` — `range`: *"28 swept points in the dynamic form and **60** independently
  constructed raw-byte splices in the static form"*: the 60 is EXP-0115's `SIMD-03-static`
  record count and the 28 is EXP-0104's `SIMD-03` count — both named originals.
* `tex_sample.tex_slot` — `range`: *"upper nibble 0x0..0xF EXHAUSTIVE (16/16) plus 12
  representative low-nibble values at both populated slots"* = EXP-0114's
  `case_tex_nibble_0..f` + `case_tex_lownib_slot{0,1}_*`, exactly 16 + 12 files.

---

## 3. Did the repair point at a WORSE source?

**No — because it pointed *away* from nothing.** At the repair commit `1f763864`, across all
30 rows: **0 original citations removed, 28 added, 0 labels changed**
(`analysis/worse_source.py`, axis A). Every original is still in its `evidence` list. The
union of sources is therefore never weaker than before; what is wrong is the prose that tells
a future reader the original is stale and empty.

**The label survives on the original citation alone in 25 of the 27.** Column D of
`analysis/worse_source.json`:

| outcome | rows |
|---|---|
| current label **SUSTAINED** on the original alone | 20 |
| sustained with a stated qualifier (`THIN`, `WEAK`, `PARTIAL`, `FOR-THE-FAMILY`, `CHAIN-BROKEN`) | 5 |
| **DOWNGRADE** | 1 — `falu_srcmod12b.opsel` |
| n/a (already `untested` and withheld) | 1 — `stop.reserved` (counted in the 27) |

`falu_srcmod12b.opsel` is the only row where the original alone does not carry
`hardware-run`: its 0..7 exhaustive sweep is committed as **eight spliced program binaries
with no committed output**, and the per-value outcomes exist only as EXP-0119 prose. On
committed observation artifacts alone it reaches `isolated-byte-diff`, not `hardware-run`.
*(This is a statement about the original citation, not a proposed relabel — the row also cites
`EXP-0138-m4-emit-falu`, which holds 21 named `opsel` records over 7 distinct values.)*

**Two places where the repaired source is arguably the weaker one:**

1. **Target.** For four rows **no** repaired-to experiment is on the row's declared `target`:
   `half_alu.dst` (target G17P → `EXP-0138-m4-emit-falu`), `mov_zext16.src_reg` (target G17P →
   `EXP-0146-m4-emit-int-misc`), `simd_shuffle.lane` (target M4 → `EXP-0163`/`EXP-0172`, both
   G17P), `tex_sample.tex_slot` (target M4 → `EXP-0172`, G17P). In each case the *original*
   the clause calls empty **is** on the row's target. Since nothing was removed this costs
   nothing today; it would cost a row its target attribution the moment anyone acted on the
   clause and dropped the original.
2. **Coverage.** Every repaired-to source does carry per-value records varying the same
   `db.json` bits (`analysis/positive_half.py` — checked under all four keyings, unlike
   `EXP-0196` which could report nothing for 15 of 28). Two are *thinner* than the original
   they displace in the prose: `EXP-0138`'s `half_alu.dst` evidence is **16 records × 3 runs**
   under `field: "_byte0_hi"` versus EXP-0180's 16 × 2 carriers × 3 runs; `EXP-0172`'s
   `tex_sample.tex_slot` evidence is 1 174 encodings over **4** distinct values versus
   EXP-0114's **16/16 exhaustive nibble sweep + 12 low-nibble cases**.

---

## 4. Two falsifiers inside the FALSE bucket — both fired

A byte-span sweep is only a per-*value* record of a field if the hardware saw distinct
encodings **of that field's bits**. `analysis/distinct_bytes.py` separates `value` (the
harness's intent), `bytes` (what ran) and the field's own bit values. It changed two answers:

### 4.1 `mov_zext16.src_reg` — `EXP-0196`'s named records do not test this field

`EXP-0196` reported *"896 records over 128 distinct values across five runs keyed exactly
`instr=mov_zext16, field=src_reg`"*. Those 896 records exist (128 per arm × 7 runs, first at
`EXP-0161/raw/g17p_20260829_run01/sweep.jsonl:3371`) and have 128 distinct `bytes` — **but
they carry `fstart: 8, fwidth: 7`**, i.e. they sweep `EXP-0161`'s *old* byte+1 `src_reg`, and
they hold `db.json`'s **current** `src_reg` (byte0 bits 4..7, after DEF-0161-2) at a **single
value**:

```
run01  SYNTH+LIFTED|B_ZEXT_SYNTH   field=src_reg   n=128  bytes=128  field-bit values = 1
run01  SYNTH+LIFTED|B_ZEXT_SYNTH   field=__falsifier_byte0  n=257  bytes=256  field-bit values = 16
```

The clause is still FALSE — but on the `__falsifier_byte0` records
(`:3111` and `:4011`, repeated at `:7033`/`:7933` in run02, 16/16 nibble values with outcomes
`{ok, fault, silent_zero, wrong_value}`), **not** on the named ones. `EXP-0196` flagged the
byte+1/byte0 distinction in a sub-note; the distinct-bytes test turns it into a hard
correction of which records carry this row.

### 4.2 `half_alu.dst` — the named `dst` sweep does not test this field either

`EXP-0180` keys 2 048 records `instr=half_alu_fma12, field=dst`. They have 256 distinct
`bytes` and **one** distinct value of byte0 bits 4..7. Only the 32 `DSTNIB` records per run
(`field: "__dst_nibble"`) vary the field: 16 distinct bytes, 16 distinct field values.

### 4.3 `ilogic.lut_a_z` — 8 values, not 256

The byte+4 sweep has 256 distinct `bytes`, but `lut_a_z` is bits 37..39. It produces **8
distinct field values — exhaustive for a 3-bit field**, not the 256 that the byte-level
framing implies. Records exist either way; the count carried over from the byte is wrong.

### 4.4 Where a FALSE verdict is weakest

Three rows are FALSE only on non-`raw/` artifacts, and are flagged as such rather than folded
into the headline:

* `falu_srcmod12b.opsel` — `work/` pilot binaries + `RESULTS.md` prose; **zero** gated-raw
  variation of the field.
* `frag_color_pack.src_present_mask` — one narrative string inside `splice_results.json`;
  `EXP-M4-14` has no `raw/` tree at all, and `EXP-0189` §5 is right that this is a CODEX §6
  chain break. It is not the same thing as the records not existing.
* `stop.reserved` — both committed cases overwrite **byte0 as well**, so under the `stop`
  descriptor's own match (`byte0 == 0x0e`) neither spliced word is a `stop`, and neither
  isolates `reserved`. The row's `range` ("the full 24-bit body corrupted") overstates what
  was isolated. The row is `untested` and already withheld, so nothing rests on it.

---

## 5. Cross-check: what `EXP-0196` got right and what changed

| | EXP-0196 | EXP-0197 |
|---|---|---|
| clauses examined | 28 matched its regex; its `(instr, field)` + byte-span pass read `.jsonl` only, and its own §5.2 disclaims the SUPPORTED side as an instrument artefact — so **6 were actually established** | 30 of 30, four keyings, every file format |
| verdicts | 6 FALSE, 22 reported SUPPORTED but disclaimed | the same 6 FALSE, **+21 more FALSE**, 3 TRUE |
| stated mechanism | field-name index blind to `field: null` and `__`-prefixed records | that, **plus** the `.jsonl`-only and `instr`/`field`-must-be-`str` gates, which account for **24 of 27** originals |
| `mov_zext16.src_reg` evidence | the 896 `field=src_reg` records | those records do not vary this field; the `__falsifier_byte0` records do (§4.1) |
| `ilogic.lut_a_z` | "1 792 records, 256 distinct values" | 256 distinct *bytes*, **8** distinct *field* values (§4.3) |
| positive half ("the records live in X") | could report nothing for 15 of 28 | all 28 verified: every repaired-to source does carry records varying the same bits |

---

## 6. How this method could have failed to say "no"

Stated so the next reader can attack it. Two of these fired during the audit.

1. **My first hex harvester could not see space-separated dumps, and produced a false zero.**
   `call_indirect` returned `K4 = 0` over `EXP-0035` purely because
   `raw/fptr_table_and_vft.txt:13` writes the encoding as `0f 80 86 02 07 02 80 06`. Had I
   stopped there I would have published a CLAUSE-TRUE that was an artefact of my own regex —
   the same defect class I was auditing. `analysis/scan.py:spaced_runs` fixes it; the
   pre-fix log is kept at `work/scan_log.txt` next to the post-fix `work/scan_log2.txt` as the
   negative control.
2. **`K3` (grouping strings) is nearly worthless and nearly cost two rows.** It looks only at
   a fixed key list, and `EXP-0115` keys its sweeps `case_id: "sshuf_raw_000"` /
   `locate_target: "static_shuffle_lane"` inside a nested `case_params` object — so K3 scored
   0 for `simd_shuffle.lane` and `icmp_pred.dst_pred`, two of the strongest FALSE rows in the
   table. Both were found by reading the file, not by the instrument. **Any row I called TRUE
   could in principle be hiding a per-case sweep under a key I did not enumerate**; for the
   three TRUE rows I mitigated this by falling back to K4, which is key-agnostic, and by
   reading the experiment's own RESULTS text — but that is a mitigation, not a proof.
3. **`MATCHFIT` is not evidence and I did not let it be.** An 8-bit `match` fits by chance:
   `spill_frame_marker` scored 71 "distinct encodings" in `EXP-0041` under matchfit and **1**
   under clean tokenization, and that one was a literal inside a `.py` file. Every CLAUSE-FALSE
   verdict in §2 rests on anchored tokenization, an explicit splice record, or a per-case
   parameter — never on matchfit alone.
4. **"An observation exists" is not "the observation isolates the field."** For nine rows the
   per-value records come from *different compiled programs*, not splices
   (`frag_color_store.src`, `iter.mode`, `tex_sample.*`, `simd_shuffle.mode`, `call.offset`).
   Those establish that the field's bits varied and that each variant ran — which is what the
   clause denies — but they are `OWN-SHADER-DIFF` strength, and several of the rows' `range`
   strings say "splice-proven" where the original citation shows no splice. Recorded in the
   `isolation` column; not adjudicated here.
5. **The line between "a committed record" and "the experiment's own prose" is mine, and it is
   soft.** `EXP-M4-14`'s per-value pixel outcomes live in one JSON string; `EXP-0119`'s live in
   a Markdown table. I counted both as records because both pair a specific field value with a
   specific observed result in a committed artifact, and flagged both as the weakest form. A
   reader who requires an append-only `raw/` observation should move
   `falu_srcmod12b.opsel` (and arguably `frag_color_pack.src_present_mask`) to TRUE, giving
   25 FALSE / 5 TRUE. **The bucket counts are sensitive to that choice and to nothing else.**
6. **I checked clauses against raw, not raw against reality.** Where an experiment's own log
   says `STATUS OK` I take it as an observation. If a harness mis-recorded an outcome, this
   audit reproduces the error and calls it a record.
7. **`half_alu.dst` is genuinely contested and I resolved it one way.** `EXP-0180` has **zero**
   records carrying `instr: "half_alu"` — only the 8- and 12-byte sibling mnemonics — and zero
   6-byte `bytes` columns. Under "records keyed to this db mnemonic" the clause is TRUE; under
   "records that dispatch values of this field's bits" it is FALSE. I chose the second because
   it is the reading the row's own note uses one sentence earlier. A reader who prefers the
   first should move this row to TRUE, giving 26 FALSE / 4 TRUE.
8. **Coverage inside a directory is not proven complete.** `analysis/scan.py` walks every file
   but skips `.gz`, binaries, and strings longer than 64 KB except for embedded runs. No
   originally-cited directory contains a `.gz` raw file, so nothing was skipped here — but the
   instrument would not tell me if one did.

---

## 7. Files

`analysis/verdicts.json` / `.tsv` — the 30 verdicts with full per-row evidence text.
`analysis/worse_source.json` — the four-axis repair comparison.
`work/scan_summary.json`, `work/scan_<row>.json` — K1–K4 per row per original citation.
`work/distinct_bytes.{json,txt}` — the distinct-encodings falsifier.
`work/collector_blindspot.{json,txt}` — `EXP-0189`'s admission filter, re-run over all 27 originals.
`work/positive_half.json` — the repaired citations, checked under the same four keyings.
`work/scan_log.txt` (pre-fix) and `work/scan_log2.txt` (post-fix) — the §6.1 negative control.

**Nothing in `tools/agx-isa/`, `docs/`, or `PROVENANCE.md` was modified. No label was
changed. Nothing was committed.**
