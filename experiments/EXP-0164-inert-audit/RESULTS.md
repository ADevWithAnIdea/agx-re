# RESULTS — EXP-0164: how much of the emitter-grade corpus survives an adversarial re-derivation

**Analysis only — no device was contacted.** Every number below is re-derived from
`experiments/*/raw/**` by `analysis/collect_raw.py` + `analysis/audit.py`, against a
hashed snapshot of `validation.json`, and never from an experiment's own verdict JSON.

```
Clean-room provenance: re-analysis of committed OWN-SHADER / HW-PROBE evidence
Inputs inspected: tools/agx-isa/{validation,db}.json; experiments/*/raw/**;
                  experiments/*/RESULTS.md + analysis/ (for schema only)
Apple binary introspection: NONE
Reproduction: python3 analysis/collect_raw.py && python3 analysis/audit.py
              python3 analysis/tables.py > work/tables_all.md
Evidence: work/validation.snapshot.json c40195cd9f65d9176c5bc518ede1c171cf3904c26ba81f7b93dc2414b1ad7091
          work/db.snapshot.json         83b83a350ece33b8fd9e98b773f02be2da89a5f942824896574ff22827042341
          repo revision b7dedbf0ce37c0a95823923bc70f3cab0f733b3c
Frozen contract: PRE_REGISTRATION.md (+ amendments A1-A5, each dated before verdicts)
```

---

## 0. Two corrections to the question as asked

1. **The number is not 659, it is 664.** `validation.json` is under concurrent edit; it
   read `hardware-run: 548` at the start of this session and `553` twenty minutes later.
   Everything here is against a pinned snapshot at revision `b7dedbf0`: **664
   emitter-grade fields (553 `hardware-run` + 111 `isolated-byte-diff`) over 67 / 166
   emitter-relevant instructions.** An audit against a moving file is not reproducible.
2. **"66/166" is now 67/166** in that snapshot (EXP-0161's `carry_gen` landed).
   My reimplementation of `validate_labels.py`'s emittable rule reproduces **67**
   exactly with nothing withheld, which is the first check that the recomputation below
   is measuring the same thing the published metric measures.

---

## 1. Verdict

**The 659/664 is not basically sound, and it is also not mostly rotten. It splits
almost exactly in half.**

| | |
|---|---|
| emitter-grade fields audited | **664** |
| supported by movement that reproduces across two gated runs (`STABLE-LIVE`) | **359 (54.1%)** |
| the suspect class — never moved anything, exactly ONE carrier (`INERT-SINGLE`) | **81 (12.2%)** |
| movement that does not reproduce (`UNSTABLE`) | **41 (6.2%)** |
| cannot be re-derived from `raw/` at all (`UNVERIFIABLE`) | **144 (21.7%)** |
| never moved but ≥ 2 carriers (`INERT-MULTI`, defensible within a stated envelope) | **23 (3.5%)** |
| only one gated run exists (`SINGLE-RUN`) | **16 (2.4%)** |

**Emittability, honestly:** the published **67 / 166** becomes **43 / 166** if only the
suspect `INERT-SINGLE` class is withheld, **33 / 166** if non-reproducing movement goes
too, and **16 / 166** under the full withhold the dispatch asked me to price. Fifty-one
of the 67 currently-emittable instructions depend on at least one field in a withheld
bucket.

Three findings drive that, in descending order of how much they should worry you:

- **H3 is false, and it is the biggest single block.** 144 fields (21.7%) have no
  per-value raw record that can be attributed to them. 49 of those cite only
  **EXP-M4-14**, whose evidence is a narrative `splice_results.json` at the experiment
  root with no `raw/` tree and no per-case records at all. Another ~60 cite the
  pre-EXP-0138 waves (`EXP-0006/0016/0029/0090/0092/0099/0101/0105/0112/0113/0119`,
  `EXP-O2C/O2D`, `RT-*`), whose raw is keyed by *case name*, not by field. **The
  `falu2` descriptor — the most heavily cited instruction in the whole DB — has 13 of
  its 15 withheld fields in this class.**
- **H1 is confirmed.** 81 fields (12.2%) were promoted from a sweep that never moved
  any observable, on exactly one carrier. Hand-checked example: `atomic_rmw.amode`,
  256/256 values dispatched in both gated runs of EXP-0141, **one** distinct read-back
  across all 512 cases, one carrier (`atdev`). An emitter told "don't care" here has
  been told that by a probe that could not have seen a difference.
- **H2 is confirmed, and it is not confined to EXP-0155.** Eleven merged fields have,
  inside one experiment's own raw, an arm that is fully inert next to an arm that is
  stably live. Six of them are outside EXP-0155: `device_store.addr_mode` (EXP-0141),
  `ibitcount.cache` (EXP-0139), `mov_imm.dst` and `sel.b1` (EXP-0140),
  `jump_cond.offset` (EXP-0156).

**What is NOT wrong.** The G17P texture/fragment wave (EXP-0155) comes out of this with
**zero** `INERT-SINGLE` — the orchestrator's merge policy already removed them, and my
pipeline independently reproduces all 15 of its withheld fields *with the same reasons*
(control C1). The method works; it just has not been applied to the ten earlier waves.

---

## 2. What was directly OBSERVED

### 2.1 The census

### T1 — bucket census (664 emitter-grade fields)

| bucket | fields | share |
|---|---:|---:|
| `STABLE-LIVE` | 359 | 54.1% |
| `INERT-MULTI` | 23 | 3.5% |
| `INERT-SINGLE` | 81 | 12.2% |
| `UNSTABLE` | 41 | 6.2% |
| `SINGLE-RUN` | 16 | 2.4% |
| `UNVERIFIABLE` | 144 | 21.7% |
| **total** | **664** | |

`UNVERIFIABLE` by reason: `field-named-but-unstructured` 24, `no-field-records` 60, `no-raw` 47, `raw-present-but-unattributable` 13

### 2.2 Where it comes from, per experiment


| experiment | cited by | STABLE | I-MULTI | I-SINGLE | UNSTABLE | 1-RUN | UNVER | raw verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `EXP-0154` | 98 | 72 | 2 | 20 | 4 | 0 | 0 | per-value records parsed and bit-attributed |
| `EXP-0155` | 90 | 73 | 10 | 0 | 7 | 0 | 0 | per-value records parsed and bit-attributed |
| `EXP-0139` | 61 | 43 | 2 | 7 | 9 | 0 | 0 | per-value records parsed and bit-attributed |
| `EXP-0141` | 56 | 35 | 3 | 15 | 3 | 0 | 0 | per-value records parsed and bit-attributed |
| `EXP-M4-14` | 49 | 0 | 0 | 0 | 0 | 0 | 49 | no raw files |
| `EXP-0138` | 46 | 34 | 0 | 10 | 2 | 0 | 0 | per-value records parsed and bit-attributed |
| `EXP-0156` | 44 | 31 | 3 | 8 | 2 | 0 | 0 | per-value records parsed and bit-attributed |
| `EXP-0144` | 42 | 28 | 1 | 2 | 11 | 0 | 0 | per-value records parsed and bit-attributed |
| `EXP-0140` | 39 | 13 | 1 | 5 | 0 | 0 | 20 | per-value records parsed and bit-attributed |
| `EXP-0147` | 31 | 16 | 1 | 11 | 3 | 0 | 0 | per-value records parsed and bit-attributed |
| `EXP-0162` | 18 | 0 | 0 | 2 | 0 | 16 | 0 | per-value records parsed and bit-attributed |
| `EXP-0119` | 10 | 0 | 0 | 0 | 0 | 0 | 10 | raw present, NO per-value field records |
| `EXP-0112` | 10 | 0 | 0 | 0 | 0 | 0 | 10 | raw present, NO per-value field records |
| `EXP-O2C` | 10 | 0 | 0 | 0 | 0 | 0 | 10 | raw present, NO per-value field records |
| `EXP-0161` | 9 | 9 | 0 | 0 | 0 | 0 | 0 | per-value records parsed and bit-attributed |
| `EXP-0090` | 8 | 0 | 0 | 0 | 0 | 0 | 8 | raw present, NO per-value field records |
| `EXP-0153` | 7 | 5 | 0 | 1 | 0 | 0 | 1 | per-value records parsed and bit-attributed |
| `EXP-0105` | 7 | 0 | 0 | 0 | 0 | 0 | 7 | raw present, NO per-value field records |
| `EXP-0006` | 7 | 0 | 0 | 0 | 0 | 0 | 7 | raw present, NO per-value field records |
| `EXP-0099` | 6 | 0 | 0 | 0 | 0 | 0 | 6 | raw present, NO per-value field records |
| `EXP-O2D` | 5 | 0 | 0 | 0 | 0 | 0 | 5 | raw present, NO per-value field records |
| `EXP-0113` | 5 | 0 | 0 | 0 | 0 | 0 | 5 | raw present, NO per-value field records |
| `EXP-0016` | 5 | 0 | 0 | 0 | 0 | 0 | 5 | raw present, NO per-value field records |
| `EXP-0092` | 4 | 0 | 0 | 0 | 0 | 0 | 4 | raw present, NO per-value field records |
| `EXP-0029` | 4 | 0 | 0 | 0 | 0 | 0 | 4 | raw present, NO per-value field records |
| `EXP-0115` | 4 | 0 | 0 | 0 | 0 | 0 | 4 | raw present, NO per-value field records |
| `RT-10-isa-pass2` | 4 | 0 | 0 | 0 | 0 | 0 | 4 | raw present, NO per-value field records |
| `EXP-0018` | 4 | 0 | 0 | 0 | 0 | 0 | 4 | raw present, NO per-value field records |
| `EXP-0010` | 3 | 0 | 0 | 0 | 0 | 0 | 3 | raw present, NO per-value field records |
| `RT-1a-FIX` | 3 | 0 | 0 | 0 | 0 | 0 | 3 | raw present, NO per-value field records |
| `RT-ISA-FIX` | 3 | 0 | 0 | 0 | 0 | 0 | 3 | raw present, NO per-value field records |
| `EXP-0034` | 3 | 0 | 0 | 0 | 0 | 0 | 3 | raw present, NO per-value field records |

Read the two blocks separately. Every experiment from **EXP-0138 onward** writes
per-value JSONL under `raw/<run>/sweep.jsonl` and is fully re-derivable; every
experiment **before** it is not, and that boundary — not the quality of the physics —
is what produces the 144.

### 2.3 The recomputed emittability ladder


| withholding policy | fields withheld | emittable | of 166 |
|---|---:|---:|---:|
| published `validation.json` | 0 | 67 | 40.4% |
| `inert_single_only` | 81 | 43 | 25.9% |
| `inert_single_plus_unstable` | 122 | 33 | 19.9% |
| `chain_broken_only` | 195 | 22 | 13.3% |
| `lenient` | 242 | 17 | 10.2% |
| `strict` | 266 | 16 | 9.6% |

Definitions: `inert_single_only` withholds only the suspect class; `chain_broken_only`
withholds `INERT-SINGLE` + `UNSTABLE` + the `UNVERIFIABLE` fields whose own experiment
*has* a raw tree that simply does not record them (i.e. it forgives EXP-M4-14, whose
evidence is committed but unstructured); `lenient` is `strict` minus the fields whose
name at least appears in raw text; `strict` is the full withhold the dispatch priced.

**The number I would defend in public is `inert_single_only` = 43 / 166**, because it
withholds exactly what the user's challenge identified and nothing else. `strict` = 16
is the correct answer to "what survives if a reviewer must be able to reproduce every
promotion from raw", and it is worth stating precisely because it is uncomfortable.

---

## 3. The ranked tables the dispatch asked for

### T4 — instructions that lose emittable status under the strict set

| instruction | withheld fields | buckets | citing experiments |
|---|---:|---|---|
| `atomic_mem` | 1 | UNSTABLE 1 | `EXP-0141` |
| `copysign` | 1 | INERT-SINGLE 1 | `EXP-0138` |
| `cvt_f2h` | 1 | UNSTABLE 1 | `EXP-0144` |
| `falu_acc` | 1 | INERT-SINGLE 1 | `EXP-0154` |
| `if_push` | 1 | INERT-SINGLE 1 | `EXP-0140` |
| `iter_at` | 1 | UNSTABLE 1 | `EXP-0155` |
| `mov_imm` | 1 | UNVERIFIABLE 1 | `EXP-0153` |
| `pack_convert` | 1 | UNSTABLE 1 | `EXP-0144` |
| `pixel_order` | 1 | UNVERIFIABLE 1 | `EXP-0093` |
| `shift_amt_move` | 1 | INERT-SINGLE 1 | `EXP-0154` |
| `stop` | 1 | UNVERIFIABLE 1 | `EXP-0003`, `EXP-0010` |
| `uniform_mov` | 1 | INERT-SINGLE 1 | `EXP-0140` |
| `cvt_f2i` | 2 | INERT-SINGLE 1, UNSTABLE 1 | `EXP-0144` |
| `cvt_i2f_src` | 2 | INERT-SINGLE 1, UNSTABLE 1 | `EXP-0144` |
| `frag_color_store` | 2 | UNVERIFIABLE 2 | `EXP-0029` |
| `imageblock_store` | 2 | UNSTABLE 1, UNVERIFIABLE 1 | `EXP-0155`, `EXP-O2D` |
| `ishift` | 2 | INERT-SINGLE 1, UNSTABLE 1 | `EXP-0139` |
| `iter` | 2 | UNVERIFIABLE 2 | `EXP-0029` |
| `iunary` | 2 | UNVERIFIABLE 2 | `EXP-M4-14` |
| `jump_cond` | 2 | INERT-SINGLE 2 | `EXP-0156` |
| `n3_sample_read` | 2 | INERT-SINGLE 2 | `EXP-0147` |
| `simd_reduce` | 2 | UNVERIFIABLE 2 | `EXP-0018`, `EXP-O2D`, `RT-ISA-FIX` |
| `tex_deriv` | 2 | UNSTABLE 1, UNVERIFIABLE 1 | `EXP-0016`, `EXP-0155` |
| `vtx_out_pos` | 2 | INERT-SINGLE 2 | `EXP-0147` |
| `frame_prologue` | 3 | UNVERIFIABLE 3 | `EXP-M4-14` |
| `ibfe` | 3 | INERT-SINGLE 3 | `EXP-0154` |
| `jump` | 3 | INERT-SINGLE 2, UNVERIFIABLE 1 | `EXP-0010`, `EXP-0115`, `EXP-0140`, `EXP-0156` |
| `spill_frame_marker` | 3 | UNVERIFIABLE 3 | `EXP-M4-14` |
| `tile_read_mrt` | 3 | INERT-SINGLE 2, UNSTABLE 1 | `EXP-0147` |
| `atomic_tg` | 4 | INERT-SINGLE 2, UNSTABLE 2 | `EXP-0141`, `EXP-0156` |
| `frag_color_pack` | 4 | UNSTABLE 1, UNVERIFIABLE 3 | `EXP-0155`, `EXP-M4-14` |
| `get_sr` | 4 | INERT-SINGLE 1, UNVERIFIABLE 3 | `EXP-0031`, `EXP-0092`, `EXP-0140`, `EXP-M4-14` |
| `half_alu` | 4 | UNVERIFIABLE 4 | `EXP-0033`, `EXP-M4-14` |
| `ibitcount` | 4 | UNSTABLE 1, UNVERIFIABLE 3 | `EXP-0129`, `EXP-0139`, `EXP-M4-14` |
| `reg_move_c1` | 4 | UNVERIFIABLE 4 | `EXP-0101`, `EXP-0113`, `EXP-0140` |
| `reg_move_cb` | 4 | UNVERIFIABLE 4 | `EXP-0140` |
| `threadgroup_barrier` | 4 | INERT-SINGLE 2, UNSTABLE 2 | `EXP-0141` |
| `reg_move_c0` | 5 | UNVERIFIABLE 5 | `EXP-0101`, `EXP-0113`, `EXP-0140` |
| `reg_move_c2var` | 5 | UNVERIFIABLE 5 | `EXP-0140` |
| `reg_move_c9` | 5 | UNVERIFIABLE 5 | `EXP-0113`, `EXP-0140` |
| `tile_read` | 5 | INERT-SINGLE 3, UNSTABLE 2 | `EXP-0147` |
| `atomic_rmw` | 6 | INERT-SINGLE 6 | `EXP-0141`, `EXP-0156` |
| `device_load` | 6 | INERT-SINGLE 4, UNVERIFIABLE 2 | `EXP-0010`, `EXP-0082`, `EXP-0083`, `EXP-0100`, `EXP-0141` |
| `device_store` | 6 | INERT-SINGLE 3, UNVERIFIABLE 3 | `EXP-0082`, `EXP-0083`, `EXP-0092`, `EXP-0100`, `EXP-0141` |
| `link_save_restore` | 6 | UNVERIFIABLE 6 | `EXP-M4-14` |
| `iadd2` | 7 | INERT-SINGLE 3, UNSTABLE 4 | `EXP-0139`, `EXP-0153` |
| `unpack_convert` | 7 | UNSTABLE 7 | `EXP-0144` |
| `half_alu_ext8` | 9 | INERT-SINGLE 2, UNVERIFIABLE 7 | `EXP-0138`, `EXP-M4-14` |
| `tex_addr_setup` | 11 | UNVERIFIABLE 11 | `EXP-M4-14` |
| `matrix_mac` | 12 | INERT-SINGLE 2, UNVERIFIABLE 10 | `EXP-0147`, `EXP-O2C`, `RT-10-isa-pass2` |
| `falu2` | 15 | UNSTABLE 2, UNVERIFIABLE 13 | `EXP-0005`, `EXP-0006`, `EXP-0020`, `EXP-0086`, `EXP-0089`, `EXP-0090`, `EXP-0099`, `EXP-0105`, `EXP-0112`, `EXP-0113`, `EXP-0119`, `EXP-0138`, `EXP-M4-10`, `RT-1a-FIX` |

Twelve instructions hang on **one** withheld field each — those are the cheapest to
rescue. `falu2` (15), `matrix_mac` (12) and `tex_addr_setup` (11) are the expensive
ones, and all three are dominated by `UNVERIFIABLE`, i.e. by a raw-format problem
rather than by a hardware unknown.

### T5 — field NAMES that block the most instructions

| field name | instructions blocked | instructions |
|---|---:|---|
| `dst` | 13 | `cvt_f2i`, `falu2`, `frag_color_pack`, `get_sr`, `matrix_mac`, `reg_move_c0`, `reg_move_c1`, `reg_move_c2var`, `reg_move_c9`, `reg_move_cb`, `uniform_mov`, `unpack_convert`, `vtx_out_pos` |
| `src_flag` | 5 | `reg_move_c0`, `reg_move_c1`, `reg_move_c2var`, `reg_move_c9`, `shift_amt_move` |
| `b1` | 4 | `iunary`, `link_save_restore`, `n3_sample_read`, `spill_frame_marker` |
| `b3` | 4 | `link_save_restore`, `n3_sample_read`, `reg_move_cb`, `spill_frame_marker` |
| `form` | 4 | `get_sr`, `ibitcount`, `reg_move_cb`, `tex_addr_setup` |
| `op_desc` | 4 | `atomic_tg`, `reg_move_c0`, `reg_move_c2var`, `reg_move_c9` |
| `opsel` | 4 | `falu2`, `half_alu`, `half_alu_ext8`, `iunary` |
| `src` | 4 | `frag_color_store`, `imageblock_store`, `reg_move_cb`, `unpack_convert` |
| `srcA` | 4 | `half_alu`, `half_alu_ext8`, `iadd2`, `ibfe` |
| `src_class` | 4 | `reg_move_c0`, `reg_move_c1`, `reg_move_c9`, `unpack_convert` |
| `src_reg` | 4 | `reg_move_c0`, `reg_move_c1`, `reg_move_c2var`, `reg_move_c9` |
| `base_slot` | 3 | `atomic_rmw`, `device_load`, `device_store` |
| `cache` | 3 | `falu_acc`, `tex_addr_setup`, `unpack_convert` |
| `reserved7` | 3 | `device_load`, `device_store`, `link_save_restore` |
| `tail` | 3 | `ibitcount`, `tile_read`, `tile_read_mrt` |
| `access_desc` | 2 | `device_load`, `device_store` |
| `addr_desc_hi` | 2 | `atomic_mem`, `atomic_rmw` |
| `amode` | 2 | `atomic_rmw`, `atomic_tg` |
| `b2` | 2 | `spill_frame_marker`, `tile_read` |
| `b4` | 2 | `tile_read`, `tile_read_mrt` |
| `b5` | 2 | `half_alu_ext8`, `threadgroup_barrier` |
| `b6_hi` | 2 | `tile_read`, `tile_read_mrt` |
| `b7` | 2 | `pack_convert`, `tile_read` |
| `dtype` | 2 | `matrix_mac`, `simd_reduce` |
| `idx_off` | 2 | `device_load`, `device_store` |
| `marker` | 2 | `frame_prologue`, `link_save_restore` |
| `mode` | 2 | `iter`, `matrix_mac` |
| `op` | 2 | `cvt_f2h`, `simd_reduce` |
| `op_enable` | 2 | `ibitcount`, `matrix_mac` |
| `reserved` | 2 | `jump_cond`, `stop` |
| `reserved13` | 2 | `device_load`, `device_store` |
| `rsv6` | 2 | `half_alu_ext8`, `tex_addr_setup` |
| `scope` | 2 | `if_push`, `link_save_restore` |
| `srcB_imm` | 2 | `falu2`, `iadd2` |
| `src_cache` | 2 | `cvt_i2f_src`, `ishift` |

`dst` is the single most load-bearing *name*: it blocks 13 instructions. That is not
one experiment's fault — it is the same probe shape reused across waves, and it is the
highest-leverage thing to re-sweep.

---

## 4. The representative-arm defect, outside EXP-0155 (H2)

### T6 — representative-arm defect (H2): inert arm + stable-live arm, same raw

| field | experiment | inert arm(s) (values swept) | stable-live arm(s) (moved) |
|---|---|---|---|
| `device_store.addr_mode` | `EXP-0141` | `synth\|S_addr_mode` (256) | `synth\|S_addr_mode_fwd` (128) |
| `frag_color_store.flags` | `EXP-0155` | `fcs@iter0` (256) | `fcs@pack0` (128) |
| `ibitcount.cache` | `EXP-0139` | `SYNTH:carrier_dag@k\|IBITCOUNT` (2) | `NAT:k_pop@ibitcount+0x012\|IBITCOUNT_NAT` (1) |
| `iter.coeff_sel` | `EXP-0155` | `iter@cent1` (256), `iter@frag0W` (256) | `iter@frag1` (128) |
| `iter.loc` | `EXP-0155` | `iter@frag0W` (256) | `iter@cent1` (48), `iter@cent4` (96), `iter@frag1` (128) |
| `jump_cond.offset` | `EXP-0156` | `cfN\|jc.liveness` (3) | `cf0\|jump_cond.offset` (2) |
| `mov_imm.dst` | `EXP-0140` | `uni\|mov_imm.dst` (16) | `uni\|mov_imm.dst.alias_scan` (3) |
| `sel.b1` | `EXP-0140` | `dsel5\|sel.body.wide` (13) | `dsel5\|sel.body.b1` (136) |
| `tex_sample.chain` | `EXP-0155` | `tex_sample@lo_0` (16) | `tex_sample@lo_1` (3), `tex_sample@t1_0` (1), `tex_sample@t1_1` (2), `tex_sample@t1_2` (2), `tex_sample@t2_0` (1), `tex_sample@t2_1` (1), `tex_sample@t2_2` (2) |
| `tex_sample.lod_present` | `EXP-0155` | `tex_sample@t2_2` (256), `tex_sample@tc_0` (256) | `tex_sample@lo_0` (128), `tex_sample@lo_1` (128), `tex_sample@lo_2` (128), `tex_sample@t1_0` (128), `tex_sample@t1_1` (128), `tex_sample@t1_2` (128), `tex_sample@t2_0` (128) |
| `tex_sample.samp_extra` | `EXP-0155` | `tex_sample@lo_0` (256), `tex_sample@lo_2` (256), `tex_sample@t1_0` (256), `tex_sample@t1_2` (256), `tex_sample@t2_0` (256), `tex_sample@t2_1` (256), `tex_sample@t2_2` (256), `tex_sample@tc_0` (256) | `tex_sample@lo_1` (128) |

---

## 5. The suspect class in full

### T7 — the INERT-SINGLE list (the suspect class)

| field | values swept | arm | runs | evidence |
|---|---:|---|---:|---|
| `atomic_rmw.addr_desc_hi` | 4 | `EXP-0141:atdev\|atdev_atomic_rmw_b6` | 2 | `EXP-0141` |
| `atomic_rmw.amode` | 256 | `EXP-0141:atdev\|atdev_atomic_rmw_b2` | 2 | `EXP-0141` |
| `atomic_rmw.base_slot` | 256 | `EXP-0141:atdev\|atdev_atomic_rmw_b4` | 2 | `EXP-0141` |
| `atomic_rmw.op_msb` | 2 | `EXP-0156:atdev\|atdev_atomic_rmw_b12` | 2 | `EXP-0156` |
| `atomic_rmw.per_lane` | 2 | `EXP-0156:atdev\|atdev_atomic_rmw_b12` | 2 | `EXP-0156` |
| `atomic_rmw.rsv3` | 256 | `EXP-0141:atdev\|atdev_atomic_rmw_b3` | 2 | `EXP-0141` |
| `atomic_tg.amode` | 256 | `EXP-0141:attg\|attg_atomic_tg_b2` | 2 | `EXP-0141` |
| `atomic_tg.ret_desc` | 256 | `EXP-0141:attg\|attg_atomic_tg_b3` | 2 | `EXP-0141` |
| `copysign.operands` | 256 | `EXP-0138:copysign` | 3 | `EXP-0138` |
| `cvt_f2i.b9` | 256 | `EXP-0144:c_f2i\|F` | 2 | `EXP-0144` |
| `cvt_i2f_src.src_cache` | 256 | `EXP-0144:c_i2f_src\|F` | 2 | `EXP-0144` |
| `device_load.access_desc` | 256 | `EXP-0141:synth\|L_access_desc` | 2 | `EXP-0141` |
| `device_load.addr_mode` | 256 | `EXP-0141:synth\|L_addr_mode` | 2 | `EXP-0141` |
| `device_load.reserved13` | 256 | `EXP-0141:synth\|L_reserved13` | 2 | `EXP-0141` |
| `device_load.reserved7` | 256 | `EXP-0141:synth\|L_reserved7` | 2 | `EXP-0141` |
| `device_store.access_desc` | 256 | `EXP-0141:synth\|S_access_desc` | 2 | `EXP-0141` |
| `device_store.reserved13` | 256 | `EXP-0141:synth\|S_reserved13` | 2 | `EXP-0141` |
| `device_store.reserved7` | 256 | `EXP-0141:synth\|S_reserved7` | 2 | `EXP-0141` |
| `falu2_ext.srcA_size` | 2 | `EXP-0154:SYNTH+LIFTED:k_sat_add@falu2_ext[32:40]\|FALU2_EXT` | 3 | `EXP-0154` |
| `falu2_ext.srcB_imm` | 2 | `EXP-0154:SYNTH+LIFTED:k_sat_add@falu2_ext[32:40]\|FALU2_EXT` | 3 | `EXP-0154` |
| `falu2_ext.srcB_neg` | 2 | `EXP-0154:SYNTH+LIFTED:k_sat_add@falu2_ext[32:40]\|FALU2_EXT` | 3 | `EXP-0154` |
| `falu2_uni.srcA_size` | 2 | `EXP-0138:carrier_uni` | 5 | `EXP-0138` |
| `falu2i.imm_flag` | 2 | `EXP-0138:carrier` | 3 | `EXP-0138` |
| `falu_acc.cache` | 2 | `EXP-0154:SYNTH+LIFTED:k_sum@falu_acc[252:256]\|FALU_ACC` | 3 | `EXP-0154` |
| `falu_srcmod12b.mod_hi` | 16 | `EXP-0138:carrier` | 3 | `EXP-0138` |
| `falu_srcmod12b.mod_lo` | 8 | `EXP-0138:carrier_uni` | 6 | `EXP-0138` |
| `falu_srcmod12b.srcB_imm` | 2 | `EXP-0138:carrier` | 3 | `EXP-0138` |
| `falu_srcmod12b.srcB_neg` | 2 | `EXP-0138:carrier` | 3 | `EXP-0138` |
| `fspecial_est.srcA` | 29 | `EXP-0154:SYNTH+LIFTED:k_rsqrt@fspecial_est[18:24]\|FSPECIAL_EST` | 3 | `EXP-0154` |
| `fspecial_est.subop` | 256 | `EXP-0138:fspecial_est` | 2 | `EXP-0138` |
| `get_sr.form` | 2 | `EXP-0140:uni\|get_sr.form` | 3 | `EXP-0140` |
| `half_alu_ext8.b7_lo` | 2 | `EXP-0138:half_alu_ext8` | 3 | `EXP-0138` |
| `half_alu_ext8.b7_mid` | 32 | `EXP-0138:half_alu_ext8` | 3 | `EXP-0138` |
| `iadd2.addsub` | 5 | `EXP-0153:u64\|C_i64add` | 2 | `EXP-0153` |
| `iadd2.b2_fmt` | 64 | `EXP-0139:SYNTH:carrier_dag@k\|IADD2` | 2 | `EXP-0139` |
| `iadd2.srcB_reg_hi` | 128 | `EXP-0139:SYNTH:carrier_dag@k\|IADD2` | 2 | `EXP-0139` |
| `ibfe.b2_bit0` | 2 | `EXP-0154:SYNTH+LIFTED:k_bfe@ibfe[18:30]\|IBFE` | 2 | `EXP-0154` |
| `ibfe.sign_ext` | 2 | `EXP-0154:SYNTH+LIFTED:k_bfe@ibfe[18:30]\|IBFE` | 2 | `EXP-0154` |
| `ibfe.srcA` | 29 | `EXP-0154:SYNTH+LIFTED:k_bfe@ibfe[18:30]\|IBFE` | 2 | `EXP-0154` |
| `ibfins.cache` | 2 | `EXP-0154:SYNTH+LIFTED:k_rot_var@ibfins[42:54]\|IBFINS` | 3 | `EXP-0154` |
| `ibfins.mask_hi` | 2 | `EXP-0154:SYNTH+LIFTED:k_rot_var@ibfins[42:54]\|IBFINS` | 3 | `EXP-0154` |
| `ibfins.mask_imm` | 256 | `EXP-0154:SYNTH+LIFTED:k_rot_var@ibfins[42:54]\|IBFINS` | 3 | `EXP-0154` |
| `icmp_pred.neg` | 2 | `EXP-0139:NAT:k_div@icmp_pred+0x0cc\|ICMP_PRED` | 2 | `EXP-0139` |
| `if_push.scope` | 256 | `EXP-0140:cf\|if_push.scope@7` | 3 | `EXP-0140` |
| `if_push_pred.scope` | 256 | `EXP-0140:cf\|if_push_pred.scope@4` | 3 | `EXP-0140` |
| `ilogic.outmod` | 256 | `EXP-0154:SYNTH+LIFTED:k_and@ilogic[32:42]\|ILOGIC` | 2 | `EXP-0154` |
| `ilogic.z6` | 256 | `EXP-0154:SYNTH+LIFTED:k_and@ilogic[32:42]\|ILOGIC` | 2 | `EXP-0154` |
| `ilogic.z8` | 256 | `EXP-0154:SYNTH+LIFTED:k_and@ilogic[32:42]\|ILOGIC` | 2 | `EXP-0154` |
| `ilogic.z9` | 256 | `EXP-0154:SYNTH+LIFTED:k_and@ilogic[32:42]\|ILOGIC` | 2 | `EXP-0154` |
| `imad.b11` | 256 | `EXP-0139:NAT:k_imad@imad+0x020\|IMAD` | 2 | `EXP-0139` |
| `imad.b1hi` | 128 | `EXP-0139:NAT:k_imad@imad+0x020\|IMAD` | 2 | `EXP-0139` |
| `imad.b2_bit0` | 2 | `EXP-0154:SYNTH+LIFTED:k_imad@imad[32:44]\|IMAD` | 2 | `EXP-0154` |
| `imad.b2_fmt` | 64 | `EXP-0139:NAT:k_imad@imad+0x020\|IMAD` | 2 | `EXP-0139` |
| `imad.store_en` | 2 | `EXP-0154:SYNTH+LIFTED:k_imad@imad[32:44]\|IMAD` | 2 | `EXP-0154` |
| `irotate.b2` | 256 | `EXP-0154:SYNTH+LIFTED:k_rot_imm@irotate[18:30]\|IROTATE` | 2 | `EXP-0154` |
| `isel8.cmpB` | 256 | `EXP-0154:SYNTH+LIFTED:k_rsqrt@isel8[18:32]\|ISEL8` | 3 | `EXP-0154` |
| `ishift.pad9` | 256 | `EXP-0139:NAT:k_ashr@ishift+0x012\|ISHIFT` | 2 | `EXP-0139` |
| `jump.branch_ctrl` | 254 | `EXP-0156:cfN\|jump.branch_ctrl` | 2 | `EXP-0156` |
| `jump.link` | 256 | `EXP-0140:cf\|jump.link@13` | 3 | `EXP-0140` |
| `jump_cond.cf_scope` | 256 | `EXP-0156:cf0\|jump_cond.cf_scope@NAT` | 2 | `EXP-0156` |
| `jump_cond.reserved` | 256 | `EXP-0156:cf0\|jump_cond.reserved@NAT` | 2 | `EXP-0156` |
| `matrix_mac.b11_rsv` | 32 | `EXP-0147:matrix_mac` | 2 | `EXP-0147` |
| `matrix_mac.dst_desc_lo` | 64 | `EXP-0147:matrix_mac` | 2 | `EXP-0147` |
| `n3_sample_read.b1` | 256 | `EXP-0147:n3_sample_read` | 2 | `EXP-0147` |
| `n3_sample_read.b3` | 256 | `EXP-0147:n3_sample_read` | 2 | `EXP-0147` |
| `packed_half2_hi.srcA` | 256 | `EXP-0162:c_ph2\|packed_half2_hi` | 1 | `EXP-0162` |
| `packed_half2_hi.srcB` | 256 | `EXP-0162:c_ph2\|packed_half2_hi` | 1 | `EXP-0162` |
| `shift_amt_move.src_flag` | 2 | `EXP-0154:SYNTH+LIFTED:k_rot_var@shift_amt_move[76:80]\|SHIFT_AMT_MOVE` | 2 | `EXP-0154` |
| `tg_addr_compute.b3` | 256 | `EXP-0156:tgac\|tgac.b3` | 2 | `EXP-0156` |
| `tg_addr_compute.b4` | 256 | `EXP-0156:tgac\|tgac.b4` | 2 | `EXP-0156` |
| `tg_addr_compute.b5` | 256 | `EXP-0156:tgac\|tgac.b5` | 2 | `EXP-0156` |
| `threadgroup_barrier.b5` | 256 | `EXP-0141:tgtile\|tgtile_threadgroup_barrier_b5` | 2 | `EXP-0141` |
| `threadgroup_barrier.flags` | 256 | `EXP-0141:tgtile\|tgtile_threadgroup_barrier_b4` | 2 | `EXP-0141` |
| `tile_read.b2` | 256 | `EXP-0147:tile_read` | 2 | `EXP-0147` |
| `tile_read.b4` | 256 | `EXP-0147:tile_read` | 2 | `EXP-0147` |
| `tile_read.b6_hi` | 128 | `EXP-0147:tile_read` | 2 | `EXP-0147` |
| `tile_read_mrt.b4` | 256 | `EXP-0147:tile_read_mrt` | 2 | `EXP-0147` |
| `tile_read_mrt.b6_hi` | 128 | `EXP-0147:tile_read_mrt` | 2 | `EXP-0147` |
| `uniform_mov.dst` | 16 | `EXP-0140:uni\|regmove.dst` | 3 | `EXP-0140` |
| `vtx_out_pos.dst` | 16 | `EXP-0147:vtx_out_pos` | 2 | `EXP-0147` |
| `vtx_out_pos.slot` | 256 | `EXP-0147:vtx_out_pos` | 2 | `EXP-0147` |

---

## 6. Method notes that changed the answer

Three parse defects were found and fixed during construction; each one, left in, would
have manufactured a false headline. They are recorded as amendments A2–A5 in
`PRE_REGISTRATION.md` and in `PROGRESS.md`.

1. **The raw does not name db fields — it names what the harness spliced**, very often a
   whole byte (`byte+12`, `b6`, `byte0_lonib`) or a composite
   (`op_lsb|op|per_lane|op_msb`). A naive name match reported `tile_read.read_en` as
   having no raw record when EXP-0147 had swept all 256 values of the byte containing
   it. That alone would have inflated `UNVERIFIABLE` from 144 to 240.
2. **The converse is the more dangerous one, and it is why attribution is done from the
   bytes.** A group labelled with ONE field name usually varies a whole byte, so
   movement credited to that field may have been produced by a different field sharing
   the byte. Every case is therefore partitioned by "the instruction word with this
   field's bits cleared", and only partitions holding ≥ 2 distinct values of the field
   count as testing it.
3. **The arm key was collapsing distinct occurrences.** EXP-0140 and EXP-0156 put the
   shader in `carrier` and the occurrence in `arm`; keying on `carrier` alone merged
   `regmove.byte2` with `regmove.usrc` and manufactured `INERT-SINGLE` verdicts. Fixed
   to the pair — which moved the number *against* this audit's own hypothesis
   (`INERT-SINGLE` 85 → 81), the only direction an amendment is allowed to move it.

**Descriptor identification.** EXP-0140 logs the whole reg-move family under the single
instr name `regmove`, which is not a db mnemonic. Where the bytes unambiguously satisfy
one descriptor's `match` constraints the descriptor is recovered from them; where the
sweep varies the descriptor-selecting byte *itself* no single descriptor owns the cases,
and those 13 fields are reported as `raw-present-but-unattributable` rather than as
"no raw". EXP-0140's own notes already say db.json's per-descriptor split of that byte
does not match the observed behaviour — this audit agrees with the experiment and
disagrees with the descriptor.

---

## 7. Controls (pre-registered in §8 of `PRE_REGISTRATION.md`)

| control | result |
|---|---|
| **C1** — restricted to EXP-0155, reproduce the orchestrator's 15 withheld fields | **PASS.** All 15 land in a withhold bucket, *and with the matching reason*: every "never-moved; single carrier only" comes out `INERT-SINGLE`, every "live-but-not-reproducible" comes out `UNSTABLE`. |
| **C2** — `iter.dst` must classify `STABLE-LIVE` | **PASS.** |
| **C3** — fault/hang movement must be visible to the signature | **PASS by construction and observed:** the effect signature carries a hard-failure class, and the `dst`-family boundary (fault at GPR ≥ 96, hang above it) is what makes several `dst` fields `STABLE-LIVE` at all. |
| **C4** — no silent skips: exactly 664 records, all 53 cited experiments accounted for | **PASS.** `analysis/experiment_coverage.json` carries a parse verdict for every cited id; 0 evidence ids failed to resolve to a directory; 0 unparseable raw lines across 728 387 records. |

**Sensitivity (reported, never used to re-bucket).** 15 of the 41 `UNSTABLE` fields
clear the movement test and fail *only* the 99% cross-run agreement bar, sitting between
95% and 99% — `frag_color_pack.dst` misses by 0.03 points (2 disagreements in 194 common
values). Keeping all 15 raises `strict` emittability from 16 to 17, so the headline is
not an artefact of that threshold. The full list is in
`analysis/emittability.json` → `sensitivity_agree_95pct`.

---

## 8. Interpretation, and what it does NOT say

**Observed:** 144 of 664 emitter-grade fields have no per-value raw record attributable
to them; 81 never moved an observable on the single carrier they were tried on; 41 moved
non-reproducibly; 11 have an inert arm sitting beside a stably-live arm in the same raw.

**Interpretation:** the corpus contains two populations with very different audit
quality. The EXP-0138+ waves are genuinely re-derivable and mostly hold up (EXP-0155:
73/90 `STABLE-LIVE`, 0 `INERT-SINGLE`; EXP-0154: 72/98). The pre-EXP-0138 waves are not
re-derivable at the field level, and the `INERT-SINGLE` residue concentrates in the
waves that ran before the merge policy existed (`EXP-0154` 20, `EXP-0141` 15,
`EXP-0147` 11, `EXP-0138` 10).

**Alternatives not excluded:**
- `UNVERIFIABLE` is a statement about the *record*, not the hardware. EXP-M4-14 ran real
  A18 splices and its `splice_results.json` contains per-field prose evidence with
  spliced bytes and observed pixels; it simply is not machine-checkable and has no
  second run. Its 49 fields should be re-recorded, not disbelieved.
- `INERT-SINGLE` does not mean "the field is live". It means the probe could not have
  shown it either way. EXP-0163 is testing exactly this hypothesis on the neo for
  EXP-0155's 22 never-moved fields; the same treatment is what these 81 need.
- Cross-run agreement is measured between the two gated runs with the widest coverage.
  Where an experiment ran more than two gated runs (EXP-0138 ran six), the other runs
  are recorded but do not enter the agreement figure.

**Confounders recorded rather than assumed away:** two occurrences of one instruction in
one program count as two arms, so `INERT-MULTI` is a weaker guarantee than "two
different shaders" (`iter_at.loc` is the live example); a non-deterministic `observed`
payload would push fields to `UNSTABLE`, so the count of distinct baseline signatures
per arm is carried in `audit.json` as `noisy_harness_arms` (it is empty).

**Target status:** unchanged by this audit. Each field keeps the target recorded in
`validation.json`; `audit.json` carries it per record. Nothing here promotes a G16G
result to G17P or vice versa.

---

## 9. Recommended action (the orchestrator owns the decision)

1. **Do not withhold all 266.** The defensible immediate action is the 81
   `INERT-SINGLE` + 41 `UNSTABLE` = 122 fields, giving **33 / 166** — every one of them
   has a concrete, cheap remedy (a second structurally different carrier, or a third
   gated run).
2. **Twelve instructions are one field away** from keeping emittable status
   (`atomic_mem`, `copysign`, `cvt_f2h`, `falu_acc`, `if_push`, `iter_at`, `mov_imm`,
   `pack_convert`, `pixel_order`, `shift_amt_move`, `stop`, `uniform_mov`). That is the
   highest-value dispatch list in this report.
3. **The 144 `UNVERIFIABLE` are a records problem, not a physics problem.** The fix is a
   re-record pass in the EXP-0138+ `sweep.jsonl` schema, not new physics — starting with
   `falu2` (13 fields), `tex_addr_setup` (11) and `matrix_mac` (10).
4. **Re-sweep `dst` deliberately.** One field name blocks 13 instructions.
5. **Read every `INERT-MULTI` envelope before trusting it.** `iter_at.loc` proves two
   carriers can be one carrier in the dimension that matters.

## 10. Limitations

- The audit is only as good as the `bytes` column. 250-odd case groups (of ~4 200) have
  no usable `bytes` and fall back to label-level attribution; exactly one merged field
  ends up attributed at label level only (`byte_level_only` in `audit.json`).
- 8 008 raw records in 119 groups remain unattributed. All were inspected and are
  non-field probes (EXP-0159 questionnaire items, EXP-0155's `op57_*` collision probes,
  EXP-0146's i64-lowering checks, `SEM` semantic probes); the full list is in
  `work/raw_index.json.gz` `_meta.unresolved_groups`.
- Gated-run selection is by convention (`PARTIAL.md`, and run names containing
  `prefreeze|smoke|pilot|quarantine|burned`). Where an experiment declared its gated
  runs in prose only, that declaration was not machine-read; the selected set is printed
  per experiment in `analysis/experiment_coverage.json` and should be eyeballed.
- `validation.json` moves. This audit is a snapshot at `b7dedbf0`; re-run both scripts
  after any merge.
- The raw corpus also moves — EXP-0163/0165/0166/0167 were writing new `raw/` records
  while this ran (the index grew from 4 198 to 4 354 case groups between two runs). The
  verdicts are unaffected because only the raw of *cited* experiments is read, and both
  runs produced byte-identical bucket counts and an identical withhold set; but a
  re-run after those waves merge will legitimately differ.
