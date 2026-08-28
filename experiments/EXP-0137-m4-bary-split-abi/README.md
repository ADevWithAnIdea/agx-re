# EXP-0129 — barycentric anomaly discrimination + split prolog/epilog ABI
# construction (DRV-ABI-01 / P0.8, closing the last two open items)

**Target: Apple M4/G16G, local host only.** See `PRE_REGISTRATION.md` for
the full frozen hypothesis/falsifier set and `RESULTS.md` for the outcome.

## Question

P0.8/DRV-ABI-01 has seven of nine constituent items closed by
EXP-0109/EXP-0117 (programmable-blend-epilog spec, CS sysvals, FS output
ordering, `primitive_id`, MSAA centroid-vs-sample, the CALL-ABI byte,
stencil overflow). Two remain open:

- **H1.** EXP-0117 hit a disclosed, 4x-reproduced anomaly: adding an
  unrelated fragment output changes the observed `barycentric_coord`
  value, blocking the vertex-order/perspective-convention determination.
  Discriminate real-hardware-behavior vs. interpolation-slot-allocation
  vs. harness-artifact, then pin the actual convention.
- **H2.** EXP-0109 established Metal's own compiler never produces a
  third code segment (in its tested cases). DRV-ABI-01 still requires the
  prolog/main/epilog linkage contract a driver must implement GIVEN that.
  Construct genuine split prolog/epilog pairs via the CALL ABI and
  characterize the seam.

## Method

Two evidence types per constructed shader variant: **structural**
(compile our own MSL -> extract raw AGX bytes -> disassemble with
`tools/agx-isa` -> compare instruction sequences) and **HW-PROBE** (real
render/dispatch on the M4, real readback, no splicing). See
`PRE_REGISTRATION.md` for the full method and `CODEX.md`/`CLAUDE.md` for
the governing clean-room process.

## Clean-room category

OWN-SHADER + HW-PROBE + PUBLIC (MSL grammar / public Metal API only).
`tools/agx-isa/isadb.py` and `tools/shdump/{shdump.m,agxparse.py}` are used
read-only, unmodified, via their published APIs on bytes this experiment
extracted from its own compiled shaders. No Apple binary is ever
disassembled, decompiled, or otherwise introspected.

## Layout

- `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json`, `PROGRESS.md` — frozen
  contract and milestone log.
- `casematrix.py` — the frozen case list (single source of truth).
- `kernels/*.metal` — authored MSL (all OWN-SHADER).
- `harness/*.m` — authored compile/extract/render/dispatch probes.
- `analysis/isahelper.py` — shared disassembly-summary wrapper around
  `tools/agx-isa/isadb.py` (imported, unmodified).
- `run.py`, `verify.py` — capture driver + standing-gate verifier.
- `raw/` — the two official captures (append-only).
- `RESULTS.md` — observations vs. interpretation, verdicts, driver
  consequences, clean-room attestation.

## Reproduction

```sh
python3 verify.py --selftest
python3 verify.py --seqtest
python3 verify.py --smoke
python3 run.py --run <id> --out raw/<id>      # x2, distinct ids
python3 verify.py --crossrun raw/<run01> raw/<run02>
```
