# EXP-0117 — M4 stage-ABI remainder (DRV-ABI-01 / P0.8)

**Question.** EXP-0109's own RESULTS.md (`experiments/EXP-0109-m4-stage-abi/RESULTS.md`,
"What P0.8 / DRV-ABI-01 still needs") enumerated NINE remaining items after that
experiment closed the VS-fetch/FS-input/FS-output/CS/linkage core of the stage
ABI. This experiment closes as many of those nine as construction-grade
evidence allows, per the coordinator's reinforced bar: for every field
touched, WE construct the values (minimum legal, maximum legal, first invalid
on each side, holes/reserved encodings), execute them on real M4 hardware,
and verify the result against a host-computable oracle by readback — not
merely observe what Metal's compiler happens to emit.

**Target:** Apple M4/G16G, this host only (Mac16,10, 10 GPU cores), macOS
26.6.2 (25G82), Metal 4, Apple clang 21.0.0, `xcrun` 72, Python 3.14.6. A18
Pro/G17P is hands-off (no data collected here); every M4 fact is `INFERRED`
by family for A18/G17P per `docs/m4-deltas.md`'s ISA-identity finding, never
independently confirmed on A18.

**Method.** OWN-SHADER (our own MSL, compiled via the public runtime
`newLibraryWithSource:`, extracted with the unmodified `tools/shdump/`
pipeline) + HW-PROBE (real draws/dispatches, real readbacks, no splicing) +
PUBLIC (Metal SDK header enum values and diagnostic text from the public
compiler on our own source). No Apple binary was disassembled, decompiled, or
otherwise introspected.

**Scope.** See `PRE_REGISTRATION.md` for the full nine-item enumeration with
explicit per-item cover/defer decisions, falsifiable hypotheses, and the
frozen case matrix (`casematrix.py`, 148 cases).

**Files.**
- `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json` — frozen contract.
- `casematrix.py` — the 148-case frozen matrix (single source of truth).
- `kernels/*.metal` — authored MSL (blend/programmable-epilog, FS output
  ordering, barycentric/primitive_id, MSAA centroid/sample, sample_mask,
  stencil overflow, CALL-ABI, call-depth chains).
- `harness/struct_extract.m`, `harness/render.m`, `harness/compute_run.m` —
  authored ObjC probes (structural compile+extract; real render+readback;
  real compute dispatch+readback).
- `harness/gen_callchain.py` — authored generator for `kernels/callchain.metal`.
- `run.py`, `verify.py` — capture driver + standing-gate verifier.
- `raw/` — the two official captures.
- `analysis/` — post-capture arithmetic (blend-factor oracle, barycentric
  oracle, half/float decode), no new GPU calls.
- `RESULTS.md` — per-item verdicts, OBSERVED vs INTERPRETED, finite-resource
  tables, what P0.8 still needs.

**Clean-room category:** OWN-SHADER + HW-PROBE + PUBLIC. See RESULTS.md for
the full attestation.
