# EXP-0053 results — bounded M4 indirect-command behavior

## Verdict

**PARTIAL; P1.7 remains open.** Two fresh processes using exact final authored
inputs completed 13 public indirect-command cases each with identical stdout and
readbacks. The tested indirect argument updates, ICB execution ranges,
reset/re-encode sequence, and public optimization behave as pre-registered.

This is M4 compiler/runtime/API behavior only. It is not a private command-stream
grammar, native packet or helper-program semantic, Linux UAPI mapping, arbitrary
DGC validation rule, or A18 Pro result.

## Direct observations

Canonical runs 05 and 06 ran on Apple M4 / Mac16,10, macOS 26.6.2 build 25G82.
All 26 canonical command buffers reported status 4/error none and both processes
ended `RESULT OK`.

### Indirect compute arguments

With eight threads per threadgroup:

| case | retained argument | exact atomic count | result |
| --- | ---: | ---: | --- |
| zero | `(0,1,1)` | 0 | no authored output changed |
| encoded as 1, changed before commit | `(3,1,1)` | 24 | words 0–23 exact |
| GPU producer in prior encoder | `(4,1,1)` | 32 | words 0–31 exact |

Every remaining output word and every prefix/suffix guard stayed at its authored
sentinel in both runs. The observations support execution-time consumption for
the tested CPU-before-commit update and visibility of GPU-produced arguments
across these adjacent compute encoders. They do not define concurrent CPU/GPU
access, missing-barrier behavior, or native cache operations.

### Indirect draw arguments

The zero-vertex case left all four pixels at clear `01020304`. The three-vertex
case wrote `11223344` to all four pixels. Argument prefix/suffix guards remained
unchanged in both repetitions.

### ICB execution ranges

Four encoded commands target independent pixels with values:

```text
index 0 = 102030ff
index 1 = 405060ff
index 2 = 708090ff
index 3 = a0b0c0ff
clear   = 01020304
```

The retained complete rows were exact for full `[0,4)`, prefix `[0,2)`, suffix
`[2,4)`, middle `[1,3)`, and empty `[0,0)` ranges. Only indices inside each
requested range changed their pixels. This establishes the tested public range
semantics, not private encoded-command count fields.

Resetting `[1,3)` left commands 0 and 3 active and pixels 1/2 clear. Re-encoding
only slot 1 restored pixel 1 while slot 2 remained clear. Commands outside the
reset range were unchanged in both repetitions.

A fresh full ICB optimized through
`optimizeIndirectCommandBuffer:withRange:` produced the same complete row as the
unoptimized full execution. This is one functional equivalence case, not a claim
about representation or performance.

## Preserved failures

Run 01 retains the compile rejection for an unavailable authored device-property
spelling. Run 02 retains five successful indirect argument commands followed by
a GPU address fault at the first ICB execution and explicitly ignored later
submissions. The cause was our missing public pipeline opt-in; adding only
`supportIndirectCommandBuffers = YES` produced two behaviorally successful
repetitions.

Runs 03 and 04 were those first successful repetitions. They retained full
render rows but only a 64-bit FNV plus aggregate mismatch/guard counts for
compute and draw-argument storage. That did not meet the pre-registered promise
to retain exact full output and guard bytes. The runs remain append-only process
history but are not the basis of the promoted byte-level claims. Runs 05/06 add
the complete argument/counter/output hex and reproduce every earlier value.

These failures are process evidence, not Apple implementation evidence. Only
public compiler/runtime error strings were retained; no referenced code, binary,
or executable section was opened or inspected.

## Remaining P1.7 work

- Repeat the final matrix on A18 Pro/G17P.
- Establish exact direct/indirect global/local CDM modes and the authored grid
  setup needed by the unchanged Linux userspace contract.
- Cover indexed/multi-draw, count buffers, restart/bounds, inherited/non-inherited
  state and resources, render/compute ICB mixtures, nested ranges, and maximums.
- Validate GPU-authored ICB commands, writable command grammar, barriers/cache
  transitions, security validation, reuse, simultaneous queues, and failures.
- Independently generate relocatable native packets before promoting any private
  stream syntax.

## Clean-room provenance

```text
Clean-room provenance: HW-PROBE + OWN-SHADER source
Apple binary introspection: NONE
Apple auxiliary/helper/program bytes inspected: NONE
Compiled shader bytes inspected: NONE
Command/BO payload tracing: NONE
Target: M4/G16G-class only; A18 Pro untested
```
