# EXP-0050 results: fragment outputs on M4

> **QUARANTINED — ALL VERDICTS AND CLAIMS BELOW ARE NON-EVIDENCE.** They are
> preserved verbatim as historical output from a process that violated its
> declared byte-access boundary. Do not promote or cite them. The draft clean-v2
> method is blocked and no v2 pre-registration or hardware result exists.

## Historical v1 narrative — quarantined and not normative

All content below is preserved as the v1 interpretation and must not be cited.
`QUARANTINE.md` is authoritative.

## Verdict

**PARTIAL. P0.8 remains open.** Two independent M4 runs give repeatable
compiler-emitted and live-behavior evidence for the tested fragment outputs.
They refine the relationship between semantic render-target selection and the
compact store ordinal, validate one compact-selector mutation, and bound depth,
sample-mask, discard, and side-effect source paths.

This is not a complete native FS ABI, prolog/epilog linkage specification,
tilebuffer ABI, arbitrary-format code generator, Linux UAPI mapping, or A18 Pro
fact.

## Direct observations

### Repetition and provenance

All 21 intact cases plus the guarded splice completed with `STATUS OK` and
`PIPELINE_SOURCE archive` in each of two fresh run directories: 44 forced-archive
executions total. There were no compile failures, pipeline misses, command-buffer
errors, timeouts, GPU faults, or recovery events. For every case, source hash,
exact own fragment main, main size/hash, complete readback, counter, and status
are identical between runs. The temporary archives are also SHA-identical.

### Declaration order is canonicalized in the tested pairs

Reversing only the output-structure member order produced byte-identical complete
fragment mains and identical outputs:

| pair | main bytes | result |
| --- | ---: | --- |
| sparse RT0+RT2: declaration 0,2 vs 2,0 | 98 | identical |
| RT0/1/2: declaration 0,1,2 vs 2,1,0 | 142 | identical |
| color+depth vs depth+color declaration | 156 | identical |
| color+mask vs mask+color, mask `0x5` | 252 | identical |

The compiler canonicalizes these tested semantic outputs; source declaration
order is not the emitted-store order in this matrix.

### Semantic RT selector versus compact store ordinal

Every live target receives its semantic MSL value, including holes:

| case | live written targets | color-store byte `+5`, emitted order |
| --- | --- | --- |
| only color(0) | RT0=`11 22 33 44` | `[0]` |
| only color(1) | RT1=`55 66 77 88` | `[0]` |
| only color(2) | RT2=`99 aa bb cc` | `[0]` |
| color(0)+color(2) | RT0, RT2 | `[2, 0]` |
| color(0)+color(1)+color(2) | RT0, RT1, RT2 | `[4, 2, 0]` |

The exact 12-byte store signature is `e7 06 54 ...`. Within the tested mains,
byte `+5` is twice the compact active-output ordinal and stores emit in descending
compact order. It is **not universally `[[color(n)]] * 2`**: isolated color(1)
and color(2) both use zero, and sparse color(2) uses two rather than four.

Separate surrounding six-byte tile-access records carry semantic selectors. The
isolated color(0), color(1), and color(2) mains differ only at two bytes, where
the setup/end selector is respectively `0x0c`, `0x30`, or `0xc0`. Sparse and MRT
mains preserve those semantic selectors around stores. Earlier contiguous-only
evidence made semantic index and compact ordinal numerically coincide; the new
sparse controls separate the roles.

Swapping the values assigned to RT1 and RT2 changes eight earlier main bytes but
leaves all three store records and their selectors identical. The live RT1/RT2
values swap exactly.

### Depth source paths

| case | color | four Depth32Float values | main bytes |
| --- | --- | --- | ---: |
| color + depth(any), color first | RT0 exact | `0.25` | 156 |
| same, depth field first | RT0 exact | `0.25` | 156, byte-identical |
| depth only | none | `0.625` | 112 |
| color, depth attached but not shader-written | RT0 exact | `0.75` interpolated | 54 |

The exact six-byte `d7 14 54 00 00 03` record occurs once in each shader-depth
case and not in the fixed-depth control. `c0` with no depth attachment and
`color-fixed-depth` with an attached/written fixed depth have byte-identical
54-byte fragment mains, showing that the attachment alone does not change this
fragment main. The record correlation is `OWN-SHADER-DIFF`, not independent
native depth-ABI synthesis.

### Four-sample mask behavior

The shader uses `[[sample_id]]` so masks with the same population but different
bits resolve differently. All four pixels within a case are identical:

| authored mask | resolved RGBA8 bytes |
| ---: | --- |
| `0xf` | `a0 00 00 ff` |
| `0x5` | `40 01 02 82` |
| `0xa` | `60 01 02 82` |
| `0x0` | clear `01 02 03 04` |

The `0x5` color-first and mask-first functions compile byte-identically and
resolve identically. The `0xf`, `0x5`, and `0xa` 252-byte mains differ at exactly
one byte, main `+0x2d`, with values `0x1e`, `0x0a`, and `0x14` (`mask << 1` for
these three constants). Mask zero compiles to a 32-byte main with no matching
color-store record and leaves the clear target. This is compiler correlation;
no mask byte was spliced, so no universal native encoding is claimed.

### Discard and authored side effects

The 4x1 discard case leaves the left two pixels at clear and writes the right two:

```text
01 02 03 04 | 01 02 03 04 | 11 22 33 44 | 11 22 33 44
```

The counter controls reproduce exactly:

| source order | counter | color result |
| --- | ---: | --- |
| atomic, no discard | 4 | all four written |
| atomic before half discard | 4 | right half written |
| half discard before atomic | 2 | right half written |

This establishes behavior of the tested Metal source paths and program order. It
does not locate a general discard/native side-effect opcode contract.

### Guarded compact-selector splice and falsifier

In each run, intact three-RT main contained exactly one store with compact
selector `0x02`. The runner changed only that byte to `0x04`, verified a
one-byte archive/main diff, and forced the mutated own archive. Both runs produced:

- RT0: authored RT0 value;
- RT1: `00 00 00 00` in all pixels;
- RT2: authored RT1 value `55 66 77 88` in all pixels.

The RT2 change validates that this checked store selector reroutes the authored
RT1 store to compact output 2 in the contiguous three-RT pipeline. However, H5
as pre-registered is **falsified**: the unwritten RT1 did not retain its requested
clear `05 06 07 08`; it became zero. A byte-spliced program violates the source
pipeline's declared-output contract, so that zero is recorded only as a
counterexample and not promoted to a background/clear rule.

## Hypothesis outcomes

- **H1 supported and refined:** live semantic routing is order-independent;
  compact store ordinal and semantic tile selector are separate fields.
- **H2 supported** for the three tested shader/fixed depth values and field-order pair.
- **H3 supported** for masks `0`, `5`, `a`, and `f`, including mask-field order.
- **H4 supported** for the tested half-discard and atomic placement.
- **H5 falsified as a combined prediction:** store rerouting occurred, but the
  unwritten target was zero rather than clear.

## Remaining P0.8 gaps

- complete FS input/output registers, system values, and calling convention;
- exact role and interaction of every tile setup/end/store field;
- arbitrary MRT holes, formats, component masks, dual-source blending, layers,
  sample counts, depth/stencil modes, and early/late tests;
- discard/helper-invocation/native side-effect encoding and scheduling;
- programmable blend/logic/conversion prolog/epilog generation and linkage;
- independent generation of whole fragment programs and pipeline sideband;
- Linux unchanged-UAPI mapping; and
- any A18 Pro validation.

The safe implementation status remains `OPEN`; retain existing fallbacks and do
not synthesize untested combinations from this narrow compiler corpus.

## Clean-room attestation

```text
Clean-room provenance: HW-PROBE / OWN-SHADER-DIFF / bounded HW splice
Inputs inspected: complete authored output_matrix.metal; exact selected fragment
  _agc.main bytes; authored color/depth/counter readbacks; public target/tool data
Apple binary introspection: NONE
Apple auxiliary/helper program inspection: NONE
Unknown BO inspection: NONE
Command/state BO inspection: NONE
Compiled constant-program inspection: NONE
Raw repetitions: 2 x (21 intact + 1 checked splice)
Evidence: README reproduction, raw/, analysis/, manifest.json
```
