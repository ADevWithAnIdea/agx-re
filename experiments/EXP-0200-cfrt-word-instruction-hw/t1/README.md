# EXP-0187 — `n4_rt_word.dst` on G17P, and a bounded census of three
# tokenization-only opcodes

**Question 1.** Is `n4_rt_word.dst` (byte+1 of `04 <dst> 20 80`, the compact word
emitted in intersection-query traversal setup) a field an emitter may **choose**?
It is the single field of a single-field instruction, so promoting it moves
`n4_rt_word` across the emittable line by itself. EXP-0184 named it the next
target and left the RT carrier proven.

**Question 2.** Can any MSL we author make the G17P compiler emit
`cubearray_coord_const`, `mesh_out_src` or `n4_cf_word` at all? All three were
declined on a measured basis before. This is a **census, not a sweep**: no device
time is spent on a carrier that could not be built, and "N constructs tried, none
emitted it" is the deliverable if none does.

**Hypotheses, refuters, gate, confounders:** `PRE_REGISTRATION.md`.
**Results:** `RESULTS.md`; machine-readable verdicts in
`analysis/field_verdicts.json` and the opcode census in `analysis/census.json`.

**Clean-room category:** OWN-SHADER + HW-PROBE. Every byte spliced, decoded or
inspected is the compiled form of our own MSL in `kernels/`. No Apple binary is
disassembled or introspected. Runs entirely on the A18 Pro / G17P neo; nothing
runs on the M4.

## Layout

```
kernels/k_rq187.metal     8 intersection_query carriers (target 1)
kernels/k_cube187.metal   12 cube / cube-array constructs (census)
kernels/k_cf187.metal     8 divergent-CF / barrier / RT constructs (census)
kernels/k_mesh187.metal   6 mesh-pipeline constructs (census)
harness/                  carriers, occurrence location, safe runner, sync,
                          remote hash verification, the AS-capable runner
pinned/                   hash-pinned db.json / isadb.py / agxparse.py /
                          persistrun.py / saferunner.py / shdump.m /
                          shdump_mesh.m / mesh_extract.py -- resolved by
                          ABSOLUTE path with a hard exit if absent, so nothing
                          resolves through tools/ while siblings edit it
analysis/                 census (both targets), arm generation, the gate
raw/                      append-only evidence; raw/prefreeze is calibration and
                          NO VERDICT MAY CITE IT
```

## Commands (reproduction)

```bash
export SSHPASS='...'                      # SSHPASS only; never in a file
bash harness/sync.sh push
python3 harness/verify_remote.py          # SEPARATE step, exit 0 required
bash harness/sync.sh build
bash harness/sync.sh shell 'cd ~/agxre/EXP-0187 && python3 analysis/census.py'
bash harness/sync.sh shell 'cd ~/agxre/EXP-0187 && python3 analysis/gen_arms.py'
bash harness/sync.sh shell 'cd ~/agxre/EXP-0187 && python3 analysis/census2.py'
bash harness/sync.sh shell 'cd ~/agxre/EXP-0187 && python3 run.py --run-id g17p_20260830_run01'
bash harness/sync.sh shell 'cd ~/agxre/EXP-0187 && python3 run.py --run-id g17p_20260830_run02'
bash harness/sync.sh pull
python3 analysis/verdicts.py raw/g17p_20260830_run01 raw/g17p_20260830_run02
```
