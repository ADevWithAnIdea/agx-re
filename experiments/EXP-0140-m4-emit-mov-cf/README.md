# EXP-0140 — M4: making the MOV and control-flow instruction families EMITTABLE

**Target: local Apple M4 / G16G only.** No SSH, no A18 Pro, no M5, no `macvdmtool`.
**Status board row:** P0.6 / DRV-ISA-01 (emitter-grade ISA fields).

## Question

23 `db.json` instructions are decodable but not emittable, blocked by 51 fields that are not
`hardware-run`/`isolated-byte-diff`. Can an emitter put an **arbitrary** value in each of those
fields and get the documented behaviour on real hardware? (`docs/evidence-classification.md`
§2: "`hardware-run` requires that *arbitrary operands executed*, not that the instruction
executed.")

## Hypotheses, coverage, confounders, safety, contamination defences

See **`PRE_REGISTRATION.md`** — frozen before any gated run.

## Method

Four authored carriers (`kernels/`); two whole-`_agc.main` replacements built instruction-by
-instruction through `tools/agx-isa`'s read-only `isadb.assemble`, and two in-place byte
patches of a single 4-byte select instruction inside its own natural compile:

| carrier | technique | families |
|---|---|---|
| `carrier_uni.metal` | generated program spliced over the whole `_agc.main`; four `constant int&` arguments preload the **uniform file with values we bind** | `mov_imm`, `get_sr`, `uniform_mov`, `reg_move_*` |
| `dsel5.metal` (EXP-0010) | in-place patch of the 4-byte `sel` at `+0x18` | `sel` |
| `gsel4.metal` (EXP-0010) | in-place patch of the 4-byte `psel` at `+0x0A` | `psel` |
| `carrier_cf2.metal` | EXP-0090/EXP-0112's HW-validated CF skeleton, one named field overridden per case, **displacements never recomputed** | `if_push`, `if_push_pred`, `jump`, `jump_cond`, `pop_reconverge`, `ret` |

Every case carries a host-computed oracle; exploratory values inside a dense sweep are judged
against the carrier's own **baseline** vector (an inertness test) with no prediction claimed.
Each group carries a pre-registered falsifier designed to fail.

## Commands

```sh
cd experiments/EXP-0140-m4-emit-mov-cf
sh harness/build.sh work/bin                # our own tools/shdump + tools/agxtest sources
python3 harness/baseline.py                 # re-derive every carrier fact (no GPU)
python3 harness/cases.py                    # print the frozen case matrix (no GPU)
python3 harness/run.py --run m4_20260828_run01
python3 harness/run.py --run m4_20260828_run02
python3 analysis/verdicts.py                # -> analysis/field_verdicts.json + summary
```

## Layout

```
PRE_REGISTRATION.md   frozen contract (hypotheses, coverage, confounders, defences, budgets)
harness/isa_helpers.py  instruction builders (all through isadb.assemble) + the CF skeleton
harness/cases.py        the FROZEN case matrix (pure, no GPU)
harness/baseline.py     re-derives carrier main lengths / base_slots / token streams (no GPU)
harness/run.py          capture driver (replication, sentinels, hang budgets, baseline checks)
kernels/                our own MSL carriers
raw/<run_id>/           append-only evidence: 00_inputs.json, sweep.jsonl, 01_summary.json
analysis/               repeatable analysis -> field_verdicts.json, cross-run gate
work/pilot/             DISCLOSED, NON-GATED pilot scripts that informed the frozen contract
RESULTS.md              observations vs interpretation, tested range, limitations, verdicts
```

`work/` is scratch and is not evidence. The pilots in `work/pilot/` are disclosed because their
findings became pre-registered predictions (notably the uniform-file map and the `sel`/`psel`
byte roles); the gated runs are what test them.

## Clean-room statement

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected: our own MSL (kernels/*.metal) and the machine code compiled from it;
                  instruction bytes assembled by our own tools/agx-isa (read-only use)
Apple binary introspection: NONE
Reproduction: the commands above
Evidence: raw/<run_id>/sweep.jsonl (+ 00_inputs.json hashes), analysis/field_verdicts.json
```

No Apple binary was disassembled, decompiled, symbol-dumped, strings-scanned or debugged. The
only machine code inspected or spliced is the compiled form of MSL we wrote.
