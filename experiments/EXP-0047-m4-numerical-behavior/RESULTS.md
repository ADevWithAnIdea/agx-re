# EXP-0047 results — repeatable M4 numerical source paths

## Verdict

**PARTIAL. P1.8 and P0.6 remain open.** Two fresh compile-and-run passes on the
local M4/G16G reproduced exact output bits and exact own-shader bytes for ten
authored no-fast-math Metal source paths. The tested fp32 arithmetic path flushes
subnormal inputs/results in the exercised cases, whereas the tested fp16 arithmetic
path preserves representable subnormals. The tested min/max and rounding behavior is
now bounded precisely below.

This is `HW-PROBE + OWN-SHADER` evidence for compiler-emitted Metal source paths. It
is **not** a claim about a particular native instruction: no independent assembly,
splice, or opcode-isolation test was performed. It is not A18 Pro validation or a
Vulkan/GL conformance result.

## Direct observations

The canonical capture is `raw/m4-two-run-v3.json`, recorded at
`2026-08-17T23:05:06.792243+00:00` on Apple M4, 10 GPU cores, macOS 26.6.2 build
25G82. All ten cases reported `STATUS OK` and `PIPELINE_SOURCE archive`. Pass A and
pass B were byte-for-byte equal, including the exact `_agc.main` produced solely from
the retained authored MSL.

### Raw-bit controls

The fp32 and fp16 identity cases returned all input bits unchanged, including positive
and negative subnormals, signed zero, quiet-NaN payloads, and infinity. This rules out
the buffer load/store and integer-bit transport path as the cause of the arithmetic
subnormal observations. It does not isolate a single floating-point instruction.

### fp32 add and multiply

- `min_subnormal + min_subnormal` returned `+0`; the negative pair returned `-0`.
- `max_subnormal + min_subnormal` returned `+0`, while
  `min_normal + (-max_subnormal)` returned `min_normal`.
- `min_normal * 0.5` returned `+0`; the negative case returned `-0`.
- `min_subnormal * 2` returned `+0`.
- finite overflow returned the correspondingly signed infinity.

Together with the identity controls, these are DAZ/FTZ-like results for the tested
compiler-emitted fp32 arithmetic paths: subnormal operands behave as signed zero and
subnormal arithmetic results flush, preserving the observed zero sign. The experiment
does not establish every operation, mode, or native opcode.

### fp16 add and multiply

- `min_subnormal + min_subnormal` returned `0x0002`.
- `max_subnormal + min_subnormal` returned `min_normal` (`0x0400`).
- `min_normal + (-max_subnormal)` returned `min_subnormal` (`0x0001`).
- `min_normal * 0.5` returned `0x0200`; `min_subnormal * 2` returned `0x0002`.
- the corresponding negative multiplication returned `0x8200`; finite overflow
  returned signed infinity.

Thus representable fp16 subnormal inputs and results were preserved for these add/mul
cases. `min_normal * min_normal` correctly underflowed below the fp16 representable
range to zero and is not evidence of flushing.

### fp32 `fmin` / `fmax`

- With exactly one quiet NaN, both paths returned the numeric operand in either order.
- With two quiet NaNs, both returned operand B with its payload unchanged.
- For `(+0,-0)` and `(-0,+0)`, both returned operand B. Therefore these source paths
  do not implement an order-independent IEEE signed-zero choice on equal operands.
- `(+min_subnormal,-min_subnormal)` also returned operand B for both operations,
  consistent with an effectively-equal comparison plus pass-through selection; the
  selected subnormal bits were not canonicalized.
- Five added unequal finite/infinity controls correctly distinguished minimum from
  maximum in both operand orders.

The safe description is: tested one-qNaN cases are minNum/maxNum-like, while tested
equal/effectively-equal and both-qNaN cases select operand B. The older universal
“IEEE minNum/maxNum” shorthand is too strong.

### `rint` / `round`

- `rint`: ±1.5 and ±2.5, plus ±0.5, matched ties-to-even and preserved the sign of
  zero for `-0.5`. Values immediately below/above +1.5 rounded to 1/2.
- `round`: the same half-way cases matched ties-away-from-zero; ±0.5 returned ±1.
  Values immediately below/above +1.5 rounded to 1/2.
- Both preserved infinities and an exact `2^24` input. `rint` canonicalized the tested
  quiet NaN payload to `0x7fc00000`; `round` preserved `0x7fc12345`.
- Both mapped the tested positive fp32 minimum subnormal to `+0`. `rint` mapped the
  negative minimum subnormal to `-0`; `round` mapped it to `+0` in this compiled path.

`rint` has a 46-byte own main and `round` a 96-byte own main in this capture. That
difference is retained as compiler-output evidence and reinforces why these results
must not be promoted to one native-op semantic claim.

## Process corrections preserved

The initial `raw/m4-two-run.json` omitted ordinary unequal min/max operands. It was
not overwritten. `raw/m4-two-run-v2.json` added that falsifier. Independent review
then requested raw-bit identity and broader rounding controls plus stronger capture
metadata. The canonical v3 capture adds those controls and embeds hashes of the exact
runner, MSL, and repository-authored tool sources, as well as repository revision,
capture time, compiler/SDK identity, target identity, and invocation.

No compile rejection, timeout, GPU fault, hang, device loss, or reboot occurred. The
two earlier matrices remain in `raw/` as append-only design-history evidence but are
not the basis for the promoted claims.

## Remaining work and safe fallback

- repeat the canonical matrix on A18 Pro/G17P;
- isolate and independently generate/splice the relevant native instructions before
  assigning the behavior to opcode semantics;
- expand signaling-NaN, quieting, payload/sign, conversion, fused-operation,
  reciprocal/transcendental, fp16 rounding, and every advertised execution mode;
- add the integer, interpolation, raster/depth/sample, helper-side-effect, and hard-limit
  portions still required by P1.8.

Until then, compiler lowering should conservatively implement required API semantics
where this measured Metal source-path behavior differs, and conformance exposure must
remain gated.

## Clean-room provenance

```text
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected: kernels/numeric.metal; repository-authored shdump/agxtest sources;
  exact _agc.main bytes produced only from numeric.metal; live raw-bit outputs
Apple binary introspection: NONE
Apple auxiliary/helper/program bytes inspected: NONE
Reproduction: python3 run_probe.py; python3 verify.py
Evidence: raw/m4-two-run-v3.json; manifest.json; this RESULTS.md
```
