# EXP-0010: control flow + program structure/termination (HW-validated)

- **Date:** 2026-07-06
- **Clean-room category:** OWN-SHADER + HW-PROBE (+ PUBLIC for the applegpu *shape* only)
- **Phase / question:** Phase 1 ISA — how G17P branches, predicates, loops, terminates,
  and how uniforms / buffer base pointers reach registers.
- **Device:** Apple A18 Pro / G17P, SoC T8140, macOS 26.6 (25G5043d), Metal 4 / Apple9.

## Hypothesis
G17P (like other SIMD GPUs) implements simple divergent `if/else`/ternary/early-return by
**predication** (a per-lane execution mask) and uses an actual **jump** only for loops
(backward edge) and larger block skips. The fixed `1ca01006…` preamble is a
get-special-register (thread index); the 64-byte `_agc.main.constant_program` and/or a
preloaded uniform slot supplies buffer base pointers; the trailing `0e000000` is not the
real terminator (EXP-0003).

## Method (clean-room)
OWN-SHADER only. We write control-flow MSL (`gen_kernels.py`, `gen_diff.py`), compile it on
the device with our own `shdump` (`newLibraryWithSource:`), extract `_agc.main` +
`_agc.main.constant_program` with our own `agxparse.py`, and **splice our own compiled bytes
and run them on the real GPU** (`agxrun_persist` + `persistrun.py`, the EXP-0005 persistent
runner). No Apple binary is disassembled or introspected. Differential compilation (vary one
constant) localizes fields; splice-and-observe hardware-validates them.

## Procedure (reproducible)
On the device under `~/cleanroom_work/exp0010/` (tools copied from `tools/shdump`,
`tools/agxtest`, `tools/agx-isa`):

```sh
clang -fobjc-arc -framework Metal -framework Foundation -o shdump shdump.m
clang -fobjc-arc -framework Metal -framework Foundation -o agxrun_persist agxrun_persist.m
python3 gen_kernels.py && python3 gen_diff.py          # our own MSL
python3 dump_cf.py            > raw/dump_nofast.log     # extract main + const_program, tokenize
python3 dump_cf.py eret2 eret4 eret6 gsel2 gsel4 ...    # differential set -> raw/dump_diff.log
python3 run_experiments.py   > raw/run_experiments.log  # E1..E6 splice-and-observe on HW
python3 e7_base.py           > raw/e7_base.log          # buffer-base-slot sweep
```
Host-side analysis: `solve_lengths.py` / `segment_cf.py` (segment programs from the logs).

Experiments (all HW splice-and-observe):
- **E1** `gidonly` (`out=gid`): corrupt the preamble → the get-SR role.
- **E2** `eret4` (`if(gid>=4) return; out=7`): move the compare immediate / invert the sense.
- **E3** `dsel5` (`out=(a>5)?100:200`): move the compare immediate feeding the select.
- **E4** `copy1`: corrupt the trailing `0e000000` and the final store → termination.
- **E5** `copy1`: corrupt `_agc.main.constant_program` → is it the buffer-base load?
- **E6** `prodloop` (`s=1; for i<n: s=s*3+1`): find + splice the backward jump offset.
- **E7** `add2` (`out=a+b`): sweep the `device_load` bytes to locate the buffer-base slot.

## Raw results
`raw/dump_nofast.log`, `raw/dump_diff.log`, `raw/dump_loops.log` (extracted bytes +
tokenization), `raw/run_experiments.log` (E1–E6), `raw/e7_base.log` (E7). Text only; the
`.bin` archives stay on the device under `~/cleanroom_work/exp0010/`.

See `RESULTS.md` for the full analysis. Headline: G17P **predicates** simple divergence
(execution mask, no jump), **jumps** only for loops (signed byte-relative offset), the
preamble is **get_sr(thread_position_in_grid)**, buffer bases come from a **preloaded
uniform slot selected by `device_load` byte+4** (not the constant_program, not the binding
index), and `0e000000` is **not** a required terminator.

## Established facts → docs
Deferred to the orchestrator (do not edit `docs/`/`PROVENANCE.md` from a subagent). ISA DB
updated: `tools/agx-isa/` gains `icmp_pred`, `sel`, `psel`, `jump`, `get_sr` (renamed from
`preamble`), a `device_load` base_slot field, and control-flow length rules; round-trip PASS.

## Follow-ups
- Full decode of the `0x0f` execution-mask sub-ops (push/`0f 05`, else/`0f 01`,
  reconverge/`0f 06`, mov-under-mask) and the loop-header ops (`0x1b`, `0x3b`, `0x8f`, `0x2b`).
- The jump offset base-point (relative to instruction start vs end) and forward-jump sign.
- What the `0300070002000000 6000` const_program prefix *is* (advisory/prefetch — corruption
  is a no-op) and how the driver actually preloads the uniform/base slots (cmdstream/USC).
- The `0x0a` vs `0x02` compare condition-code field (full enumeration of relations).
