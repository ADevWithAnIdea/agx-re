# EXP-0207 — G17P fragment / raster / system-value fields: seven blockers, six instructions

**Target:** Apple A18 Pro / **G17P** (`applegpu_g17p`, `AGXAcceleratorG17P`, 5 cores,
macOS 26.6, Metal family Apple9). **Nothing ran on the M4**, which is the repo host and
analysis machine only.

```text
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/*.metal (authored by us) and the AGX bytes the public
                  newLibraryWithSource: API compiled from them
Apple binary introspection: NONE
Reproduction: harness/sync.sh push ; python3 harness/verify_remote.py ;
              harness/sync.sh build ;
              python3 harness/run207.py --run-id <id> --out-root raw [--order reverse] ;
              python3 analysis/verdicts.py ; python3 analysis/census.py ;
              python3 analysis/covary.py ; python3 ../../tools/agx-isa/wave_audit.py .
Evidence: raw/<run_id>/sweep.jsonl + raw/<run_id>/payloads.jsonl (append-only),
          raw/prefreeze/ (census + pilots), analysis/field_verdicts.json
Pinned toolchain: pinned/{isadb.py,db.json,agxparse.py,mesh_extract.py}, sha256 in
                  CAPTURE_CONTRACT.json, resolved by absolute path with a hard exit if absent
```

## The question

Seven fields are the last thing standing between six instructions and emitter-grade status,
and **every one of them has already been refused once, on a recorded basis**:

| field | prior status | the recorded reason it failed |
|---|---|---|
| `frag_color_store.store_mode` | `single-template-inference` | inert on 8 arms / 7 carriers; then declined again by EXP-0188 **without device time** ("needs a fragment-stage render harness") |
| `iter.b9` | `single-template-inference` | inert on 6 arms / 6 carriers; same EXP-0188 decline |
| `vtx_coord_xform.operand` | `untested` | **withdrawn the same morning**: 1 distinct VALID payload across 817 legal values — the movement was 987 `no_draw` + 39 `fault`, a hazard map |
| `get_sr.form` | `untested` | promoted by the orchestrator, **promotion withdrawn**: all 12 records `oracle: null`, scoring the unmutated baseline `wrong_value` |
| `get_sr.dst_hi` | `untested` | withheld INERT-SINGLE: 8 values, **one** arm, 0 moved |
| `mesh_out_src.sel` | `tokenization-only` | declined on a 0-occurrence census over 24 carriers — **all 24 COMPUTE kernels, for a MESH-STAGE-ONLY op** |
| `dev_scoreboard_fence.scope_flag` | `corpus-correlation` | synthesised into a program that "has no scoreboard/ordering observable" |

So the question is not "is field X inert". It is: **what dimension does each field plausibly
control, can a carrier be built that differs in that dimension _and demonstrates it can
differ_, and does the field move there with more than one distinct VALID payload?**

## Method

`PRE_REGISTRATION.md` is frozen (three numbered amendments, all before any gated capture;
superseded contracts retained in `raw/prefreeze/`). It names, per field, the dimensions
already spanned by earlier experiments — so none is repeated — and the new dimension built
here. `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` is normative and its Gates A/B/C/E and
six-axis verdict shape are implemented in `analysis/verdicts.py`, which recomputes every
verdict from `raw/` and refuses to write anything if its own self-test cannot make the gate
say "no".

New machinery built for this experiment:

* `harness/rendersweep207.m` — the render sweep runner, extended with the pipeline-state
  dimensions these fields need: attachment **format**, **blend** (including **dual-source**),
  a **depth** attachment, a poisoned device read-back for **per-sample** observation, and a
  byte-exact `raw` observable so the comparison does not go through floats.
* `harness/meshsweep207.m` — **a mesh render sweep runner.** This is why
  `mesh_out_src.sel` had never been dispatched by anyone: no runner in this repository
  could execute a spliced **mesh** pipeline.
* `harness/shdump207.m` / `shdump_mesh207.m` — archive builders whose pipeline key matches
  what the runners render with, so `FailOnBinaryArchiveMiss` cannot silently substitute a
  different program.
* `harness/run207.py` — capture driver: per-case **actual-byte ledger** (Gate A),
  content-addressed payload store, per-child reader thread (DEF-0178-1), no per-field hang
  budget (rule 3c), reversed case order for the confirmation run (Gate E).

Results, with the exact numerators and denominators and the six axes, are in `RESULTS.md`
and `analysis/field_verdicts.json`.
