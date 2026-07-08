# CMD-8 — Threadgroup rounding + CDM occupancy bit23 (local Apple M4)

**Clean-room:** OWN-SHADER (our own MSL compiled at runtime; our own shader's own `__GPU_METADATA`) +
DATA-TRACE (our own command-buffer bytes via `iotrace`). No Apple binary disassembled.

**Device:** local **Apple M4** (10-core GPU, Metal 4) — **not** the A18 Pro. CDM BO is at the same VA
`0x100000b0000` with the same record layout; all numeric thresholds flagged **A18-CROSS-CONFIRM**.

## Two questions (from `docs/cmdstream/README.md`)
1. **tg field @ +0x1c/+0x20/+0x24 rounding rule.** Doc claimed "each axis rounded up to a power of two,
   product ≥ 32." → **FALSIFIED.** It is the physical launch threadgroup size: **verbatim** for single
   groups and for kernels with a barrier / threadgroup memory (`tgmem`); Metal *repacks* barrier-free
   kernels for occupancy (an opaque heuristic, neither pow2 nor mult-32). Driver should emit verbatim.
2. **CDM cfg word @ +0x00 bit23 = register/occupancy tier.** Doc interpolated "clear ≤11 / set ≥12 GPRs."
   → **FALSIFIED.** bit23 is a single-bit 2-tier flag == presence of `__GPU_METADATA` field-32; it tracks
   **peak** register pressure, not field-0 GPR count (f0=8 and f0=9 each occur clear AND set), and flips
   at ~8–10 peak GPRs — nowhere near 12.

See **`RESULTS.md`** for full tables, evidence, and corrected doc statements.

## Files
- `cvar.m` — parametric compute dispatcher (added `--srcfile PATH` to dispatch arbitrary MSL, nbuf=2).
- `iotrace.c`, `cdmread.py`, `cdmraw.py`, `bodiff.py`, `dumpscan.py` — harness (copied) + full-record dumper.
- `shdump.m`, `agxparse.py` — our-own-shader compile + `__GPU_METADATA` GPR-footprint extractor (copied).
- `gprmeas.py` — generates ladder kernels, measures GPR footprint (field-0) + field-32 presence.
- `run_tg.sh` (single-group), `run_tg2.sh` (multi-group + discriminators), `run_tg3.sh` (fine map +
  shader-dependence + grid-dependence) — sub-task 1.
- `run_gpr.py` — GPR ladder → cfg-word/bit23 capture — sub-task 2.
- `caps_*/` — raw CDM BO hex captures (`bo_*va100000b0000_*.hex`), `.out` logs, `.metal` sources
  (pruned to the load-bearing CDM BO; other BOs reproducible by re-running).

## Reproduce
```sh
clang -arch arm64e -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation
clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o cvar cvar.m
clang -fobjc-arc -framework Metal -framework Foundation -o shdump shdump.m
./run_tg.sh ; ./run_tg2.sh ; ./run_tg3.sh      # sub-task 1
python3 run_gpr.py                             # sub-task 2
```
