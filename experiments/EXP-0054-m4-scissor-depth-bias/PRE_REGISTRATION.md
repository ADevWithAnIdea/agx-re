# EXP-0054 pre-registration — M4 scissor and depth-bias behavior

Date frozen: 2026-08-17 (America/Los_Angeles)

Target: local Apple M4 / G16G-class GPU only. A18 Pro / G17P is untested.

Gap: `AGX_RE_INFORMATION_GAPS.md` P0.3 requires the Apple9 values and layouts
behind `isp_scissor_base`, `isp_dbias_base`, multiple scissors, empty rectangles,
and float/integer depth-bias selection. This experiment deliberately addresses
only the public Metal behavior and the authored state-generation inputs visible
through complete render-target/depth readback. It cannot by itself establish the
private ISP descriptor layout or the unchanged Linux UAPI mapping.

## Clean-room scope frozen before execution

This is an `HW-PROBE + OWN-SHADER source` experiment using only authored
Objective-C/MSL and public Metal/Foundation APIs. It will not trace or inspect BO
payloads. In particular it will not inspect Apple binaries, Apple auxiliary or
helper code, compiled shader bytes, executable sections, command/unknown BOs, or
unclassified state/descriptor memory; it will not scan memory, follow pointers,
mutate command memory, splice bytes, or replay captured commands.

The earlier M4 EXP-0043 clean-evidence allowlist does not independently classify
the `0x58000` or `0x68000` payloads for use here. Therefore those addresses and
all other captured BOs are out of scope. Any future DATA-TRACE extension requires
a separate pre-run amendment that names exact independently classified state BO
VAs, validates snapshot metadata before payload access, and forbids generic scans.

## Questions

1. Do single public `MTLScissorRect` rectangles produce exact half-open pixel
   coverage on M4, including asymmetric, one-pixel edge, and zero-area cases?
2. If the current public SDK/runtime cleanly accepts `setScissorRects:count:`, do
   two viewport-indexed rectangles independently constrain authored primitives,
   and does changing only rectangle 1 leave rectangle 0 behavior unchanged?
3. For `MTLPixelFormatDepth32Float`, which sign of public
   `setDepthBias:slopeScale:clamp:` moves a repeated primitive toward the camera,
   do constant and slope terms affect the expected flat/sloped controls, and does
   a nonzero clamp bound the observed stored-depth displacement?
4. Does public Metal expose any explicit integer-versus-float depth-bias selector
   in the authored path? If not, no integer-mode or private-array claim will be
   inferred.

## Frozen authored matrix

All render targets are 16 x 16. Color is RGBA8Unorm with asymmetric clear/draw
bytes. Depth cases use Depth32Float. Each retained color/depth copy is surrounded
by 32-byte prefix and suffix guards initialized to asymmetric sentinel patterns.
The complete guarded bytes, not only hashes or aggregate counts, will be retained.

Single-scissor cases:

| Case | Rectangle | Purpose |
| --- | --- | --- |
| `scissor-full` | `(0,0,16,16)` | full-target control |
| `scissor-asymmetric` | `(3,5,7,4)` | distinguish origin, extent, and half-open end |
| `scissor-edge` | `(15,14,1,2)` | right/bottom boundary control |
| `scissor-empty-width` | `(6,7,0,5)` | zero-area acceptance or preserved rejection |
| `scissor-empty-height` | `(6,7,5,0)` | independent zero-area control |

If public `setScissorRects:count:` compiles and the M4 runtime accepts it, two
identical full-target viewports will be paired with rectangles 0/1. Two authored
primitives will select viewport indices 0/1 and write distinct colors:

| Case | Rectangle 0 | Rectangle 1 | Purpose |
| --- | --- | --- | --- |
| `multi-base` | `(1,2,5,6)` | `(9,3,4,10)` | independent slot behavior |
| `multi-rect1-change` | `(1,2,5,6)` | `(11,8,3,5)` | change only slot 1 |

If compilation, selector creation, or encoding rejects this public multi-scissor
path, the exact diagnostic/failure record is retained and no multiple-scissor
behavioral claim is made.

Depth-bias cases render an authored base triangle first, then the same geometry in
a distinct color under `less` comparison; the second draw writes depth when it
passes. Flat geometry uses depth 0.5. Sloped geometry uses asymmetric vertex depths
0.2, 0.8, and 0.35. Frozen states are:

| Case | Geometry | constant | slope | clamp |
| --- | --- | ---: | ---: | ---: |
| `dbias-flat-zero` | flat | 0 | 0 | 0 |
| `dbias-flat-negative` | flat | -1 | 0 | 0 |
| `dbias-flat-positive` | flat | 1 | 0 | 0 |
| `dbias-slope-zero` | sloped | 0 | 0 | 0 |
| `dbias-slope-negative` | sloped | 0 | -1 | 0 |
| `dbias-slope-positive` | sloped | 0 | 1 | 0 |
| `dbias-clamp-negative` | flat | -100 | 0 | 0.001 |
| `dbias-clamp-positive` | flat | 100 | 0 | -0.001 |

The two clamp signs are retained as public-API observations; the analysis will not
assume Metal's clamp-sign convention. Any encoder exception, validation failure,
GPU fault, timeout, or non-finite depth is a retained result.

## Hypotheses and falsifiers

### H1 — single scissors use half-open integer rectangles

Expected: exactly `width * height` pixels change, at `x <= X < x+width` and
`y <= Y < y+height`; the edge case changes exactly two pixels; accepted empty
rectangles change none.

Falsified by any changed pixel outside the rectangle, any unchanged pixel inside,
inclusive far edges, coordinate transposition, or accepted empty coverage.

### H2 — public multiple scissors are indexed independently

Expected if supported: each primitive is clipped only by the rectangle matching
its authored `[[viewport_array_index]]`; changing rectangle 1 changes only the
second-color coverage and leaves rectangle-0 pixels exact.

Falsified by shared/union/intersection behavior, rectangle-0 changes under the
slot-1 perturbation, cross-slot color writes, or nondeterministic coverage.
Compile/runtime rejection classifies H2 as `UNSUPPORTED/UNTESTED`, not falsified.

### H3 — depth-bias signs and terms are behaviorally distinguishable

Expected: with `less`, an unbiased repeated primitive does not replace the base;
one constant-bias sign replaces it and stores a consistently shifted depth while
the opposite sign does not. On sloped geometry, one slope sign similarly replaces
pixels while the flat zero-slope control is unaffected by slope-only bias.

Falsified by an unbiased replacement, identical positive/negative behavior, slope
bias changing only the flat control, guard corruption, or inconsistent repeats.
The direction and exact stored values will be learned from the readback, not assumed.

### H4 — clamp bounds the tested displacement

Expected: at least one nonzero-clamp case produces a finite stored-depth displacement
whose magnitude is no greater than approximately the requested 0.001 plus observed
Depth32Float rounding. The sign convention is an observation.

Falsified by an accepted/passing clamp case whose displacement clearly exceeds the
bound, or by nondeterministic/non-finite results. If neither clamp case passes depth,
H4 remains `UNKNOWN`.

### H5 — there is no public integer-depth-bias selection in this path

Expected: the authored public encoder surface used here provides only floating
constant/slope/clamp inputs. This supports only a negative API-surface observation.

Falsified by a documented public encoder/pipeline selector in the current SDK that
directly chooses integer versus floating depth-bias mode. Absence of a selector does
not establish the private ISP mode bit or the Linux render flag.

## Controls and confounders

- Two fresh processes with byte-identical final source and case order are mandatory.
- Distinct colors, asymmetric rectangles/depths, a full-target control, and positive/
  negative/zero values separate coordinates, signs, and state leakage.
- Each case creates fresh color/depth/readback resources and a fresh command buffer.
- All command buffers must report their exact public status/error and finish under a
  hard per-process timeout. Build and analysis also have hard timeouts.
- Runtime shader compilation, floating-point rasterization rules, pixel-center rules,
  implementation depth-bias units, clipping, and public API validation are confounders.
- Public output correlation does not identify a private descriptor byte, prove a
  hardware-versus-runtime division, or transfer from M4 to A18 Pro.

## Retention and acceptance

Before the first source compilation or GPU execution, this exact file must be the
only EXP-0054 artifact committed. Every run records its SHA-256, the preregistration
commit, repository revision, target/OS/tool identity, exact authored-source hashes,
exact build and run argv, start times, timeouts, exits, stdout/stderr, failures, and
per-run SHA-256 inventory.

At least two successful fresh-process repetitions of the final source are required
for a promoted behavioral observation. Full guarded color/depth bytes and exact case
metadata must agree. Failed attempts remain append-only and noncanonical. A strict
verifier must enforce exact run sets, file sets, source bindings, closed output grammar,
modeled scissor pixels/guards, finite depth values, reproducibility, manifest coverage,
and the clean-room attestations.

Verdicts remain `PARTIAL`, M4-only. `isp_scissor_base`, `isp_dbias_base`, private
descriptor layouts, integer-depth-bias mode, Linux marshaling, and A18 behavior remain
`UNKNOWN` unless established by separate clean evidence.

Clean-room provenance: HW-PROBE + OWN-SHADER source
Inputs inspected: authored Objective-C/MSL; public Metal status/errors; complete bytes
  in color/depth/readback resources allocated by the authored process
Apple binary introspection: NONE
Apple auxiliary/helper/program bytes inspected: NONE
Compiled shader bytes inspected: NONE
Command/state/unknown BO payload tracing: NONE
Pointer following: NONE
Mutation/splice/replay: NONE
