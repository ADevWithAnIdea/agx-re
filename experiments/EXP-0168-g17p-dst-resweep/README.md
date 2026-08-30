# EXP-0168 — the `dst` re-sweep, and the twelve instructions that are one field away

**Target: Apple A18 Pro / G17P** — `applegpu_g17p`, `AGXAcceleratorG17P`, 5 GPU
cores, macOS 26.6, Metal family Apple9. Every result here is labelled
`target: G17P` and is **direct** evidence for the documentation target.

```
Clean-room provenance: OWN-SHADER + HW-PROBE
  (+ PUBLIC for IEEE-754 / the MSL conversion definitions, used ONLY to write
   host oracles, never to source an Apple9 encoding fact)
Inputs inspected: kernels/*.metal (authored by us) and the AGX machine code the
  public newLibraryWithSource: / MTLBinaryArchive API compiled FROM THEM; plus
  this repository's own committed raw observations from EXP-0138, EXP-0140,
  EXP-0141, EXP-0144, EXP-0147, EXP-0155, EXP-0163 and EXP-0164.
Apple binary introspection: NONE
Reproduction: see "Reproduce" below
Evidence: raw/prefreeze/** (calibration, never evidence);
          raw/<run id>/sweep.jsonl (gated, append-only, one JSON object per
          case, flush + fsync per record)
```

## The question

EXP-0164 re-derived every emitter-grade field in `tools/agx-isa/validation.json`
from committed `raw/` — 728,387 per-value records across 53 experiments — and
withdrew the emittability headline from 79/166 to **41/166**, downgrading 122
fields to `untested`. It also named the cheapest way back up, and that is this
experiment: the field NAME `dst` blocks **13 instructions**, and **twelve more
instructions are exactly ONE field away** from keeping emittable status.

The fields were withheld because the old evidence was **underpowered**, not
because it was absent. So the question is not "does the field work" but:

> **Is there a carrier that can express what the field controls — and can the
> carrier prove it had the power to see a difference before we conclude
> anything?**

## Why the old evidence was underpowered — three defects, each measured

This is the substance of the experiment, so it is stated up front.

**1. The observable co-varied with the field.** EXP-0140's `uniform_mov.dst`
sweep built its read-back as `device_store(..., data_reg=D)` where `D` is the
very dst being swept (`EXP-0140/harness/cases.py:92-100`). Field and observable
move together, so a **correct** hardware result is a constant observed vector by
construction — the audit's "16 values dispatched, 0 moved" was the *passing*
outcome of a test that could return nothing else. Only 2 output words were
compared, and the wider 12-register scan ran at one dst value (D=3).

**2. One verdict was fanned out to five descriptors that behave differently.**
The `reg_move_*` family plus `uniform_mov` is ONE 4-byte instruction
(EXP-0087/EXP-0140) whose byte+2 is a form selector. EXP-0140 swept `dst` at ONE
form and `analysis/verdicts.py:327` copied that single verdict verbatim onto all
six descriptor names — though its own probe shows c0/c2var `silent_zero`, c9
`wrong_value` (returning byte+1 verbatim), cb `wrong_value` and only c1 `ok`.
There is **no dst × form cross-product anywhere in that matrix.**

**3. "Two carriers" were often one.** EXP-0144's `F` and `W` are *arm letters*
over the same compiled program. EXP-0155's `iter_at@cent1_0/_1` and
`fcp@pack0/pack1` are two **occurrences of one instruction inside one program**,
at one sample count and one attachment format. EXP-0147's `vtx_out_pos` carrier
was **single-varying**, while `slot` selects *which varying*.

The canonical proof that this matters is `iter_at.loc`: inert on every EXP-0155
arm, and it **moves 128/256 at `rasterSampleCount = 4`** (EXP-0163) — because at
one sample the centroid, the sample point and the pixel centre are the same
point. **Two carriers identical in the dimension the field controls are one
carrier.**

## What this experiment does about it

- **The observable never co-varies with the field.** Every STYLE-S case dumps all
  16 GPRs through an identical store list, and the verdict is a function of
  *which slot changed*.
- **Every arm names the DIMENSION it varies**, and arms that pair must differ in
  it. `casematrix.py`'s arm table carries `dim` and `why` per arm.
- **`dst` is swept as a cross-product with the form selector**, which is the
  measurement that was actually missing.
- **Every arm proves detection power first** with a liveness ladder on a
  known-live control of the same instruction, each with the citation that makes
  it known-live. An arm whose ladder is flat is **discarded**, not reported as
  inertness.
- **Byte-mate controls**: only the field's own bits are mutated, and the
  complementary bits of the same byte are swept separately so a reader can see
  whether movement could have come from a neighbour.
- **Run integrity is separate from outcome.** A read-back that is entirely
  poison, or whose PRE / POST / tail sentinel failed, is `validity != valid` and
  is **re-run — never recorded as a silent zero**. EXP-0160 saw 25 dispatches
  report `STATUS OK` and write nothing at all, with no victim string.

## An offline result, independent of the sweep

`analysis/rescore_0144.py` re-derives EXP-0164's cross-run gate from EXP-0144's
committed raw, comparing only runs that **actually dispatched** the value.

| field | audit said | best measured pair | common | agree |
|---|---|---|---|---|
| `pack_convert.b7` | 2.73% | run05 vs rv01 | 256 | **100.00%** |
| `cvt_f2i.dst` | 82.42% | run02 vs rv01 | 225 | **99.56%** |
| `cvt_f2i.b9` | inert / 1 carrier | run03 vs rv01 | 256 | **100.00%** |
| `unpack_convert.dst` | 25.78% | run05 vs rv01 | 192 | 98.96% |
| `cvt_f2h.op` | 91.41% | run01 vs run04 | 256 | 98.44% |

Cause: EXP-0164 picks the two gated runs with the most distinct attributed
values, **ties broken alphabetically** (`audit.py:78-80`), which selects `run03`
— a capture EXP-0144 itself disowns. run03 holds **17 measured cases and 248
placeholders** for `pack_convert.b7`, and run03/run04 hold **0 measured and 272
placeholders each** for `unpack_convert.dst`. The placeholders carry
`outcome:"hang"`, and EXP-0164 treats only `{invalid_run, victim, skipped}` as
contamination, so they were scored as observations.

**This is a re-scoring repair, not a third-gated-run repair, and it costs no
device time.** It does not promote anything: the underlying data is M4/G16G.

## Method

Two carrier styles, because one does not fit everything:

- **STYLE-S (SYNTH+LIFTED)** — the whole `_agc.main` of a neutral carrier is
  replaced by a program we assembled from `tools/agx-isa`'s own field rules
  (seeds → PRE sentinel → the block under test → high-register probe → 16-GPR
  dump → POST sentinel → stop), with the instruction under test **lifted
  byte-for-byte** out of the compiled form of our own MSL. Read-back: 104 words,
  poisoned with `0xDEADBEEF`, including a 28-word tail region no store ever
  targets.
- **STYLE-P (IN-PLACE)** — for control-flow and memory instructions, whose branch
  displacements and buffer bindings do not survive being moved: one field is
  mutated where it already sits inside our own compiled probe kernel and THAT
  kernel is dispatched with real inputs. For `if_push` every divergent region
  contains a **store**, which cannot be if-converted, so against a poisoned
  output buffer the per-lane × per-region slot pattern **is** the execution mask.

Full hypotheses, refuters, carriers, ladders and thresholds:
**`PRE_REGISTRATION.md`**; frozen hashes and the raw schema:
**`CAPTURE_CONTRACT.json`**; the render/vertex arm: **`RENDER-DESIGN.md`**.

## Reproduce

On the repo host (no device):

```sh
cd experiments/EXP-0168-g17p-dst-resweep
python3 analysis/rescore_0144.py            # the offline re-scoring, no GPU
python3 work/mkfake_anchors.py              # a TEST FIXTURE, never evidence
python3 harness/dryrun.py                   # builds every arm's program, no GPU
```

On the target (`~/agxre/EXP-0168/`), with `SSHPASS` exported by the caller and
written to no file:

```sh
export SSHPASS='...'                        # never committed, never logged
harness/sync.sh push
harness/sync.sh build                       # rebuild shdump + agxrun_persist there
harness/sync.sh frozen                      # pin the db.json the HW ran against
harness/sync.sh sh 'cd agxre/EXP-0168 && python3 harness/anchors.py'
harness/sync.sh sh 'cd agxre/EXP-0168 && python3 harness/casematrix.py'
harness/sync.sh sh 'cd agxre/EXP-0168 && python3 harness/smoke.py'    # pre-freeze
# gated runs (quiet window, gpuwatch alongside):
harness/sync.sh sh 'cd agxre/EXP-0168 && python3 harness/gpuwatch.py --run g17p_20260830_run02 &
                    python3 harness/run.py --run g17p_20260830_run02 --order forward'
harness/sync.sh sh 'cd agxre/EXP-0168 && python3 harness/run.py --run g17p_20260830_run03 --order reverse'
harness/sync.sh pull g17p_20260830_run02
harness/sync.sh pull g17p_20260830_run03
python3 analysis/verdicts.py --runs raw/g17p_20260830_run02 raw/g17p_20260830_run03
```

## Scope, and what is deliberately NOT done

- **`matrix_mac.dst` is NOT attempted** — it needs a simdgroup-matrix carrier and
  it is one of *twelve* withheld fields on `matrix_mac`, so repairing `dst` alone
  cannot recover the instruction. Reported as NOT ATTEMPTED, never as inert.
- **`iter_at.grp` is bounded by a descriptor defect before any sweep touches
  it**: `db.json` declares it 8 bits at `start=0` while the descriptor's own
  match constant `[0, 7, 47]` pins bits 0..6, so only bit 7 is free and every
  other value is a *different instruction*. That is also why it hangs.
- **`db.json` is not edited** (EXP-0165 owns it); corrected models go under
  `db_defects` in `analysis/field_verdicts.json` with their evidence.
- **`validation.json`, `docs/` and `PROVENANCE.md` are not edited, and nothing is
  committed** — the orchestrator reviews and commits.
- The neo SSH password is held in-session only and appears in **no file** in this
  repository, committed or not. **[CORRECTED 2026-08-30 BY THE ORCHESTRATOR: this claim was FALSE when written.** A repo-wide sweep found the literal password committed in FIVE tracked files, seven occurrences — `EXP-0003-hw-testbed/run_all.sh` (x2) and `sshto.py`, `EXP-M5-04-capabilities/run.sh`, and `M5-DELTA-SUBAGENT-BRIEF.md` (x2), plus `EXP-0184/PROGRESS.md` which made this same false claim while writing the password verbatim on the line asserting it. The scope of the check was the EXPERIMENT TREE, not the repository, and the conclusion was stated repo-wide. All were cleaned to `sshpass -e` with the `SSHPASS` env var; **the credential remains in git history and only rotating the device password remediates it**.]

## Layout

```
PRE_REGISTRATION.md     hypotheses, refuters, carriers, the frozen gate
CAPTURE_CONTRACT.json   frozen hashes, raw schema, timeouts, safety budgets
RENDER-DESIGN.md        the fragment/vertex arm (part of the pre-registration)
PROGRESS.md             append-only milestone log
harness/                isa_helpers, anchors, casematrix, sweeprun, run,
                        smoke (pre-freeze), gpuwatch, dryrun, sync.sh,
                        gfrun3.m + runner3.py + render* (render arm)
kernels/                probes.metal, carrier_dag.metal, r_*.metal (all ours)
analysis/               rescore_0144.py (offline), verdicts.py (the gate),
                        render_verdicts.py, field_verdicts.json
raw/prefreeze/          anchor extraction + smoke; NEVER evidence
raw/<run id>/           gated, append-only
work/                   scratch, the pinned db.json snapshot, the dry-run fixture
```
