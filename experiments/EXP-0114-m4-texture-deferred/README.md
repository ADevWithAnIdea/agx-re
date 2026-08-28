# EXP-0114 m4-texture-deferred

Closes as many of EXP-0106's DEFERRED `TEX-*` items as this contract's evidence allows,
following the successor specs EXP-0106 wrote, prioritized per dispatch: **TEX-15** (texture
selector field width) first, then the raw-descriptor-splice half of **TEX-16**, then EXP-0094's
OPEN gradient-operand register field. The remaining eight dispatched items (TEX-01, TEX-12,
TEX-19, TEX-20, TEX-21, TEX-22, TEX-26, TEX-27, TEX-28) are explicitly DEFERRED with named
successor reasons in `PRE_REGISTRATION.md` §0 — none silently dropped.

Question / hypothesis / method: see `PRE_REGISTRATION.md`.
Observations, interpretation, verdicts: see `RESULTS.md`.
Milestone log: see `PROGRESS.md`.

Clean-room category: **OWN-SHADER + PUBLIC**. All MSL is ours (`kernels/*.metal`); all AGX bytes
inspected or spliced are the compiled form of that MSL, extracted with the project's own public
Mach-O/Metal-fat parser (`tools/shdump/agxparse.py`, used read-only); all dispatch/splice harnesses
(`harness/texsplice.m`, `harness/gradsplice.m`, `harness/case_runner.py`) are authored fresh for
this experiment. No Apple binary is disassembled, decompiled, or otherwise introspected.

## Reproduce

```sh
python3 gen_contract.py                              # regenerate CAPTURE_CONTRACT.json (idempotent)
python3 verify.py --selftest                          # state-agnostic self-test
python3 verify.py --seqtest                            # gate-sequence state machine
python3 run.py --run-id m4-20260828d-run01 --execute   # capture run 1 (own process per case)
python3 run.py --run-id m4-20260828d-run02 --execute   # capture run 2
python3 analysis/analyze.py --write                    # derive analysis.json, check repeat-exact
python3 verify.py --captured                            # final post-capture gate
```

## Layout

- `kernels/` — authored MSL: `read_n{2,4,8,16,32,64,127}.metal` + `read_sparse3.metal` (TEX-15/16
  texture-selector census), `gradpair{,2}_{A,B}.metal` (gradient-operand differential pairs).
- `harness/case_runner.py` — per-case worker (own process per case): compiles/extracts/scans for
  `diff` cases; compiles/splices/dispatches for `splice_tex`/`splice_grad` cases.
- `harness/texsplice.m`, `harness/gradsplice.m` — own compute/render splice-and-dispatch runners
  (texture-binding-capable siblings of `tools/agxtest/agxrun.m`/`agxrender.m`, which do not
  support texture or mip-chain binding).
- `analysis/analyze.py` — derives `analysis.json` from the two raw captures; checks expectations
  against `CAPTURE_CONTRACT.json` and repeat-exactness between runs.
- `run.py`, `verify.py`, `gen_contract.py`, `CAPTURE_CONTRACT.json` — capture/gate apparatus.
