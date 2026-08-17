# EXP-0048 results: PBE formats and empty-tile behavior on M4

## Verdict

**PARTIAL. P0.4 and P1.1 are not closed.** Two independent M4 runs establish
reproducible empty-tile Clear/Store and Load/Store behavior, six useful
format/control variants of the 0x20-byte MRT LOAD/STORE-PBE records, a bounded
load/store action selector candidate, and clean blend/atomic boundaries.

The experiment did **not** identify a BG/EOT tagged program address, the packed
resource-specification layout required by `drm_asahi_bg_eot`, a callable
userspace program ABI, or ownership of store-program ID `0x6f`. The safe outcome
is a stronger PBE/behavior foundation plus an explicit negative boundary, not a
guessed BG/EOT implementation.

All findings are local Apple M4 / G16G observations. They do not validate A18
Pro despite the architectural similarity hypothesis.

## Direct observations

### 1. Repetition and live completion

All 12 primary cases completed with Metal command status 4 and no error in each
of two fresh processes. Each case captured all four and only the four
pre-registered state BOs. For every case, every captured byte is identical
between run01 and run02: 48 exact case/BO repeat comparisons. Generated MSL and
authored target/counter results also reproduce exactly.

The same-draw Load/Store no-blend control completed twice and its four state BOs
are byte-identical across those repetitions.

### 2. Empty-tile load/clear/store behavior

Every 32 x 32 target pixel was uniform in each result:

| authored pass | RT0 physical bytes | RT1 physical bytes | observation |
| --- | --- | --- | --- |
| empty Clear/Store | `20 40 60 80` | `a0 60 30 c0` | exact requested clear colors stored |
| empty Load/Store | `40 20 10 ff` | `10 18 20 ff` | exact initialized surface bytes preserved |

These are direct behavioral observations of background/load and end/store work
on an empty one-tile pass. They do not reveal the implementing program or ABI.

With a full-screen draw, DontCare/Store produced the same authored color as
Clear/Store because every sample was covered. Clear/StoreDontCare left the
initialized shared-buffer bytes unchanged in both runs. StoreDontCare readback
is API-undefined, so that repeatable value is recorded but not promoted to a
general guarantee.

### 3. Fixed 0x20-byte LOAD and STORE/PBE records

For attachment `k`, the relocated descriptor arena contains LOAD at
`0x10000018200 + 0x20 + k*0x20` and STORE/PBE at
`0x10000018200 + 0x220 + k*0x20`. Selected exact first-attachment words are:

| format | LOAD words 0..3 | STORE/PBE words 0..3 |
| --- | --- | --- |
| RGBA8Unorm | `f6880a02 00007c01 00006000 0003c010` | `1fe40a02 000007c0 00006000 0000f010` |
| BGRA8Unorm | `f60a0a02 00007c01 00006000 0003c010` | `1fc60a02 000007c0 00006000 0000f010` |
| RGBA8Unorm_sRGB | `f6880a02 00007c01 00006000 0003d010` | `1fe40a02 000007c0 00006000 2000f010` |
| R32Float | `f9688842 00007c01 00006000 0003c010` | `1f008842 000007c0 00006000 0000f010` |
| R32Uint | `f9684842 00007c01 00006000 0003c010` | `1f004842 000007c0 00006000 0000f010` |

The mixed RGBA8/R32Float pass places the R32Float words in the second record at
`+0x40` and `+0x240`, independently confirming per-attachment format state.

Directly observable invariants:

- STORE word0 high byte is 31 and STORE word1 shifted right 6 is 31 for all
  cases, matching width-1 and height-1 for the authored 32 x 32 targets.
- In both LOAD and STORE records, the low 40 bits of the qword at record `+0x08`
  shifted left four reconstruct the exact authored target-buffer GPU VA
  (`0x10000060000` or `0x10000068000`). The remaining high 24 bits are kept as
  an opaque packed resource/control field.
- RGBA/BGRA and float/uint variants have distinct stable low-24 format/component
  values. sRGB retains RGBA8's low 24 bits but changes the packed high field:
  LOAD `0x0003c0 -> 0x0003d0`, STORE `0x0000f0 -> 0x2000f0`.

The field names above width/height and surface-address reconstruction are
structural interpretations, not names read from Apple code.

### 4. Load/store actions are not carried by the PBE record differential

The complete relocated descriptor arena is byte-identical across all RGBA8
action cases. The only bounded action-correlated byte is fixed-function state
`0x58000 + 0x14`:

| pass shape/action | observed byte |
| --- | ---: |
| drawn Clear/Store | `0x19` |
| drawn DontCare/Store | `0x19` |
| drawn Load/Store no-blend control | `0x10` |
| drawn Clear/StoreDontCare | `0x20` |
| empty Clear/Store | `0x00` |
| empty Load/Store | `0x00` |

Interpretation: `+0x14` is an action/path selector candidate in this matrix; it
is not a decoded enum. In particular, empty Clear and empty Load have
byte-identical contents in all four allowed state BOs while producing different
target results. Therefore the tested allowlist does not expose the complete
BG/EOT action selection or inputs.

StoreDontCare does not poison or remove the surface in the relocated STORE/PBE
record here. Its record remains byte-identical to Store, while `+0x14` and live
behavior differ. This corrects the pre-registered poison expectation for this
MRT layout without denying that a different single-RT layout may use poison.

### 5. Blend boundary

The pre-registered Load/Store no-blend control produced RGBA bytes
`40 80 bf 80`; enabling standard source-alpha blending produced
`40 50 68 bf`, the expected blend against initialized `40 20 10 ff`.

Control and blend PBE arenas, VDM state, and tiling state are byte-identical.
Only `0x58000 + 0x53` changes `00 -> 20`. This isolates bit `0x20` at that byte
as blend-correlated for this workload. The larger main-baseline diff at `+0x14`
was due to Clear versus Load, which is why the post-matrix control was
pre-registered and run twice.

### 6. Fragment atomic boundary

The authored fragment atomic case increments its counter exactly 1024 times,
one per pixel in the 32 x 32 full-screen draw. Its two target surfaces exactly
match the non-atomic RGBA8 baseline. Its entire MRT descriptor arena is also
byte-identical to baseline, including both PBE format/dimension/address records.

Atomic use changes two bytes in the allowlisted VDM BO and eleven bytes in the
fixed-function state BO. Those values are retained in `analysis/summary.json`;
this experiment does not assign them field names. The observation confines the
atomic side effect outside PBE identity, not to a specific undocumented ABI.

### 7. Typed format behavior at the process boundary

Every stored surface was uniform and exact in both runs:

| target | authored logical output | observed physical bytes |
| --- | --- | --- |
| RGBA8Unorm | `(0.25, 0.5, 0.75, 0.5)` | `40 80 bf 80` |
| BGRA8Unorm | same | `bf 80 40 80` |
| RGBA8Unorm_sRGB | same | `89 bc e1 80` |
| R32Float | `0.25` | `00 00 80 3e` |
| R32Uint | `37` | `25 00 00 00` |
| MRT1 R32Float | `0.625` | `00 00 20 3f` |

This independently connects the format-specific record words with successful
typed conversion/store behavior. It does not yet establish saturation edges,
NaN behavior, all channel arrangements, integer widths, or blend legality for
other formats.

## Hypothesis outcomes

- **H1 supported:** format cases change stable record fields while 32 x 32
  geometry and per-target addresses remain coherent.
- **H2 supported:** empty clear and empty load produce the exact defined target
  bytes in both runs.
- **H3 refined/partly falsified:** action deltas exist at `+0x58014`, but the
  PBE surface record is not poisoned for StoreDontCare, and empty Clear versus
  Load is invisible in every allowlisted state BO.
- **H4 supported by the added pre-registered control:** correct blend result,
  one fixed-state byte delta, unchanged PBE.
- **H5 supported:** counter 1024, unchanged target result and PBE identity.
- **H6 supported for the five exercised target formats:** physical bytes match
  the requested typed/encoded stores exactly.

## Explicit negative boundary and remaining gaps

This experiment does not locate or characterize:

- tagged BG/EOT program addresses or their low-bit tags;
- the packed BG/EOT resource-specification bit layout;
- program input/output, tilebuffer/sample/layer/invocation, or register ABI;
- which command/state record chooses clear/load/resolve/store implementations;
- program ID `0x6f` ownership or meaning. The prior single-RT fixed slot
  `+0x8c4` is zero in this relocated MRT arena for every case;
- partial background/end-of-tile, partial-save/restore, empty-tile process flags,
  or fault/retry behavior;
- MSAA/resolve, layers, mips, memoryless, private/compressed layouts, coherency,
  rotate/flip, depth/stencil, or complete MRT controls;
- complete format pack/unpack, clamp, integer, sRGB, blend, or write-mask rules;
- any A18 Pro fact.

No absence claim extends beyond the four exact BOs and fixed offsets in the
pre-registration. Locating the missing program/resource ABI requires another
pre-registered live differential with a newly established command/state role;
it must not be pursued by scanning or pointer following.

## Clean-room attestation

```text
Clean-room provenance: HW-PROBE / DATA-TRACE / OWN-SHADER / PUBLIC-hypothesis-only
Inputs inspected: authored MSL; authored RT/counter data; allocation/call metadata;
  four exact previously correlated command/state BO mappings
Apple binary introspection: NONE
Apple auxiliary/helper program bytes inspected: NONE
Compiled shader bytes inspected: NONE
Unknown BO contents inspected: NONE
Pointer following: NONE
Raw repetitions: 2 primary + 2 blend controls
Evidence: README.md reproduction, raw/, analysis/, manifest.json
```
