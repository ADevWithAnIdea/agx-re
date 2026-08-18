# EXP-0054 results — bounded M4 public scissor/depth-bias behavior

## Verdict

**PARTIAL; P0.3 remains open.** Runs03/04 are two fresh processes using exact
final authored inputs; all 19 cases per process completed with public command
status 4, no error, identical stdout, exact full color/depth bytes, and zero guard
errors. Runs01/02 independently repeat every unchanged case and preserve the
initial clamp-control miss.

This establishes only the tested M4 / macOS public Metal behavior. It is not an
`isp_scissor_base` or `isp_dbias_base` descriptor specification, integer-bias
mode, native packet encoding, Linux UAPI mapping, or A18 Pro result.

## Direct observations

Target for all four runs: Apple M4, Mac16,10, macOS 26.6.2 build 25G82. The
public SDK/runtime compiled and accepted `setScissorRects:count:` with a vertex
`[[viewport_array_index]]`. The two recorded public render-encoder headers expose
floating constant/slope/clamp inputs and no explicit integer-versus-float bias
selector in those encoder interfaces. That last point is PUBLIC API-surface
evidence, not a private-mode result or a claim about every possible API header.

### Single scissors

Every changed pixel exactly matched the half-open rectangle; every other pixel
retained clear `01020304`:

| case | rectangle | changed | clear | status |
| --- | --- | ---: | ---: | ---: |
| full | `(0,0,16,16)` | 256 | 0 | 4 |
| asymmetric | `(3,5,7,4)` | 28 | 228 | 4 |
| edge | `(15,14,1,2)` | 2 | 254 | 4 |
| empty width | `(6,7,0,5)` | 0 | 256 | 4 |
| empty height | `(6,7,5,0)` | 0 | 256 | 4 |

Both zero-area rectangles were accepted and covered no pixel. This supports H1
for exactly these in-bounds rectangles and target dimensions; it does not define
out-of-bounds validation, signed coordinates, array layout, or larger targets.

### Two public viewport-indexed scissors

With non-overlapping rectangles, slot 0 wrote exactly 30 pixels and slot 1 wrote
40. Changing only slot 1 to a 3x5 rectangle changed its output to 15 pixels while
slot 0 remained byte-exact at 30. No cross-slot or other-color pixel appeared.

This supports H2 for two identical viewports, two scissors, and two authored
full-screen primitives selecting indices 0/1. It does not establish maximum
counts, mixed viewport transforms, overlaps, private indexing, or descriptor stride.

### Depth bias — constant and slope behavior

With strict `less`, the unbiased repeated flat primitive did not replace the base
and retained depth 0.5. The tested negative constant passed at every pixel; the
positive constant did not. Flat slope-only `-1` and `+1` cases both remained
identical to unbiased depth, as expected from zero depth slope.

For the sloped triangle, unbiased stored depths ranged from `0.211718723` to
`0.563281238`. Slope `-1` passed every pixel and shifted the range to
`0.192968711`–`0.544531226`; slope `+1` under `less` did not replace the base.
The `-0.01875` displacement matches the maximum authored window-depth derivative
for this triangle. This supports H3 only for the tested geometry, strict compare,
Depth32Float, and state order.

For flat depth 0.5, observed constant displacement matched
`constant * 2^-24` at `-1`, `±100`, and `±100000` (subject to binary32 rounding):

| input | compare | stored depth | displacement |
| ---: | --- | ---: | ---: |
| `-1` | less | `0.499999940` | `-0.0000000596046` |
| `-100` | less | `0.499994040` | `-0.00000596046` |
| `+100` | greater | `0.500005960` | `+0.00000596046` |
| `-100000` | less | `0.494039536` | `-0.00596046448` |
| `+100000` | greater | `0.505960464` | `+0.00596046448` |

This is a bounded public-path correlation, not a universal format formula or an
encoding of the private bias descriptor.

### Clamp falsifier and engaged follow-up

The preregistered magnitude-100 clamped and unclamped pairs were byte-identical:
their approximately `5.96e-6` displacement was already below `0.001`. Therefore
H4's predicted strict reduction was **not observed**. That failed attribution is
preserved rather than retroactively promoted.

The separately preregistered magnitude-100000 follow-up engaged both clamp signs:

| sign | unclamped depth | clamped depth | clamped displacement |
| --- | ---: | ---: | ---: |
| negative | `0.494039536` | `0.498999983` | `-0.00100001693` |
| positive | `0.505960464` | `0.500999987` | `+0.000999987125` |

Both clamped cases passed their strict comparison, remained finite, and reduced
the absolute displacement from about `0.00596` to `0.001` within Depth32Float
rounding. H6 is supported for these two sign-matched public inputs.

## Process evidence and limitations

- Runs01/02 are successful initial-source repetitions, not discarded failures.
  They bind the exact magnitude-100 source/runner hashes and initial stdout hash.
- Runs03/04 bind the exact final magnitude-100000 source/runner hashes and final
  stdout hash. All scissor and unchanged depth cases match runs01/02 exactly.
- The retained build warning only notes that the authored compile option property
  is deprecated; every build exited zero. Runtime stderr is empty.
- All 76 command buffers completed; no timeout, GPU fault, retry, or reboot occurred.
- No BO trace exists. Consequently this experiment does not advance the byte layout
  of either ISP array. It advances behavioral generation constraints only.

Remaining P0.3 work includes exact descriptor bases/strides/packing and bounds,
multiple-scissor storage, empty-entry representation, integer-depth-bias selection,
other depth formats/ranges, Linux field marshaling, and direct A18 Pro repetition.

## Clean-room provenance

```text
Clean-room provenance: HW-PROBE + OWN-SHADER source + PUBLIC
Apple binary introspection: NONE
Apple auxiliary/helper/program bytes inspected: NONE
Compiled shader bytes inspected: NONE
Command/state/unknown BO payload tracing: NONE
Generic memory scan / pointer following: NONE
Mutation/splice/replay: NONE
Target: M4/G16G-class only; A18 Pro untested
Evidence: raw/m4_20260817_run01..04, analysis/, manifest.json
```
