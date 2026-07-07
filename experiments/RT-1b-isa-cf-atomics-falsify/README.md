# RT-1b: red-team falsification of control-flow / calls / memory / atomics (2nd overlapping ISA pass)

- **Date:** 2026-07-07
- **Clean-room category:** OWN-SHADER (our MSL → our compiled bytes → splice → run on real A18 Pro) + PUBLIC (isadb).
- **Role:** RED-TEAM verifier, 2nd overlapping pass on the ISA cluster. Assume the
  control-flow / memory / atomic findings may be subtly wrong; run falsification tests to break them.
- **Claims under test:** `docs/isa/README.md` — control-flow, memory, atomics, barrier/interlock
  sections (note: just-corrected memory index reg = **byte+5**). Also `tools/agx-isa/db.json` census.
- **Device:** A18 Pro / G17P, macOS 26.6, `~/cleanroom_work/rt1b/`.

## Independent harness (different from RT-1a / RT-1a-FIX)
Both prior passes drove the **persistent** runner (`agxrun_persist`, one long-lived `MTLDevice`,
`newLibraryWithURL` reload). RT-1b uses my own **one-shot** runner `harness/rt1b_run.m`: a **fresh
`MTLDevice` per dispatch**, so there is no in-process code-memoization surface at all — if RT-1a's
persistent-reload path had a subtle memoization bug, this harness would disagree. Splice locations are
found by **tokenizing with the ISA DB** (`harness/rt1b.py` → `isadb.decode_one`), not hardcoded byte
offsets, so the location method is also independent. Kernels (`kernels/*.metal`) use different ramps,
indices, and combine-expressions than RT-1a.

## Method
For each claim: compile our own MSL (`shdump`) → locate the target instruction in `_agc.main` by
tokenizing → splice one field → run on the real GPU (`rt1b_run`, fresh device) → read outputs →
compare. Semantics cross-checked against CPU references. Clean-room legal: only our own compiled
shader bytes are inspected/spliced; no Apple binary is disassembled.

## Procedure (reproduce on device)
```sh
cd ~/cleanroom_work/rt1b
clang -fobjc-arc -framework Metal -framework Foundation -o shdump shdump.m
clang -fobjc-arc -framework Metal -framework Foundation -o rt1b_run rt1b_run.m
python3 t_mem.py      # byte+5 index / byte+6 inert / byte+1 space
python3 t_memoff.py   # immediate index-offset field (+ signed offset)
python3 t_memvec.py   # vector loads + threadgroup space
python3 t_cf.py       # predication / select / backward jump / adversarial CF
python3 t_call.py     # CALL target formula / off40 / nested / recursion / spill
python3 t_atom.py     # atomic op@byte+12 / cmpxchg / device-vs-tg / barrier race
python3 t_stress.py   # big kernel: semantics vs CPU ref
python3 t_census.py   # alignment-preserving tokenization census
```

## Raw results
`raw/t_*.log` (test outputs), `raw/enc_*.txt` (encoding dumps). Verdicts in `RESULTS.md`.

## Files
- `harness/rt1b_run.m` — independent one-shot runner (fresh device per dispatch).
- `harness/rt1b.py` — splice/run driver (DB-tokenizer-based instruction location).
- `harness/t_*.py` — one driver per item; `harness/dbg_*.py` — encoding dumps.
- `kernels/*.metal` — our own MSL (mem / cf / call / atom / stress).
