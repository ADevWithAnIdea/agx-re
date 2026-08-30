# EXP-0157 — the MISC family on G17P: ray-query, SFU-adjacent, half-coordinate, mesh, fence, `op04`

**Target: Apple A18 Pro / G17P** (`Mac17,5`, `AGXAcceleratorG17P`, arch `applegpu_g17p`,
5 GPU cores, macOS 26.6 build 25G5043d, Metal family Apple9).
Every result is labelled **`target: G17P`**.

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: our own MSL (kernels/*.metal), the AGX bytes those compile to on
  G17P, and the outputs the GPU produced from them.
Apple binary introspection: NONE
Reproduction: see "Reproduction" below
Evidence: raw/<run_id>/{00_env.json,00_build.json,00_cases.json,00_manifest.json,
  01_progress.json,sweep.jsonl}
```

## Question

Twenty `db.json` descriptors in the MISC cluster have no emitter-grade field on the
documentation target. For each: can an emitter choose arbitrary values and get the
documented behaviour on G17P, and where it cannot, **is the blocker the hardware, the
descriptor, or our testbed?**

`n2_op6` · `n2_op8` · `n2_op10` · `n3_mov` · `coord_madf` · `sr_read_wide` · `h_coord_hi` ·
`h_coord_hi_ext` · `mesh_out_src` · `op04_len8` · `scoreboard_fence` ·
`compute_fence_scoped` · `rtq_pred` · `sfu_marker` · `rtq_dualsrc` · `rtq_state_move` ·
`ray_move` · `ray_move_copy6` · `ray_move_zero6` · `ray_move_zinit`

## Hypotheses and method

Frozen in `PRE_REGISTRATION.md` (H0–H6) with `CAPTURE_CONTRACT.json`. In brief:

* **H0 — the testbed.** `agxrun_persist` binds `MTLBuffer`s only, so EXP-0146's ray-query
  kernel executed but never traversed and *every* ray-query getter was dead on the output
  path. Adding a `setAccelerationStructure:` path should make the whole cluster sweepable.
* **H1–H5** — one hypothesis per descriptor cluster, each with a named refuter.
* **H6 — the fences.** Promotion is **pre-emptively declined** unless a litmus is
  demonstrated that detects a spliced-out barrier on this target, in this carrier.

Sweeps follow `experiments/FIELD-SWEEP-PROTOCOL.md`: dense over all 2^w values for
`w <= 8`; boundaries + powers of two + interior samples above that; poisoned read-back;
an integrity sentinel on a path independent of the instruction under test; the OS
fault-classification string on every non-`ok` case; and no `fault` verdict from a single
observation.

**Anchors** are resolved on the target by a resync tokenizer (`analysis/resync.py`) and
then have to pass **two liveness controls** (`byte0 ^= 1`, and erase-to-zero) before any
field of them is swept. An anchor that fails both is recorded `inert_or_unreached` and
nothing at it is promoted.

## Layout

| path | what |
|---|---|
| `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json` | the frozen contract |
| `harness/agxrun_persist_as.m` | **the testbed fix**: `agxrun_persist` + an `MTLAccelerationStructure` build-and-bind path |
| `harness/{carriers,cases,run,runner_as,anchors,isa_helpers}.py` | sweep harness |
| `harness/run_lm.py` | arms L/M/N — the **hardware length probe** |
| `kernels/k_rq_prim.metal`, `k_rq_inst.metal`, `k_rq_getters.metal` | authored ray-query carriers |
| `kernels/k_provoke.metal` | authored provocations for `n2_op8` / `coord_madf` / `h_coord_hi*` |
| `analysis/resync.py`, `analysis/verdicts.py` | resync tokenizer, verdict builder |
| `raw/` | append-only captures |
| `RESULTS.md` | observations, interpretation, limitations, verdict |

Reused with citation: `harness/{anchors,isa_helpers}.py` and the shape of `harness/run.py`
from **EXP-0153**; `kernels/k_sfu_sin.metal`, `k_roundmodes.metal`, `k_u64eq.metal`,
`k_zext16.metal`, `k_sfu_mix.metal` from **EXP-0146**; `kernels/c_hcoord.metal` from
**EXP-0145**; `kernels/carrier_synth.metal`, `carrier_dag.metal` from **EXP-0141/0139**
via EXP-0153.

## Reproduction

On the neo (`~/agxre/EXP-0157`), with `AGX_TOOLS=$HOME/agxre/tools`:

```sh
bash harness/build.sh
python3 -B harness/run.py --run-id g17p_run01 --bin-dir bin --work work/w1 \
        --raw raw/g17p_run01 --arms R,S,H --max-anchors 12 --sweep-anchors 1
python3 -B harness/run.py --run-id g17p_run02 --bin-dir bin --work work/w2 \
        --raw raw/g17p_run02 --replay raw/g17p_run01/00_cases.json
LENMAP_CANDS=3 LENMAP_BYTES=0,1,2,3,4,5,6,7 \
python3 -B harness/run_lm.py --run-id g17p_lenmap01 --bin-dir bin --work work/wl \
        --raw raw/g17p_lenmap01 --candidates work/op04_candidates.json --arms N,L,M
```

Then, in this repository:

```sh
python3 analysis/verdicts.py raw/g17p_run01 raw/g17p_run02
python3 analysis/lenrule.py raw/g17p_lenmap01
```

## Clean-room statement

Every byte inspected or spliced is the compiled form of MSL **we wrote**, or bytes emitted
by `tools/agx-isa`'s assembler from our own field values. The acceleration structure is
built from triangle vertices **we authored**. No Apple binary was disassembled,
decompiled, symbol-dumped, strings-scanned, or debugged. `tools/agx-isa/db.json`,
`validation.json`, `docs/**` and `PROVENANCE.md` were **not modified**;
`tools/agxtest/agxrun_persist.m` was **not modified** (the AS path lives in this
experiment's own derived copy so that concurrently-running sibling experiments keep
building).
