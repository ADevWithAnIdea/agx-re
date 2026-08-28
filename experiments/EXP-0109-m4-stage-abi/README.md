# EXP-0109 — M4 VS/FS/CS stage ABI (DRV-ABI-01 / P0.8)

## Question

`docs/P0-P1-CLOSURE.md` P0.8 (`DRV-ABI-01`) is the only `queued` P0 row with no active
experiment: the complete VS/FS/CS stage ABI, shader linking, and programmable epilogs.
This experiment establishes a bounded, high-value slice of it on the local M4, building
on EXP-0031 (A18 SR/ABI table), EXP-0092 (M4 sysval ABI), EXP-0029 (A18 fragment ISA),
EXP-0097 (M4 varying capacity), EXP-0091 (M4 discard/sample-mask), and
`docs/isa/register-move-and-liveness.md`.

Full hypotheses, falsifiers, and scope boundary: `PRE_REGISTRATION.md`.

## Method

Two evidence tiers, both OWN-SHADER (our own MSL, compiled through the public Metal
runtime; no Apple binary introspected):

1. **Structural differential compile** (`harness/vfetch_extract.m`,
   `harness/mrt_extract.m`, and the unmodified `tools/shdump/shdump.m`): build a render
   or compute pipeline from our own MSL with one ABI-relevant parameter varied
   (vertex-descriptor format/layout, interpolation qualifier, attachment count, a
   deliberately-invalid attribute), serialize to an `MTLBinaryArchive`, and extract the
   AGX bytes with the repo's read-only `agxparse.py` for presence/length/byte-diff
   analysis. This is `OWN-SHADER-DIFF`/`STRUCTURAL` tier evidence.
2. **HW-PROBE execution + readback** (`harness/render_probe.m`,
   `harness/compute_probe.m`): real draws/dispatches on the M4 GPU with host-controlled
   parameters, reading back device-buffer contents or color/depth/stencil texture bytes
   — no splicing, pure black-box observation of our own compiled shaders' actual
   runtime behavior. This is the stronger `HW-VALIDATED`/`HW-PROBE` tier for the load-
   bearing claims (does a value actually arrive correctly, not just "does different code
   get generated").

`casematrix.py` is the frozen, single-source-of-truth case list (57 cases across 5
backends) used identically by `run.py` (capture) and `verify.py` (gates).

## Commands

```sh
# Build the harness binaries + run one full capture:
python3 run.py --run <run_id> --out raw/<run_id>

# Non-recorded smoke gate (one structural + one HW-PROBE case, writes to work/, not raw/):
python3 run.py --run smoke --out work/smoke_<n> --smoke-only

# Standing gates:
python3 verify.py --selftest
python3 verify.py --seqtest
python3 verify.py --crossrun raw/m4-20260828-run01 raw/m4-20260828-run02
```

## Standing gates implemented

- `--selftest`: synthetic fabricated records (no GPU, no `raw/` needed) exercise the
  gating/comparison logic and prove it fails closed on a broken shape.
- `--seqtest`: walks `PRE_GPU -> RUN01_PRESENT -> RUN02_PRESENT` and checks each gate is
  runnable exactly where the contract expects.
- Non-recorded smoke gate: `run.py --smoke-only` runs one real structural case and one
  real HW-PROBE case before any `raw/` capture begins, writing only to `work/`.
- No-nondeterminism: `run.py`'s `check_no_nondet()` statically forbids
  `{duration_ms, pid, timestamp, started_utc, address, elapsed}` inside any case's
  gated (cross-run-compared) record; all timing/process metadata lives in the separate
  `meta` field, which is excluded from the cross-run comparison.
- Fixtures from recorded reality: `verify.py --selftest`'s synthetic shapes are modeled
  directly on real `04_results.jsonl` records produced during harness development
  (see `harness/fixtures/recorded_reality.json`).

## Clean-room provenance

```text
Clean-room provenance: OWN-SHADER (+ HW-PROBE for harness/render_probe.m and
  harness/compute_probe.m; PUBLIC for the MTLVertexFormat/MTLPixelFormat enum values,
  read from the public Metal.framework SDK headers, and for the
  supportsShaderBarycentricCoordinates device-capability query)
Inputs inspected: kernels/*.metal (authored by us), the public Metal SDK headers
  (MTLVertexDescriptor.h, MTLPixelFormat.h, MTLRenderPipeline.h, MTLDevice.h — public
  developer-facing API declarations, not compiled binaries), and NSError diagnostic
  text the public Metal compiler frontend returns for our own source.
Apple binary introspection: NONE. tools/shdump/shdump.m is used unmodified, rebuilt
  fresh from its committed source (SUBAGENT_BRIEF's "reused OWN-SHADER tools ...
  (copied, not edited)" pattern); tools/agx-isa/ and tools/agxtest/ were not touched.
Reproduction: see Commands above.
Evidence: raw/m4-20260828-run01/, raw/m4-20260828-run02/, RESULTS.md.
```
