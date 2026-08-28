# EXP-0086 — M4 register-liveness / "cache" bit falsification

## Question

`docs/isa/README.md:770` claims the `0x54<->0x56` byte+2 bit1 field (and, by
extension, the `0x18/0x38` compact-form field cited as its evidence) is
"a source cache / last-use hint (NOT an op change)" — i.e. functionally
inert with respect to correctness. Its only supporting evidence
(`experiments/RT-1a-FIX/RESULTS.md` line 81) spliced the bit on an
instruction and re-checked THAT SAME INSTRUCTION's own result — structurally
incapable of detecting a liveness/last-use bit, whose failure mode is a
LATER read of the marked register returning a stale/garbage/discarded value.
An external compiler engineer building a NIR->Apple9 backend independently
reports Apple9 has a real register-lifetime mechanism and that getting it
wrong causes generated code to intermittently misbehave. This experiment
tests the existing "inert" claim against a real later read, with real
distance/register-pressure/control-flow variation, on real M4 hardware.

## Hypothesis

See `PRE_REGISTRATION.md` for the full falsifiable H1 (inert, the existing
doc claim) vs H2 (real liveness/cache semantics, asymmetric corruption
predicted for a false "reuse cached copy" claim) statement, refuters, and the
frozen case matrix.

## Method

1. Compile 7 minimal MSL kernels (`kernels/*.metal`) via `tools/shdump`, each
   producing a value `v` into a GPR and reading it in two separate later ALU
   instructions, with controlled distance (adjacent / near / +4 / +16
   instructions), register pressure (~40 concurrently live values), or a real
   runtime `if`/`for` control-flow boundary between the two reads.
2. Locate the two register-select-field candidate bits (`casematrix.py`,
   `CAND_A`/`CAND_B`) by disassembling our own compiled bytes with
   `tools/agx-isa` (read-only), freezing the exact byte offsets/hex as
   anchors, re-verified fresh on every capture run (`baseline.py`).
3. Splice ONE field (one bit, same instruction length, no other byte
   changed) via `isadb.decode_one`/`assemble`, using `tools/agxtest/agxtest.py`
   to re-run the spliced binary archive on real M4 hardware in a fresh
   process per case, and compare the output to an independent host-side
   float32 oracle (`casematrix.EXPECTED`).
4. Two full capture runs (135 cases each, 3 repeats per case) with a
   byte-identical-gated-file cross-run gate and a separate non-gated raw
   timing record (`run.py`/`verify.py`).

## Commands

```sh
python3 -B casematrix.py                          # case matrix summary (no GPU)
python3 -B baseline.py --bin-dir <bindir> --out <report.json>   # host-only compile check
python3 -B verify.py --selftest                    # synthetic, no GPU
python3 -B verify.py --seqtest                      # synthetic, no GPU
python3 -B run.py --execute --run-id m4-20260828-run01   # REAL GPU capture
python3 -B run.py --execute --run-id m4-20260828-run02   # REAL GPU capture
python3 -B analysis.py --run-a m4-20260828-run01 --run-b m4-20260828-run02 --write
```

## Clean-room category

**OWN-SHADER** + **HW-PROBE**. Every byte inspected or spliced is the
compiled form of our own MSL (`kernels/*.metal`), compiled at runtime via
`newLibraryWithSource:` (`tools/shdump`) and decoded/re-assembled with our
own `tools/agx-isa` database. Splices are executed on the real M4 GPU via
`tools/agxtest`. No Apple binary, framework, kext, or firmware is
disassembled, decompiled, or otherwise introspected.

## Files

- `PRE_REGISTRATION.md` / `CAPTURE_CONTRACT.json` — frozen hypothesis,
  variables, matrix, environment (filed before any GPU capture).
- `kernels/*.metal` — the 7 authored probe kernels.
- `casematrix.py` — kernel metadata, frozen anchors, independent oracle,
  case generator (single source of truth for `run.py`/`verify.py`/`analysis.py`).
- `baseline.py` — pre-GPU compile + anchor-freshness check.
- `harness/build.sh` — builds the read-only `tools/shdump`/`tools/agxtest`
  sources into this experiment's private `work/` bin dir.
- `run.py` — the capture runner (device-touching only under `--execute`).
- `verify.py` — fail-closed static + post-capture verifier
  (`--selftest`/`--seqtest`/`--preflight`/`--between-runs`/`--captured`).
- `analysis.py` — cross-run comparison + verdict/determinism summary.
- `make_manifest.py` — whole-tree artifact manifest (PRE_GPU / CAPTURED).
- `RESULTS.md` — observations vs interpretation, verdict on the doc claim.
- `PROGRESS.md` — timestamped milestones.
