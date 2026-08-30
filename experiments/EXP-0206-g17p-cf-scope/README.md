# EXP-0206 — control flow and scope on G17P: seven fields across six instructions

**Question.** Six control-flow instructions — `call`, `ret`, `ret_luse`, `if_push`, `stop`,
`pop_reconverge` — are each one or two fields away from emitter grade. All seven blocking
fields have already been measured and all seven were **refused**, and the refusals share one
shape: *the arm could not express the dimension the field controls, or the gate could not come
out the other way.* This experiment attacks the **carrier** and the **gate**, not the sample
size.

| instruction | field | start | width | prior status | the recorded wall |
|---|---|---:|---:|---|---|
| `if_push` | `scope` | 16 | 8 | `single-template-inference` | EXP-0184 got 0/2560 — and named its own gap: **the loop-iteration region kind (`scope_kind == 0x1a`) was never reached** |
| `pop_reconverge` | `scope` | 16 | 8 | `untested` | 512 valid observations per arm, **one** distinct payload, **no control of any kind** |
| `pop_reconverge` | `reserved` | 32 | 16 | `untested` | DEF-0190-1: the INERT bucket returns `moved = 0` **by construction** |
| `call` | `tail` | 104 | 8 | `untested` | EXP-0189: the promoting gate had **no `moved >= 1` conjunct**, so a perfectly inert field passed it |
| `ret` | `scoreboard` | 24 | 8 | `corpus-correlation` | it is an **ordering** wait mask and neither carrier had anything to wait on |
| `ret_luse` | `linkmode` | 8 | 8 | `untested` | EXP-0192 **Case C**: 1 distinct VALID payload across 32 LEGAL values — a hazard map, not a semantic |
| `stop` | `reserved` | 8 | 24 | `untested` | a reserved-bit claim with no positive control in the termination dimension |

**Hypotheses, falsifiers and the gate:** `PRE_REGISTRATION.md` (frozen before any build) and
`PRE_REGISTRATION_A2.md` (frozen before the first gated dispatch, adding Gates A/C/E of
`/RE_EXPERIMENT_PROCESS_CORRECTIONS.md`).
**Results:** `RESULTS.md`. **Machine-readable verdicts:** `analysis/field_verdicts.json`.

## What is new here

1. **The loop-iteration region kind is reached.** `kernels/k_cf206.metal` puts every loop trip
   count in *device memory* and nests the loops, so the compiler can neither unroll nor
   flatten them. The census (`raw/prefreeze/census.json`) confirms `scope_kind == 0x1a` on all
   six loop carriers, alongside `0x21`, `0x25` and `0x29` — and the compiler emits **both**
   documented banks `0x54` and `0x56`.
2. **The memory-ordering dimension is built.** `kernels/k_cl206.metal` spans, on one axis,
   *nothing outstanding at the return* → *load in the callee* → *load in flight across the
   return* → *store→load hazard spanning the return* → *atomic RMW whose result is consumed
   after the return*. `ret.scoreboard` was declined because no carrier had anything to wait on.
3. **The link dimension is built, and the non-leaf return had to be excavated.** Every
   non-leaf callee our compiler emits ends with the 6-byte word `ef 02 54 00 00 50`, which the
   pinned `db.json` **cannot decode**, immediately followed by the non-leaf return
   `8f 12 54 00`. A linear tokenizer walk dies just short of the only occurrences in the whole
   corpus carrying `linkmode == 0x12` — the exact value the leaf-only carriers of the withdrawn
   `ret_luse.linkmode` measurement could never reach. `harness/locate206.py` adds a bounded
   resync so they can be found; the undecodable word is reported as a db defect.
4. **A real `ret_luse` exists in our own code.** `cl_atomic`'s callee ends with
   `8f 12 56 00` — byte+2 `0x56` **and** linkmode `0x12`. That occurrence needs no synthesis
   at all, and it already refutes EXP-0156's `v & 7 == 4` accepted-set rule from our own
   compiled bytes.
5. **A mid-program terminator is constructed, because none occurs naturally.** The census
   refuted this experiment's own H6 premise: the callee lives in its own symbol region, so
   `_agc.main` ends at its `stop` and `follows_code` is False at every natural stop. One is
   therefore built by overwriting the 4-byte `frame_marker` — an instruction EXP-0179
   established is **optional** — with `0e 00 00 00`, changing exactly one thing: whether a
   terminator is present.

## Method

1. `analysis/census.py` — **pre-freeze calibration, cited by no verdict.** Compiles every
   carrier with our own `shdump`, carves every symbol region of the shader `__text` section,
   and locates each target instruction by two independent methods.
2. `analysis/gen_arms.py` — applies the frozen selection rule of `PRE_REGISTRATION.md` §4 and
   attaches each arm's competing semantic models from `analysis/models206.py`.
3. `analysis/freeze_contract.py` — hashes every authored input and pinned tool into
   `CAPTURE_CONTRACT.json`. The repo revision is **recorded, not gated**.
4. `harness/verify_remote.py` — a **separate** step (never chained behind a push) that
   compares every remote file hash against the frozen contract.
5. `run.py` — sweeps on the neo with no abort path and no hang budget; poisoned read-back,
   integrity sentinel, OS fault-classification string, majority-of-3 on every non-OK case,
   the pinned tokenizer's opinion of the mutated bytes, an **actual-byte ledger** read back
   out of the final dispatched blob, a **five-bucket semantic classification**, and a process
   table sample every 100 cases.
6. `analysis/verdicts206.py` — recomputes every verdict from `raw/` under the frozen gate.
   It runs a **five-case self-test first and refuses to produce verdicts if it fails**.

## Reproduction

```bash
export SSHPASS='...'                                    # SSHPASS only, never in a file
bash harness/sync.sh push
bash harness/sync.sh build
python3 harness/verify_remote.py                        # SEPARATE step; exit 0 required
bash harness/sync.sh shell 'cd ~/agxre/EXP-0206 && python3 -B analysis/census.py'
bash harness/sync.sh shell 'cd ~/agxre/EXP-0206 && python3 -B analysis/gen_arms.py'
bash harness/sync.sh pullharness
python3 analysis/freeze_contract.py
bash harness/sync.sh push ; python3 harness/verify_remote.py
bash harness/sync.sh shell 'cd ~/agxre/EXP-0206 && python3 -B run.py --run-id g17p_20260830_run03 --order forward'
bash harness/sync.sh shell 'cd ~/agxre/EXP-0206 && python3 -B run.py --run-id g17p_20260830_run04 --order reversed'
bash harness/sync.sh pull
python3 analysis/verdicts206.py raw/g17p_20260830_run03 raw/g17p_20260830_run04
python3 ../../tools/agx-isa/wave_audit.py .
```

## Retained, never reused, cited by no verdict

* `raw/prefreeze/census.json` — the pre-freeze census (calibration).
* `raw/pilot_20260830_p01/` — the 434-case pilot (calibration).
* `raw/g17p_20260830_run01/` — a gated run **killed at 152 cases** when it measured
  1.756 s/case against the pilot's 0.234 s/case. It is left exactly as it is, is never topped
  up, and its id is never reused. Why it was killed, and the arm reduction it forced, are
  contract amendment 5 in `CAPTURE_CONTRACT.json` and §A2.1 of `PRE_REGISTRATION_A2.md`.
* `raw/smoke_20260830_s01/` — a 36-case smoke test of the amended harness (calibration).

## Clean-room attestation

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected:      kernels/k_cf206.metal and kernels/k_cl206.metal -- authored by us --
                       and the AGX bytes the public Metal runtime compiled from them
Apple binary introspection: NONE
Reproduction:          the block above
Evidence:              raw/<run_id>/sweep.jsonl, raw/<run_id>/procs.jsonl,
                       raw/<run_id>/env.json, raw/prefreeze/, CAPTURE_CONTRACT.json
```

No Apple binary is disassembled, decompiled, symbol-dumped or otherwise introspected anywhere
in this experiment. Every byte inspected or mutated is the compiled form of MSL in `kernels/`,
written by us.
