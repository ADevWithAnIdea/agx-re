# EXP-0201 — G17P float ALU: six fields across five instructions

**Question.** Five float-ALU instructions in the emitter worklist are blocked by six fields between
them. Can an emitter *choose* each field's value and get documented behaviour on the A18 Pro / G17P?

| instruction | field | span | prior state, and why it is still open |
|---|---|---|---|
| `falu3` | `op` | 16..23 | 256 values, **428 moved** — withheld **UNSTABLE**: one arm, 87.5 % cross-run |
| `falu3_ext` | `op` | 16..23 | 256 values, **450 moved** — withheld **UNSTABLE**: one arm, 87.5 % cross-run |
| `fspecial_est` | `srcA` | 8..15 | 256 values over 4 arms, **1 moved** — a **detection-power** problem, not instability |
| `falu3_srcmod12` | `opsel` | 16..18 | prior sweep **ALIASED** — nominal 4 and 6 assembled to identical bytes |
| `falu3_srcmod12` | `ctrl` | 32..38 | no documented refusal — open ground |
| `copysign` | `operands` | 24..31 | 256 values, **256 distinct encodings**, no faults, 100 % agreement — and **V = 1**: it ran legally and was **indistinguishable** |

`copysign._instruction` is additionally still `corpus-correlation`, so the family cannot be called
emittable even if the field passes.

**Hypotheses, refuters, confounders, coverage, the promotion gate and the quiet-window protocol:**
`PRE_REGISTRATION.md` (frozen, with `CAPTURE_CONTRACT.json`, before any build or device run),
including amendments A1 and A2 recorded pre-build on coordinator intel.

**`PRE_REGISTRATION-A.md` is AMENDMENT A**, frozen before the first dispatch of run id
`g17p_20260830_a_run01`. `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` landed in the repository while
runs 01-04 were executing; it is normative and overrides this experiment's original gates where
they conflict. The amendment adds the Gate-A caller-to-**actual**-dispatched-byte ledger, Gate-C
adversarial float inputs, Gate-E reversed case order plus a strict quiet requirement, and the six
independent verdict axes. **Runs 01-04 are retained unchanged** and reclassified on those axes;
nothing is discarded and nothing that already meets a gate is re-run.

**Outcome: no field is promoted, and one gate blocks five of the six -- the machine was never
quiet.** See `RESULTS.md` §0 and §7.

## The three failures this design is built around

1. **The oracle, not the range, is the binding constraint.** `copysign.operands` was already swept
   dense with **256 distinct encodings** and stayed `untested` because the oracle was *constant*: a
   constant expectation across a varying field predicts the *instruction's* effect, not the
   field's. So every arm here carries a **per-value host-computed prediction** and every case
   records **which named library member the hardware actually produced** (`observed_fn`), out of
   9–14 pairwise-distinct 8-lane candidate vectors proven distinct on the host by
   `analysis/oracle_check.py` **before** the contract was frozen.
2. **Aliasing is checked before dispatch, not after.** `opsel` (bits 16..18) straddles its own
   descriptor's `match` constraint at bit 17. No assembler is used: `run.py` splices raw bits, and
   `analysis/gen_arms.py` refuses to emit an arm unless every value produces **pairwise-distinct
   bytes** whose XOR against the baseline is **confined to the field's own span**.
3. **A confirmation run needs a quiet machine.** `harness/gpuwatch.py` samples the device process
   table every 2 s for the duration of every gated run into `raw/<run_id>/gpuwatch.jsonl`.
   Quietness is a **measurement**; a run with any foreign GPU-runner sample is reported
   `CONTAMINATED`, never as a clean refutation.

## Method

Splice one field of one located instruction occurrence inside the compiled `_agc.main` of **our own
MSL**, dispatch it on real hardware, and read back a **poisoned** output buffer (`0xDEADBEEF + i`)
against the host oracle, with an **integrity sentinel** written first through an independent path
and the OS fault-classification string recorded on every non-`ok` case.

* `kernels/k_falu201.metal` — the fifteen authored carriers (3 `falu3`, 2 `falu3_ext`,
  2 `falu3_srcmod12`, 4 `fspecial_est`, 4 `copysign`). Multiple carriers per field because
  the two `op` fields had **one arm each** and `fspecial_est.srcA` had no arm with detection power.
* `harness/carriers201.py` — dispatch shape, authored inputs, and the **host function library**.
* `harness/models201.py` — the per-value falsifiable prediction for each field, taken from
  `db.json`'s own published notes so that a mismatch *refutes the published map*.
* `harness/locate201.py` — occurrence location by the **pinned** descriptor signature, then
  cross-checked against the pinned tokenizer (four descriptors share `[0,4,9] + [17,1,1]` and
  differ only by length, so a signature hit alone is not an occurrence).
* `harness/saferunner201.py` — one reader thread per child, tagged by owner; a malformed response
  is a **measurement failure**, never a hang.
* `run.py` — the sweep driver. **No hang budget, no abort path**: every value is dispatched.
* `analysis/verdicts.py` — the frozen gate, with a self-test that proves it can say **no** and that
  it does **not** refuse a width-1 field by arithmetic.

## Reproduction

```bash
export SSHPASS='...'                        # never written to any file
python3 analysis/oracle_check.py            # host: libraries must discriminate
python3 analysis/contract.py freeze
bash harness/sync.sh push
python3 harness/verify_remote.py            # SEPARATE step; exit 0 required
bash harness/sync.sh build
bash harness/sync.sh shell 'cd ~/agxre/EXP-0201 && python3 analysis/gen_arms.py'
bash harness/sync.sh pullharness            # freeze arms201.json into the contract
python3 analysis/contract.py freeze
bash harness/sync.sh push && python3 harness/verify_remote.py
# gated_run.sh attaches harness/gpuwatch.py to the same run directory, so
# "the machine was quiet" is a measurement in raw/<run_id>/gpuwatch.jsonl
bash harness/sync.sh shell 'cd ~/agxre/EXP-0201 && bash harness/gated_run.sh g17p_YYYYMMDD_a_run01 --order forward'
bash harness/sync.sh shell 'cd ~/agxre/EXP-0201 && bash harness/gated_run.sh g17p_YYYYMMDD_a_run02 --order reverse'
bash harness/sync.sh pull
python3 analysis/verdicts.py raw/g17p_YYYYMMDD_a_run01 raw/g17p_YYYYMMDD_a_run02
python3 analysis/maps.py     raw/g17p_YYYYMMDD_a_run01 raw/g17p_YYYYMMDD_a_run02
python3 analysis/op_semantics.py raw/g17p_YYYYMMDD_a_run01 raw/g17p_YYYYMMDD_a_run02
python3 analysis/finalize.py
python3 analysis/manifest_build.py
python3 ../../tools/agx-isa/wave_audit.py .        # the arrival gate, run by us first
```

## Clean-room statement

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected:      kernels/k_falu201.metal (authored by us) and its compiled _agc.main bytes
Apple binary introspection: NONE
Reproduction:          the block above; run ids in raw/
Evidence:              raw/<run_id>/sweep.jsonl (append-only), CAPTURE_CONTRACT.json hashes
```

**Results:** `RESULTS.md`. **Progress log:** `PROGRESS.md`.
**Not edited, not committed:** `tools/agx-isa/`, `docs/`, `PROVENANCE.md`.
