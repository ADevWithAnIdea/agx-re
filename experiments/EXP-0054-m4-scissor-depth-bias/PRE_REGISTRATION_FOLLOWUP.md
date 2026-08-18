# EXP-0054 preregistered clamp-engagement follow-up

Date frozen: 2026-08-17 (America/Los_Angeles)

This follow-up is written after append-only runs `m4_20260817_run01` and
`m4_20260817_run02`, but before changing the authored source, compiling that
change, or executing another GPU command. The original preregistration,
pre-run correction, sources, raw runs, and H4 result remain preserved.

## Triggering observation

Both original final-source repetitions were byte-identical. For flat depth 0.5,
the clamp-disabled `constant = -100` case stored `0.49999404` and the
sign-matched `clamp = -0.001` case stored the same value byte-for-byte. The
positive pair similarly both stored `0.50000596`. Thus magnitude 100 produced
only an approximately `5.96e-6` displacement, already smaller than 0.001; the
clamp control did not engage.

Under the exact first amendment, H4's expected strict reduction was not observed.
That negative/inadequate-input result is not discarded or rewritten. It neither
shows that clamping is absent nor establishes its formula.

## Follow-up variable and controls

Change only the magnitude in the four existing large/clamp cases from 100 to
100000. Names, geometry, comparison, slopes, clamps, command order, shaders,
resources, and every scissor/other depth case remain unchanged:

| Case | compare | constant | slope | clamp |
| --- | --- | ---: | ---: | ---: |
| `dbias-large-negative` | less | -100000 | 0 | 0 |
| `dbias-clamp-negative` | less | -100000 | 0 | -0.001 |
| `dbias-large-positive` | greater | 100000 | 0 | 0 |
| `dbias-clamp-positive` | greater | 100000 | 0 | 0.001 |

The exact prior source hash and outputs remain bound to runs01/02. At least two
fresh processes with the new byte-identical source are required; they become the
canonical final-source repetitions only if all cases complete, guards remain
unchanged, complete outputs match, and the strict verifier reconstructs and binds
both source versions.

## H6 — sign-matched public clamp engages above its bound

Expected: clamp-disabled magnitude-100000 displacements are finite and exceed
0.001 in magnitude. Each sign-matched clamped case passes its strict comparison,
has a finite displacement no greater than approximately 0.001 plus Depth32Float
rounding, and has strictly smaller displacement than its same-sign unclamped pair.

Falsified by an unclamped displacement that still does not exceed 0.001, a clamped
displacement that clearly exceeds 0.001, no strict reduction when both draws pass,
non-finite output, guard corruption, or disagreement between repetitions. A result
is only public M4 API behavior; it is not a private descriptor encoding or general
depth-format formula.

## Unchanged boundary

The experiment remains `HW-PROBE + OWN-SHADER source` with PUBLIC header context.
No BO tracing or content inspection is added. No Apple binary, auxiliary/helper
code, compiled shader bytes, executable sections, command/state/unknown BO, or
pointer target may be inspected. No generic scan, mutation, splice, or replay is
allowed. P0.3 remains open for `isp_dbias_base`, descriptor layout, integer mode,
Linux mapping, other formats, and A18 Pro.

Clean-room provenance: HW-PROBE + OWN-SHADER source + PUBLIC
Inputs inspected: authored run01/02 public output bytes and public Metal declarations
Apple binary introspection: NONE
Apple auxiliary/helper/program bytes inspected: NONE
Compiled shader bytes inspected: NONE
Command/state/unknown BO payload tracing: NONE
Pointer following: NONE
Mutation/splice/replay: NONE
