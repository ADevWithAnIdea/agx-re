# EXP-0167 — G17P generator synthesis, RE-CONFIRMED under isolation

## Question

`EXP-0158` reports **233 of 237** generated programs with **zero copied fields** producing
their exact host-computed oracle on G17P — the direct test of `CLAUDE.md`'s Definition-of-Done
rules 1 and 6. **But its own pre-registered cross-run gate FAILS** (`verify.py --captured`),
its strict figure is **149**, and it ran with 8–12 sibling GPU experiments on the same device.

**Re-measured on a quiet machine, does the 233 survive, and does the gate pass?**

## Method

This experiment changes the **conditions**, not the **artifacts**. `synth.py`, `generator.py`,
`families.py`, `cf.py`, `casematrix.py`, `frozen_pilot.py`, the carriers, the harness and the
pinned `tools/agx-isa` snapshot are copied from EXP-0158 **byte for byte**; the only semantic
edit anywhere is `run.py`'s two run-id strings, so this experiment cannot write into EXP-0158's
append-only `raw/`. Proven before freeze by hashing the built corpus in both trees:

```
EXP-0158  289 programs  sha256(concat hex) = f08d598832ea7bbb5ad90f32a9c52cd6cd9402d3bf9cf52ac6dc047f259e4e87
EXP-0167  289 programs  sha256(concat hex) = f08d598832ea7bbb5ad90f32a9c52cd6cd9402d3bf9cf52ac6dc047f259e4e87
```

Isolation is **not** established by a lock: `~/agxre/gpulease.sh` is a neutralised pass-through
shim as of 2026-08-30 and takes no lock — **EXP-0158's own run03/run04 went through that same
shim**. It is established by the orchestrator quiescing the other device agents, and
**verified** by `harness/gpuwatch.py`, which samples the target's process table every 2 s for
the whole pass and lands in `raw/isolation/` as append-only evidence. That measurement is the
deliverable EXP-0158 could not produce about itself.

The four metrics (M1 strict-pair, M2 matched-everywhere, M3 attributable, M4 cross-run
byte-identity gate), the committed predictions, the pre-committed honest-lower branch, and the
20 named watch programs are frozen in `PRE_REGISTRATION.md` and `CAPTURE_CONTRACT.json`.

## Reproduce

On the target, under `~/agxre/EXP-0167/experiments/EXP-0167-g17p-synthesis-reconfirm/`:

```sh
# isolation evidence -- start BEFORE any device operation, keep it running
nohup python3 -B harness/gpuwatch.py --out raw/isolation/00_prewindow.jsonl \
      --marker EXP-0167 --interval 2.0 --phase prewindow &

# gates (no GPU)
python3 -B verify.py --selftest
python3 -B verify.py --seqtest
python3 -B verify.py --preflight

# gated captures (no lock exists; isolation is verified, not asserted)
python3 -B run.py --run-id g17p-20260830-iso01 --execute
python3 -B verify.py --between-runs
python3 -B run.py --run-id g17p-20260830-iso02 --execute
python3 -B verify.py --captured

# witness-gated 5-repeat re-confirmation (scope: PRE_REGISTRATION section 6.1)
python3 -B harness/reconfirm.py --indices <list> --reps 5 \
      --out work/reconfirm/reconfirm_iso.jsonl --bin-dir work/bin \
      --repo <repo-root> --run-dir work/reconfirm_run

# analysis (no GPU, runs on the repo host)
python3 -B analysis/summarize.py --write
python3 -B analysis/compare.py --write
```

## Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: EXP-0158's own authored generator/emitter/harness code and carrier MSL,
  copied byte-identical (hashes in PRE_REGISTRATION.md section 8); a PINNED, hash-recorded
  snapshot of this repository's own tools/agx-isa isadb; this experiment's own gpuwatch.py
  and compare.py; the target's own process table via /bin/ps.
Apple binary introspection: NONE.
Reproduction: the commands above.
Evidence: raw/g17p-20260830-iso01/, raw/g17p-20260830-iso02/, raw/isolation/,
  work/reconfirm/, analysis/comparison.json
```

## Notes for a reviewer

- `experiments/EXP-0158-g17p-generator-synthesis/` is committed evidence and is opened
  **read-only** here; it is not modified or re-run. Its raw trees are not copied into this
  experiment — `analysis/compare.py` reads them in place.
- No `git commit` — the orchestrator reviews and commits.
