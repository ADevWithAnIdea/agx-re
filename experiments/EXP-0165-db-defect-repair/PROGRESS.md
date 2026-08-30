# EXP-0165 PROGRESS (append-only)

## 2026-08-30 — start
Read CLAUDE.md, CODEX.md, experiments/SUBAGENT_BRIEF.md, FIELD-SWEEP-PROTOCOL.md,
EXP-0161 RESULTS.md + field_verdicts.json `db_defects`, and the four target
descriptors in tools/agx-isa/db.json (`fspecial`, `fspecial_est`, `mov_zext16`,
`carry_gen`).  No db.json edit yet.

## DEF-0161-1 (fspecial operands swapped) — RE-DERIVED INDEPENDENTLY: **CONFIRMED**
Scripts: `analysis/rederive_def1_fspecial.py`, `analysis/def1_summary.py`,
`analysis/rederive_gen03.py`.  Inputs: EXP-0161 `raw/g17p_20260829_run01`,
`run02` (arm `D3_FSPEC_SYNTH`, 16-register dumps) and `raw/g17p_20260830_gen03`.
Rederived from the seed vector + register dumps only; EXP-0161's own verdicts
were not read.

* byte+1 high nibble (db `dst`): **all 16 values byte-identical to the
  baseline dump**, in BOTH gated runs.  Inert.
* byte+3 (db `src`): destination register = `v >> 1`.  **28 / 28 fit, 0
  misfits** in both runs (v = 0..29 -> r0..r14).  Values 12/13 write r6, whose
  seed 0.5 already equals rsqrt(seed[r0]=4.0), so the write is invisible — an
  aliasing artefact of the seed vector, not a misfit.  v >= 30 selects r15+,
  outside the dump.
* byte+5 (db `src_ext`): source register = `v >> 2`.  **60 / 60 fit, 0
  misfits** in both runs (v = 0..59 -> r0..r14), each identified twice over:
  the computed rsqrt matches that register's seed, AND that register is
  released to zero (56/56 where src != dst).
* Generation: re-scored gen03's 20 `fspecial` cases from the committed block
  bytes, ignoring EXP-0161's verdict field.  Corrected model **20/20 pass**;
  the committed db.json model gets **10 fail + 10 unpredictable** (its `dst`
  nibble is 0 in every generated case while the result lands elsewhere).

## DEF-0161-2 (mov_zext16 register in byte0 hi nibble) — **CONFIRMED**, with one correction to the severity
Script: `analysis/rederive_def2_zext.py`.  Inputs: run01/run02 `B_ZEXT_SYNTH` +
`B_ZEXT_INPLACE`, supp02/supp03 `B2_ZEXT_SYNTH_R5`, gen03.

* `byte0 = 0xN3` narrows r[N] and NOTHING else: **11/11 fits, 0 misfits** in both
  gated runs (N = 0..10).  N = 0xB..0xF: **no register changes at all** (no-op).
* No byte0 whose LOW nibble != 3 narrows anything (all 16 buckets checked).
* `src_reg` (byte+1 bits0-6): **128/128 register dumps identical to baseline**;
  `src_flag`: 2/2 — in run01, run02, supp02 AND supp03 (the r5 form).
* `__falsifier_byte0 := 0x00` fires (`wrong_value`) in the SYNTH carrier and is
  `ok` in EXP-0146's INPLACE carrier — that carrier is dead, as EXP-0161 says.
* gen03 re-scored from block bytes: 11/16 pass, failures exactly 0xB..0xF.  One
  anomaly recorded: nibble 0x8 narrowed in 4 of 5 observations and was a no-op in
  gen03.
* **Severity correction:** EXP-0161's "the register selector is invisible to an
  emitter" is not right — `n3_mov` (match `[0,4,3]`) ALREADY exposes byte0's high
  nibble as a 4-bit `dst` register field and its own semantics says it generalises
  `mov_zext16` (0x13) and `frame_marker` (0x43).  EXP-0161 never mentions `n3_mov`.
  The defect is real, but it is a mis-modelled descriptor, not an unreachable
  register.

## DEF-0161-3 (fnclass) — **CONFIRMED IN PART, REFUTED IN PART**
Script: `analysis/rederive_def3_fnclass.py`, measured by COMPUTED VALUE in three
carriers x two runs.  Bit 3 IS a don't-care (8/8 pairs identical, everywhere).
Bit 2 is **NOT**: at `class&3 == 0` it is live on both datapaths (4/12 store
nothing) and at `class&3 == 1` it is live on 0x2f (5/13 FAULT).  And EXP-0161's
"values 1,3,5,...,15 all compute the same function" holds only on the 0xaf
carrier — on 0x2f, 1 -> rsqrt, 3 -> NaN, 5 -> fault.  Applied as corrected.

## DEF-0161-4 (roundmode bit0 -> NaN) — **CONFIRMED** exactly
`analysis/rederive_def4_roundmode.py`, using `math.isnan` not a tolerance compare:
128/128 odd values all-NaN in 12/12 lanes and 128/128 even values bit-matching the
baseline, in 2 carriers x 2 runs (4 independent tables, no exceptions).

## DEF-0161-5 (device_store not interlocked vs device_load) — **CONFIRMED**
Re-read `raw/prefreeze/pilot_seed.json` against `harness/pilot_seed.py`: P1/P3
(load order reversed) both leave r0..r4 stale -> follows STORE order; P5 (dump
order reversed) moves the stale set to r11..r14; P4 reproduces it with only 5
loads outstanding; P7/P6/P2 (4/16/64 filler ops) leave 5/3/0 stale -> a latency;
P8 (second load wave) leaves 0.

## DEF-0161-6 (carry_gen byte+2) — **CONFIRMED EXHAUSTIVELY**, decode change NOT applied
`analysis/rederive_def67_carry.py` checks the rule against all 256 swept values in
both carriers x both runs: accepted set is exactly {05,07,15,17,25,27,35,37} and
an exhaustive search over all 256 candidate masks returns `(v & 0xCD) == 0x05` as
the UNIQUE separator — 0 false accepts, 0 false rejects.  The match relaxation is
still deferred: it needs 3 match entries + 2 NEW field names, and a new db.json
field with no validation.json entry hard-fails `validate_labels.py`.

## DEF-0161-7 (carry_gen size bit) — **CONFIRMED**
Predicate recomputed directly from the committed register dumps (not from the
harness' `observed_predicate`): size-aware model 16/16 (gen02) and 48/48 (gen03),
covering both widths and both settings of the inert bit 7; an always-32-bit model
scores 7/16 and 39/48.

## db.json PATCHED — gates green
`analysis/apply_defects.py tools/agx-isa/db.json`.
* `roundtrip_test.py`: **ALL PASS**, 0 FAIL (unchanged).
* corpus A/B (`analysis/ab_gate.py`): clean **833/1080**, leftover **388604**,
  tokens **25419** — identical before and after.  Only firing delta:
  `n3_mov` 336 -> 259, `mov_zext16` 54 -> 131 (105 in, 28 out; same family, same
  lengths).
* `validate_labels.py`: **exit 0**, output identical to before except the expected
  `db_sha256` WARN.
* functional check (`analysis/functional_check.py`, re-emitting the encodings the
  HARDWARE accepted): decode **42 ok / 37 bad -> 72 ok / 7 bad**; re-emit
  unchanged at 73/6.

## NEW FINDING (not from EXP-0161): legal `carry_gen` encodings are mis-lengthed
`isadb.py`'s R9 trailing-word closure claims 16 `(0x32, byte+1)` pairs as 2-byte
pads before the low-nibble-2 length rule runs, so 6 of EXP-0161's 48 PASSING
generated `carry_gen` encodings do not round-trip through our own tokenizer.
Recorded in db.json `length_rule_gaps`; the guard was built and MEASURED
(`work/probe_r9`) and REGRESSES the corpus gate (833 -> 832 clean, +398 leftover),
so it was NOT applied.

---

# SECOND DISPATCH (coordinator, mid-task): EXP-0160 + EXP-0157 defects

Device work in §4 of the original dispatch is **stood down** at the coordinator's
request (EXP-0167 needs a quiet GPU). Nothing here needed the device.

## EXP-0160 — re-derived, all CONFIRMED
Scripts: `analysis/rederive_imad.py`, `analysis/rederive_0160_misc.py`.

* **DEF-0160-6 (the most serious) CONFIRMED.** Solved `r0 = m*(seed[a]*seed[b]) + A`
  from scratch with BOTH multiplicands free, requiring one solution to satisfy both
  seed sets. 132 2-D points, **0 with no solution**. byte+6 = 0x10 pins r2
  **uniquely**; 0x00/0x02/0x04 -> r0, 0x08 -> r1, 0x20 -> r4, 0x40 -> r8. Rule
  `reg = v>>3` fits 10 of 11 probed values (the eleventh, 0xFF -> r31, is outside
  the seeded set).
* **DEF-0160-3 CONFIRMED and sharpened.** 191 of 192 clean two-seed values fit
  exactly; the one exception is a status-OK-wrote-nothing dispatch (DEF-0160-5's own
  class). `m` is determined ENTIRELY by bits 0-1 (0 keep / 1 drop / 2 drop / 3
  FAULT, all 64 `(v&3)==3` values and no others). Bit 2 inert, 0 disagreeing pairs.
  `A` single-valued per K over all 32 K and seed-independent by construction.
* **DEF-0160-7 CONFIRMED**: addend constant across every mulsel point, 12/12 descs.
* **DEF-0160-1 CONFIRMED**: `(v & 0xD7) == 0x16` unique over 256 masks; bit 5 the
  only inert bit; opsel map 0=a+b 1=a*b 2=a*b+a 4=-b 5=0 6=a*b+c, `(v&7)==7` faults.
* **DEF-0160-2 CONFIRMED**: anchor computes `imin(r0,r2)` in both seed sets and r2
  (named by byte+3) is released to zero; byte+5 has 4 inert bits and no register map.
* **DEF-0160-4 CONFIRMED**: the splice positive control fires (r6=77 AND r7=99) while
  the +2..+3-only splice leaves the seeds -> half_pack really is 4 bytes.
* **NEW, not in EXP-0160**: imad's SECOND multiplicand is r2 while byte+5 = 0x08,
  which `(reg<<1)|size` reads as r4 -- byte+5's role is UNRESOLVED and unswept.

## EXP-0157
* `sfu_marker`: two fields added, match relaxed to the HW-required bits. Corpus A/B
  shows **zero firing delta** (the length rule still gates byte+1 == 0x02).
* `op04_len8`: HW-measured 12-byte length **REGRESSES** the gate (833 -> 823 clean,
  +1964 leftover). Reported and left, per instruction.
* `half_pack` length: measured, **IMPROVES** (-20 leftover), left to the length-rule
  owner. `mesh_out_src`: recorded, belongs with the op04 rework.

## SECOND db.json WRITE — done, gates green
`analysis/apply_defects2.py tools/agx-isa/db.json`. Corpus clean **833**, leftover
**388604**, tokens **25419** -- all unchanged, **zero firing delta**. roundtrip
**ALL PASS**. `validate_labels.py` exits **1** with exactly two `MISSING label`
errors for `sfu_marker.b0_hi`/`.b1_hi` (the two new fields the coordinator asked
for); merging `analysis/field_verdicts.json` clears both, and
`analysis/revert_sfu_marker_fields.py` backs them out if green is wanted first.

**db.json is now STABLE — no further writes planned.**
sha256 `addf5edaf29cc218954af6fbdc277a4c0dd827267c177bbd8af6a57e90f71b8f`.

## Deliverables complete
`README.md`, `RESULTS.md`, `manifest.json`, `analysis/` (14 scripts),
`work/` (evidence dumps + `PROBES.md` describing the 4 measured-but-not-applied
variants). 27 re-expressed verdicts in `analysis/field_verdicts.json`;
`work/merge_verdicts.py --dry-run` applies 27, skips 0.
