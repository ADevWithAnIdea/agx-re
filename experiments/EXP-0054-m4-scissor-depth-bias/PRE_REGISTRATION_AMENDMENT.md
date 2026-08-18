# EXP-0054 pre-run amendment — corrected depth-bias controls

Date frozen: 2026-08-17 (America/Los_Angeles)

This amendment is frozen after `PRE_REGISTRATION.md` commit `13d200c5` and before
any EXP-0054 source compilation or GPU execution. The original preregistration is
preserved unchanged. This file supersedes only the depth-bias matrix and the H3/H4
details stated below; every clean-room, retention, target, timeout, and scope limit
in the original remains in force.

## Reason for the amendment

Pre-run review of the public macOS SDK header found two design defects:

1. `MTL4RenderCommandEncoder.h` documents that a positive clamp limits positive
   bias and a negative clamp limits negative bias. The original matrix paired the
   signs oppositely.
2. H3 mentioned flat slope-only controls, but the original frozen table did not
   include them. H4 also lacked matched clamp-disabled controls needed to attribute
   a smaller displacement to clamping.

No experiment source had been compiled and no EXP-0054 GPU command had run when
these defects were found or this amendment was written.

## Superseding depth-bias matrix

Each case still renders the authored base triangle first, then identical geometry
in a distinct color. The second draw writes depth only if its listed comparison
passes. `less` is used for negative/zero discrimination and `greater` for the
positive large-bias/clamp pair so both clamp signs can be observed. Flat geometry
uses depth 0.5. Sloped geometry uses asymmetric vertex depths 0.2, 0.8, and 0.35.

| Case | Geometry | compare | constant | slope | clamp |
| --- | --- | --- | ---: | ---: | ---: |
| `dbias-flat-zero` | flat | less | 0 | 0 | 0 |
| `dbias-flat-negative` | flat | less | -1 | 0 | 0 |
| `dbias-flat-positive` | flat | less | 1 | 0 | 0 |
| `dbias-flat-slope-negative` | flat | less | 0 | -1 | 0 |
| `dbias-flat-slope-positive` | flat | less | 0 | 1 | 0 |
| `dbias-slope-zero` | sloped | less | 0 | 0 | 0 |
| `dbias-slope-negative` | sloped | less | 0 | -1 | 0 |
| `dbias-slope-positive` | sloped | less | 0 | 1 | 0 |
| `dbias-large-negative` | flat | less | -100 | 0 | 0 |
| `dbias-clamp-negative` | flat | less | -100 | 0 | -0.001 |
| `dbias-large-positive` | flat | greater | 100 | 0 | 0 |
| `dbias-clamp-positive` | flat | greater | 100 | 0 | 0.001 |

The original oppositely signed clamp cases are not run. The exact decimal API
inputs and their binary32 encodings will be retained in authored output.

## Superseding H3 details

Expected: an unbiased repeated primitive fails the strict comparison. Under
`less`, negative constant bias passes and positive constant bias does not. Each
flat slope-only control remains identical to the unbiased flat result. On sloped
geometry, negative and positive slope terms are distinguishable, with at least one
sign changing coverage or stored depth relative to `dbias-slope-zero`.

Falsified by unbiased replacement, a flat slope-only replacement, indistinguishable
positive/negative sloped results, guard corruption, or inconsistent repetitions.
The exact sign and depth displacement remain observations rather than assumptions.

## Superseding H4 details

For each sign, compare an identical magnitude-100 constant bias with clamp disabled
and with the public, sign-matched magnitude-0.001 clamp. The negative pair uses
`less`; the positive pair uses `greater`.

Expected: both sign-matched clamped cases pass their strict comparison and store
finite values. Each clamped displacement from the unbiased base is no greater than
approximately 0.001 plus observed Depth32Float rounding and is strictly smaller
than its same-sign clamp-disabled displacement.

Falsified by a clamped displacement clearly exceeding 0.001, failure to reduce a
same-sign displacement when both paired draws pass, non-finite output, guard
corruption, or inconsistent repetitions. If public validation rejects a case or a
paired draw does not pass, that sign remains `UNKNOWN`; the other sign is evaluated
independently.

## Public API scope note

The current public headers cleanly expose `setViewports:count:`,
`setScissorRects:count:`, and `setDepthBias:slopeScale:clamp:`. They expose no
explicit integer-versus-floating depth-bias selector. Header inspection is PUBLIC
interface evidence only; live M4 output is still required for every behavior claim.

The experiment remains behavioral-only. EXP-0048 does preclassify some M4 fixed
state VAs, but no DATA-TRACE extension is needed for this bounded probe. No BO
payload will be captured or inspected, and no descriptor/UAPI claim will be made.

Clean-room provenance: PUBLIC preregistration amendment for HW-PROBE + OWN-SHADER source
Inputs inspected: public Metal SDK declarations/documentation and committed project text
Apple binary introspection: NONE
Apple auxiliary/helper/program bytes inspected: NONE
Compiled shader bytes inspected: NONE
Command/state/unknown BO payload tracing: NONE
Pointer following: NONE
Mutation/splice/replay: NONE
