# EXP-0055 pre-registration — M4 scissor/depth-bias state boundary

Date frozen: 2026-08-17 (America/Los_Angeles)

Target: local Apple M4 / G16G-class GPU only. A18 Pro / G17P is untested.

Gap: `AGX_RE_INFORMATION_GAPS.md` P0.3 requires the Apple9 layouts and values
behind `isp_scissor_base`, `isp_dbias_base`, multiple scissors, empty rectangles,
and float/integer depth-bias selection. EXP-0054 established bounded public-Metal
behavior without tracing any BO. This experiment asks the next smaller question:
do one-factor public scissor and depth-bias changes produce stable byte
differentials inside two exact M4 state mappings already preclassified by clean
live evidence?

This experiment cannot close P0.3. It can at most locate reproducible candidates
inside the two permitted captures. Hardware consumption, private descriptor
meaning, Linux UAPI marshaling, integer mode, addresses outside this allowlist,
and A18 behavior remain unknown.

## Frozen clean-room boundary

This is an `HW-PROBE + DATA-TRACE + OWN-SHADER source` experiment. Inputs are
authored Objective-C/MSL, public Metal/Foundation APIs and status, authored
color/depth/guard readbacks, boundary call/allocation metadata, and only two
exact independently preclassified state mappings.

It must never inspect, disassemble, scan, or otherwise introspect an Apple
binary, executable section, framework implementation, kernel, firmware, system
shader, generated Apple helper, or auxiliary program. It must not capture or
inspect compiled shader bytes or shader/code BOs. It must not read command or
unknown BO contents, scan mappings to find state, follow or interpret a value as
a pointer, mutate executing memory, splice bytes, or replay a capture.

No value from an allowed dump may be dereferenced. Whole-dump bytewise comparison
is permitted only after the exact path and metadata preflight below succeeds;
this is a comparison inside two declared state BOs, not a scan for new BOs or
pointer-like values.

## Exact prior-classification provenance and allowlist

The only payloads that may be retained or opened are allocations whose **exact
starting GPU VA** equals:

| GPU VA | Prior M4 role | Maximum read |
| --- | --- | ---: |
| `0x58000` | `fixed-function-render-state` | `0x10000` |
| `0x68000` | `tiling-state` | `0x10000` |

This allowlist is anchored to committed `EXP-0048-bg-eot-pbe` artifact commit
`5b701aa587b15b13680a9d83854d563bcb46228a`. Its parent is
`22ab13a10e7e0a744c5f847d2c7286ba6b2c1cad`, matching that experiment's
manifest-generation revision. The committed manifest SHA-256 is
`58d518daea1fca9a45fdab16bdc681425c64eaedc97eaf7a07f773604a59dcfb`.
The manifest names the earlier live bases `EXP-M4-03-cmdstream-pipeline` and
`EXP-M4-09-cmdstream-coverage/cmd3-mrt`, and records the roles/caps above.

Two exact repeated EXP-0048 metadata anchors for a drawn Clear/Store workload
are also bound here:

| mapping | allocation/read size | metadata SHA-256 (both runs) |
| --- | ---: | --- |
| `0x58000` | `0x8000` | `f582146de68fa08599d3b6a7678b279f813a425c7ab3125f3c57e845d9211a64` |
| `0x68000` | `0x88e0` | `b4f99584fd9fe87211bdff651004bf6c2e6b7860280592aec4160ccfe9552f7c` |

The paths are
`raw/m4_20260817_run01/state_rgba8-clear-store-draw/va_{58000,68000}.meta`
and the corresponding run02 paths within EXP-0048. The EXP-0048 direct result
also identifies `0x58000 + 0x14 = 0x19` for a drawn Clear/Store path and
`0x58000 + 0x53 = 0x00` for its no-blend control. These fixed bytes are role
anchors, not a general descriptor signature or decoded enum.

The earlier experiment also proves a hazard: a client allocation once occupied
the high VA expected for an MRT descriptor. Therefore an exact VA and a tracer-
generated role string are necessary but not sufficient alone. Current captures
must additionally reproduce the expected allocation sizes, the fixed-state role
anchors where applicable, public readback, and two fresh-run differentials.

The A18-only depth-bias VA reported elsewhere and every EXP-0048 mapping other
than `0x58000`/`0x68000` are explicitly forbidden here.

## Tracer and mandatory preflight

The interposer is compile-time incapable of remembering a CPU mapping unless its
allocation start exactly equals one of the two VAs above. Nonallowlisted mapping
metadata may be logged, but no CPU address for it is retained and no byte is read.
There is exactly one post-completion snapshot per fresh probe process.

Each successful dump has exactly one `.bin`/`.meta` pair. Metadata has this
closed nine-key grammar:

```text
gpu_va
allocation_size
read_size
role
mapping_handle
mapping_occurrence
fixed_allowlist=1
pointer_following=0
command_mutation=0
```

Before any payload is opened or hashed, the runner, analyzer, manifest generator,
and verifier must validate the complete expected trial/path matrix, regular files
with no symlinks, exact pair presence, exactly nine unique well-formed keys, exact
VA/role, one mapping occurrence, boundary flags, and:

```text
file_size == read_size == allocation_size == prior expected size <= 0x10000
```

The trace must contain exactly one fixed-scope header, exactly one allowlisted
`RESOURCE_MAP` and one successful `ALLOWLIST_DUMP` per VA, no duplicate allowed
mapping, and exact handle/VA/role/allocation/cap/read linkage to the metadata and
file. A missing pair, short read, extra `.bin`/`.meta`, changed size, duplicate,
role-anchor mismatch, trace mismatch, or snapshot failure is a hard bounded stop.
The payload remains unopened and the failure is retained; capture is never widened.

## Frozen authored workload

Each trial is a new process with a fresh device/queue/resources/command buffer.
All targets are 16 x 16 RGBA8Unorm plus Depth32Float where listed. A 32-byte
prefix and suffix guard surround each retained 1024-byte authored image. The full
guarded hex, not only hashes or counts, is printed. All cases use Clear/Store,
no blending, one full-screen oversized authored triangle per scissor or depth
draw, and exact public command status/error reporting.

Single-scissor cases use an identical pipeline, viewport, geometry, draw count,
and color. Each named perturbation changes only the listed rectangle component:

| case | x | y | width | height |
| --- | ---: | ---: | ---: | ---: |
| `scissor-base` | 2 | 3 | 7 | 5 |
| `scissor-x` | 4 | 3 | 7 | 5 |
| `scissor-y` | 2 | 5 | 7 | 5 |
| `scissor-width` | 2 | 3 | 9 | 5 |
| `scissor-height` | 2 | 3 | 7 | 8 |
| `scissor-empty-width` | 2 | 3 | 0 | 5 |
| `scissor-empty-height` | 2 | 3 | 7 | 0 |

Multi-scissor cases use the same two identical viewports, the same two authored
full-screen primitives selecting viewport indices 0/1, and distinct colors:

| case | rectangle 0 | rectangle 1 | changed factor |
| --- | --- | --- | --- |
| `multi-base` | `(1,2,5,6)` | `(9,3,4,10)` | baseline |
| `multi-slot0-x` | `(2,2,5,6)` | `(9,3,4,10)` | slot 0 x only |
| `multi-slot1-x` | `(1,2,5,6)` | `(11,3,4,10)` | slot 1 x only |

Depth-bias cases use the same sloped triangle, `MTLCompareFunctionAlways`, one
draw, full scissor, and depth writes. This avoids compare-function and draw-order
changes while retaining the complete biased depth result:

| case | constant | slope | clamp |
| --- | ---: | ---: | ---: |
| `dbias-zero` | 0 | 0 | 0 |
| `dbias-constant-negative` | -1 | 0 | 0 |
| `dbias-constant-positive` | 1 | 0 | 0 |
| `dbias-slope-negative` | 0 | -1 | 0 |
| `dbias-slope-positive` | 0 | 1 | 0 |
| `dbias-large-negative` | -100000 | 0 | 0 |
| `dbias-clamp-negative` | -100000 | 0 | -0.001 |
| `dbias-large-positive` | 100000 | 0 | 0 |
| `dbias-clamp-positive` | 100000 | 0 | 0.001 |

Every case runs under two predeclared client-allocation schedules:

- `plain`: no client padding allocation;
- `pad64k`: retain one authored 65536-byte shared buffer, initialized to a fixed
  asymmetric pattern, before library/pipeline and render-resource creation.

The padding bytes and mapping are authored controls and are never captured or
inspected as BO evidence. The padded schedule is accepted only if both exact
state mappings retain their prior sizes/roles and the public readback remains
correct; otherwise it is a preserved bounded stop and contributes no payload
interpretation. This factor tests whether candidate state deltas survive a
controlled client allocation perturbation. It does not prove relocatability.

Two append-only top-level runs are mandatory. Each top-level run builds the exact
authored sources once and launches all 38 `(19 cases x 2 schedules)` trials as
fresh processes. Thus acceptance requires 76 successful independent GPU
processes, with two repeats of every exact input/schedule combination.

## Hypotheses and falsifiers

### H1 — single-scissor components have stable allowed-state differentials

Expected: changing only x, y, width, or height produces one or more identical
fixed-offset byte changes in `0x58000` or `0x68000` in both top-level runs. The
same per-factor before/after values and offsets survive the allocation schedule.
Zero width/height may select an additional representation, which is reported only
if it independently reproduces.

Falsified for a component by no allowed-state difference, changing offsets/bytes
between repeats, schedule-dependent candidate deltas, corrupted guards/readback,
or a role/preflight stop. Failure to locate a component is only a negative within
these exact capped mappings.

### H2 — two public scissor slots are structurally distinguishable

Expected: changing slot 0 x and changing slot 1 x yield reproducibly distinct or
fixed-stride-related candidate offsets, while the unchanged slot's output remains
exact. Support requires exact repeat and schedule agreement.

Falsified by indistinguishable changes that cannot separate slots, no allowed-
state difference, readback cross-slot changes, or instability. Even a fixed stride
does not establish maximum count, base pointer meaning, or hardware consumption.

### H3 — public depth-bias terms have stable allowed-state differentials

Expected: constant, slope, and sign-matched clamp perturbations yield stable
fixed-offset before/after bytes across repeats and schedules. A byte sequence is
described as an IEEE-754 input correlation only if its exact bytes equal the
authored binary32 bits at the same fixed offset in every qualifying pair.

Falsified for a term by no allowed-state difference, inconsistent offsets/bytes,
schedule sensitivity, wrong public depth output, or preflight stop. No candidate
is called an integer-mode selector or private array base.

### H4 — the fixed state-role boundary survives controlled client allocation

Expected: both schedules yield exactly one `0x58000` allocation of `0x8000` and
one `0x68000` allocation of `0x88e0`; the two fixed `0x58000` role anchors and all
case-paired candidate deltas remain stable.

Falsified by address/size/occurrence movement, anchor mismatch, missing/duplicate
mapping, or schedule-specific semantic differential. The result is then a bounded
process negative; no alternative state location may be sought in this experiment.

### H5 — behavioral readback remains consistent with EXP-0054 controls

Expected: scissor colors exactly cover their half-open rectangles; multi-slot
colors stay within their selected rectangles; depth outputs are finite and have
the expected sign/order for constant, slope, and clamp pairs; every guard is exact.

Falsified by any public command error/timeout, out-of-rectangle pixel, unexpected
depth relation, non-finite value, guard corruption, or disagreement between exact
repetitions. Failed behavior prevents interpretation of its state differential.

## Analysis rules

- Preflight all metadata and exact paths before opening or hashing any payload.
- Compare only identical-VA dumps in predeclared baseline/one-factor pairs.
- Record every changed offset and exact before/after byte; do not discard noisy or
  null differentials.
- A semantic candidate requires identical pairwise differences in both independent
  runs and both allocation schedules, plus correct full guarded readback.
- Schedule-only differences are retained as opaque allocation-correlated bytes;
  they are not decoded as addresses and are never followed.
- No unaligned value/pointer search, descriptor signature scan, or examination of
  any path outside the exact matrix is allowed.
- Structural location is not proof of hardware consumption. No native synthesis,
  Linux, kernel/firmware ownership, A18, or universal-format claim is permitted.

## Safety, retention, and acceptance

The preregistration is committed alone before the first source build or GPU run.
Builds have 60-second timeouts and each GPU process has a 45-second timeout.
Analysis/verification have hard timeouts. A process signals exactly one snapshot
only after public Metal completion and complete authored readback, then exits.

Every top-level run directory is append-only (`exist_ok=False`) and retains the
preregistration hash/commit, repository revision, exact source/tool/public-header
hashes, build argv/stdout/stderr/exit/timeout, SHA-256 and size of the two authored
build products before execution, every exact trial argv/environment/start/exit,
complete public stdout/stderr, closed trace metadata, exact allowed snapshots,
failure records, and recursive SHA-256 inventory. Build products themselves are
rebuildable temporary files and are not committed or inspected semantically.

A strict verifier must bind the committed preregistration blob and Git ancestry,
prior EXP-0048 commit/parent/manifest/hash/metadata anchors, exact 2 x 38 trial
matrix, exact file/metadata/trace grammar, preflight-before-payload ordering,
source/build/run identities, modeled guarded readbacks, raw inventories,
reproducible derived analysis, manifest coverage, and clean-room wording.

Success is at most `DATA-TRACE-VALIDATED` for stable correlations inside the two
allowed M4 state BOs. No location is a bounded negative, not evidence of absence
elsewhere. P0.3 remains `OPEN`; no shared documentation is changed by this
experiment before independent audit.

Clean-room provenance: HW-PROBE + DATA-TRACE + OWN-SHADER source
Inputs inspected: authored Objective-C/MSL and readbacks; public Metal status;
  boundary metadata; exact preclassified M4 state BOs 0x58000 and 0x68000 only
Apple binary introspection: NONE
Apple auxiliary/helper/program bytes inspected: NONE
Compiled shader bytes inspected: NONE
Command BO contents inspected: NONE
Unknown BO contents inspected: NONE
Pointer following: NONE
Generic BO/memory scan: NONE
Mutation/splice/replay: NONE
A18 Pro claim: NONE
