# EXP-0160 — the last blocking field on eight ALU instructions (G17P)

**Question.** Eight instructions in `tools/agx-isa/db.json` are blocked from `emittable` by
**exactly one field each**. Can that one field be moved to emitter grade, on the A18 Pro /
G17P, for each of them?

| instruction | blocking field | label at dispatch |
|---|---|---|
| `falu2_ext` | `ctrl` | `tokenization-only` |
| `falu3` | `op` | `untested` |
| `falu3_ext` | `op` | `untested` |
| `iminmax` | `srcB` | `untested` |
| `isel8` | `cmp_mode` | `untested` |
| `imad` | `srcC_desc` | `corpus-correlation` |
| `half_pack` | `src` | `corpus-correlation` |
| `falu2i` | `ctrl_lo` | `tokenization-only` |

**Hypotheses, method, promotion rule, falsifiers:** `PRE_REGISTRATION.md` (frozen before any
build or run). **Frozen inputs and hashes:** `CAPTURE_CONTRACT.json`.
**Observations and verdict:** `RESULTS.md`, `analysis/field_verdicts.json`.

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/probes.metal and kernels/carrier_dag.metal (both authored by us
  for this experiment) and the AGX machine code the PUBLIC Metal runtime API compiled from
  that source. tools/{shdump,agxtest,agx-isa} used READ-ONLY and unmodified. EXP-0154's
  committed raw JSONL was read as prior evidence, for experiment DESIGN only.
Apple binary introspection: NONE
Reproduction: see "Reproduction" below
Evidence: raw/g17p_20260830_run01/, raw/g17p_20260830_run02/ (the gated pair);
          raw/g17p_20260830_confirm01/ (isolated fault adjudication, FIELD-SWEEP-PROTOCOL 7A);
          raw/g17p_20260830_smoke01/ (retained smoke capture);
          work/anchors/anchor_report.json, work/authored_hashes.txt
```

## Method in one paragraph

Carrier style **SYNTH-WITH-LIFTED-BLOCK**. The whole `_agc.main` of an authored carrier is
replaced by a program assembled from `tools/agx-isa`'s own field rules: seed r0..r15 with 16
distinct values → store a PRE sentinel to memory → **a contiguous block lifted byte-for-byte
out of the compiled form of our own MSL**, with exactly one byte mutated → dump all 16
registers → write and store a POST sentinel → `stop`. Reading a GPR as a 32-bit source zeroes
it, so the 16-register dump turns release-on-read from a trap into an instrument. Both
sentinels live where the instruction under test cannot name them. The read-back buffer is
pre-filled with `0xDEADBEEF`, so a dumped word still holding poison proves that store never ran
— a *framing break* rather than a wrong value. **Every case runs under two independent seed
sets** with a byte-identical program shape, so a model fitted on set 1 must predict set 2's
register post-state out of sample.

## Reproduction

```sh
# on the repo host (M4): push authored inputs + pinned toolchain to the test target
export SSHPASS=...            # NEO=192.168.10.243
harness/sync.sh push

# on the neo (A18 Pro / G17P), under ~/agxre/EXP-0160:
python3 harness/anchors.py            # compile our MSL, locate the eight anchors
python3 harness/casematrix.py         # the frozen matrix: 4064 cases, sha256 f2a2fec3...
python3 harness/casematrix_ext.py     # Addendum A: 1028 cases, sha256 e919aa1b...

python3 harness/run.py     --run g17p_20260830_run01     --order forward
python3 harness/run.py     --run g17p_20260830_run02     --order reverse
python3 harness/run_ext.py --run g17p_20260830_ext_run01 --order forward
python3 harness/run_ext.py --run g17p_20260830_ext_run02 --order reverse

# adjudication (FIELD-SWEEP-PROTOCOL 7A). The GPU lease was REMOVED from the
# protocol while this experiment ran, so these are repetition, not isolation --
# see RESULTS.md section 4.4 for what that cost and what replaced it.
python3 harness/confirm_faults.py --run g17p_20260830_confirm02 \
        --from raw/g17p_20260830_run01 raw/g17p_20260830_run02 --reps 5
python3 harness/confirm_faults.py --run g17p_20260830_confirm03 \
        --from raw/g17p_20260830_run01 raw/g17p_20260830_run02 \
        --idx-file work/readjudicate.idx  --reps 5
python3 harness/confirm_faults.py --run g17p_20260830_confirm04 \
        --from raw/g17p_20260830_run01 --idx-file work/readjudicate2.idx --reps 9
python3 harness/confirm_faults.py --run g17p_20260830_confirm05b \
        --from raw/g17p_20260830_smoke01 --idx-file work/readjudicate4.idx --reps 25
python3 harness/confirm_faults.py --run g17p_20260830_confirm06 \
        --from raw/g17p_20260830_smoke01 --idx-file work/readjudicate6.idx --reps 40
python3 harness/confirm_ext.py    --run g17p_20260830_ext_confirm01 \
        --from raw/g17p_20260830_ext_run01 --idx-file work/ext_readjudicate.idx --reps 20

# back on the repo host
harness/sync.sh pull <each run id>
python3 analysis/verdicts.py raw/g17p_20260830_run01 raw/g17p_20260830_run02 \
    --confirm raw/g17p_20260830_confirm01,raw/g17p_20260830_confirm02,\
raw/g17p_20260830_confirm03,raw/g17p_20260830_confirm04,\
raw/g17p_20260830_confirm05b,raw/g17p_20260830_confirm06
python3 analysis/verdicts.py raw/g17p_20260830_ext_run01 raw/g17p_20260830_ext_run02 \
    --confirm raw/g17p_20260830_ext_confirm01 --matrix casematrix_ext \
    --out analysis/field_verdicts_ext.json
python3 analysis/merge_ext.py         # folds Addendum A into field_verdicts.json
```

`analysis/prior_scan.py` and `analysis/design_check.py` are desk-only re-readings of EXP-0154's
committed raw records; they touch no hardware and promote nothing.

`raw/g17p_20260830_confirm01/` is retained but superseded: a victim-class failure on one arm's
baseline made 32 of its cases `undecodable`, which is why `confirm02` exists (contract
amendment 01). `work/preview_verdicts.json` and `work/preview2.json` are retained snapshots of
two **superseded** analysis gates, including the one retracted by amendment 06; they are kept
so the retraction is auditable, and no label depends on them.

## Scope and non-goals

This experiment does **not** edit `tools/agx-isa/db.json`, `tools/agx-isa/validation.json`,
`docs/`, or `PROVENANCE.md`, and it does not commit. Model corrections are reported under
`db_defects` in `analysis/field_verdicts.json` for the orchestrator to merge
(FIELD-SWEEP-PROTOCOL §6).
