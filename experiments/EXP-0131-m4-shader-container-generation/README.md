# EXP-0131 -- M4 shader container field map + live splice-and-execute
# hardware-consumer proof (P0.7 / DRV-SHADER-01)

- Date: 2026-08-28
- Target actually tested: local Apple M4 / G16G, macOS 26.6.2 (25G82), Metal 4
- Gap scope: `APPLE9_RE_IMPLEMENTATION_GAPS.md` `DRV-SHADER-01`;
  `docs/P0-P1-CLOSURE.md` row P0.7
- Evidence: HW-PROBE + DATA-TRACE + OWN-SHADER
- Coordination: `EXP-0127-m4-shader-selection` independently attacks the
  live FS/VS *selector* mechanism from the graphics-selection side; this
  experiment deliberately does NOT attempt to derive or construct that
  selector (see `PRE_REGISTRATION.md` "Question" and `PROGRESS.md`
  Milestone 1 step 6). This experiment's angle is the CONTAINER: the
  0x10000000000-family code-BO record's own field layout, and whether
  hardware genuinely consumes it.

## Question

Can the graphics shader container record EXP-0042 structurally mapped on M4
(header/constant_program/main/pad, plus an unresolved "following record") be
(a) independently reproduced from a fresh compile, (b) proven
hardware-consumed (not just macOS-cached) by mutating it in place with our
own tools/agx-isa-derived bytes and observing a predicted, different
rendered pixel, and (c) characterized at its extent/alignment boundaries by
construction (corrupted header, truncated program, corrupted adjacent
record)?

## Method summary

Full detail in `PRE_REGISTRATION.md`. In short: `harness/codesplice.m`
compiles `kernels/render_min.metal` (byte-identical to
`EXP-0008-fragment-extraction`'s own already-HW-validated shader) in-process,
draws once (baseline), uses the unmodified, read-only
`tools/iotrace/iotrace.c` interposer to snapshot this process's own
registered GPU buffers, locates our own compiled 54-byte fragment `_agc.main`
verbatim inside the `0x10000000000`-family code BO, then -- per `--case` --
either leaves it untouched or writes a small number of bytes directly into
that live, CPU-mapped, POST-CREATION memory (never into an archive file,
never before pipeline creation). A second, fresh command buffer then draws
again using the SAME already-created `MTLRenderPipelineState`, and the
resulting pixel is read back and compared against a pre-registered
prediction.

## Commands

```sh
# Build + gates (no GPU):
python3 verify.py --selftest
python3 verify.py --seqtest

# Smoke gate (throwaway, never raw/):
python3 run.py --run-id <id> --smoke-only

# Official capture (writes raw/<run-id>/):
python3 run.py --run-id m4_20260828_run01
python3 run.py --run-id m4_20260828_run02

# Cross-run gate + analysis:
python3 verify.py --captured m4_20260828_run01 m4_20260828_run02
python3 analysis/report.py m4_20260828_run01 m4_20260828_run02
```

See `RESULTS.md` for observations, `PROGRESS.md` for the disclosed
calibration history (including a reproducible, contained process-teardown
crash for one case), and `PRE_REGISTRATION.md`/`CAPTURE_CONTRACT.json` for
the frozen hypotheses, case matrix, and hashes.
