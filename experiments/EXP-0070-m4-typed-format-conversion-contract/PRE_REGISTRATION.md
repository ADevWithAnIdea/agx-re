# EXP-0070 pre-registration — M4 public typed-format conversion

**Frozen state: PRE-GPU.** This is a new P1.2 public-Metal experiment scaffold,
not a result and not a replacement for quarantined EXP-0064. No compilation or
execution has occurred for EXP-0070.

## Question and bounded hypotheses

For each named 1x1 public texture format, what complete owned backing bytes follow
one authored fragment store, and what does one authored, in-bounds typed compute
`read(uint2(0,0))` observe in the same public command buffer? The six cases are
`rgba8unorm_edges`, `bgra8unorm_edges`, `rgba8srgb_threshold`,
`r16unorm_midpoint`, `rgba16float_finite`, and `r32uint_exact`.

The testable hypotheses are deliberately narrow: selected UNorm endpoints are
clamped; the selected BGRA case differs in physical channel order; the named sRGB
inputs exercise a near-knee store; selected finite half values round-trip through
the public typed reader; and the selected uint word survives a typed uint store and
read. A pipeline or command failure, changed guard, absent status/error record,
wrong-sized backing, repeat mismatch, or a result inconsistent with the recorded
case falsifies its corresponding hypothesis. No rounding rule outside these exact
values is pre-claimed.

## Exact method and controls

Each case gets a fresh process, device, command queue, library, pipeline(s),
command buffer, and exactly two *owned* shared buffers. The render backing is 64
`0x5a` guard bytes, a 256-byte payload row, then 64 `0xa5` guard bytes. A 1x1
texture occupies only the payload start, with `bytesPerRow=256`. The compute
backing is 64 `0x5a`, sixteen result bytes, then 64 `0xa5`. The shader only writes
the sole pixel and reads coordinate `(0,0)`; it deliberately has no OOB path.

The harness prints only public status/error information and complete owned buffer
hex. It never retains or inspects compiled shader bytes, archives, command streams,
BOs, pointers, private interfaces, or Apple helpers. Two fresh append-only M4 runs
are required. The runner records Git revision, all authored SHA-256 values,
`sw_vers`, `xcrun --version`, device, machine, argv, exits, stdout/stderr, and the
60-second host-build and 20-second per-case process caps. A timeout/fault writes a
`STOP.json`, ends that run, and receives no automatic retry.

## Promotion rule and scope

Before any build, `python3 -B verify.py --preflight` must pass. Before any
interpretation, `python3 -B verify.py --captured` must pass for exactly the two
contracted runs, including closed raw trees, source/revision binding, full guard
hex, statuses, and byte-exact repeatability. Until then P1.2 remains **OPEN**.
This cannot establish native PBE/epilog, descriptor, Linux, A18, capability,
filtering, blending, atomics, MSAA, NaN/infinity/subnormal, or general conversion
semantics.

Clean-room provenance: HW-PROBE / OWN-SHADER source / PUBLIC API (planned only)
Inputs inspected: committed authored MSL, harness, contract, and future owned readbacks
Apple binary introspection: NONE
Reproduction: `python3 -B verify.py --preflight`; future capture requires explicit `run.py --execute`
Evidence: no raw observations exist; `CAPTURE_CONTRACT.json` is the frozen capture grammar
