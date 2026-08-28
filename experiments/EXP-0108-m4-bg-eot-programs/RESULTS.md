# RESULTS — EXP-0108: M4 BG/EOT program-record ABI matrix

**Target:** local Apple M4/G16G, this host only. macOS 26.6.2, Metal 4, public IOKit
user-client selectors only. M4-only; no A18 Pro evidence exists or is claimed here.

**Officially gated evidence:** `raw/m4-20260828-run05/`, `raw/m4-20260828-run06/`, 40/40
`status=OK` in both, `verify.py --selftest`/`--seqtest` PASS, `verify.py --captured` PASS
(`run.records_reproducibly_equal`, one tolerated content-capture read-timing flake, well
under the 5-flake budget; see below). `raw_superseded/m4-20260828-run0{1,2,3,4}/` are two
earlier complete, valid, all-40-OK capture pairs, preserved untouched, superseded only by
successive refinements to the post-hoc verification gate (never by a change to the actual
data-collection code) — see `PROGRESS.md` milestones M2/M3. The headline structural finding
below (region-count delta) is byte-identical across all three pairs.

## Verdict

**PARTIAL.** P0.4 is not closed. This experiment establishes, with a byte-exact two-run
gate, a robust negative result (no distinct BG/EOT *program* record was found anywhere in
the tested 40-case/11-axis matrix) and a new positive structural result (depth and stencil
attachments are described using the *same* per-attachment k-indexed descriptor-record array
already used for color attachments, not a separate mechanism) — corroborated by two
independent single-run sightings across two different gated capture pairs, though not itself
satisfying this experiment's own two-run byte-exact requirement (see "Read-timing flakes and
the doubly-corroborated depth/stencil descriptor slot" below). Format conversion for the
tested formats is consistent with fixed-function hardware, not a program. Partial-render, at
the tested magnitude, leaves no new userspace-visible record. The tilebuffer/sample/layer
addressing ABI remains characterized only at the level already established by prior work
(tile geometry, per-attachment descriptor fields, sample-count field) — no register-level or
call-convention ABI was found, because no program was found to have one.

## 1. Tested matrix (exact)

40 cases / 11 axes, `harness/casematrix.py` (single source of truth). All render a 32x32
target unless noted.

| axis | cases | what varies |
|---|---|---|
| `action` (7) | a1..a7 | load (Clear/Load/DontCare) x store (Store/DontCare), with/without draw |
| `mrt` (3) | b2,b3,b4 | 2/3/4 RGBA8 attachments, clear/store, draw |
| `mrt-mixed` (1) | c1 | RGBA8 + R32Float, 2 attachments |
| `format` (7) | d1..d7 | BGRA8, sRGB, R32Float, R32Uint, RGBA16Float, R8Unorm, RG8Unorm |
| `msaa` (5) | e1..e5 | samples=2/4, Store / MultisampleResolve / StoreAndMultisampleResolve, Load+MSAA |
| `memoryless` (1) | f1 | memoryless color, StoreDontCare |
| `depth` (5) | g1..g5 | Private/memoryless, load Clear/Load, store Store/DontCare, with/without an enabled `MTLDepthStencilState` (write, `compareFunction=Always`) |
| `stencil` (3) | h1..h3 | Private, load Clear/Load, store Store, with/without an enabled stencil-write state |
| `depth-stencil` (1) | i1 | both depth and stencil, both write-enabled |
| `empty` (3) | j1..j3 | mrt2 / msaa4-resolve / depth-write, each with no draw |
| `partial` (4) | k1..k4 | 64x64x1-instance control vs 2048x2048 and/or 200000-instance triangle-fan-like draws, isolating target size from primitive count |

## 2. OBSERVED vs INTERPRETED

### 2.1 No distinct BG/EOT program record was found (H1 REFUTED for the tested matrix)

**OBSERVED:** The 4GiB-aligned code window (`0x10000000000`, established by EXP-0042 as
where our own compiled VS/FS machine code lives) is exactly `0x10000` bytes in **every one
of the 40 cases, in both officially gated runs** (and in both superseded pairs). Its content
is never read into any committed artifact (see `PRE_REGISTRATION.md` section 6); only its
size is used as a self-check. No other captured region, across the full inventory of every
BO the process registers via IOKit's resource-map selector (not a fixed four-BO allowlist,
per `harness/wtrace.c`), was found whose presence/size/content correlates with configuration
in a way consistent with a distinct executable program.

**INTERPRETED:** Across the tested matrix (load/store action x7, MRT count x3, mixed format,
format x7, MSAA+resolve x5, memoryless, depth x5, stencil x3, combined depth+stencil, empty
x3, partial-render x4), userspace's own visible state never grows a new executable-shaped
region and the shader-code window never changes size. If Apple's driver supplies a BG/EOT
program to firmware for these operations, either (a) it is a fixed, canonical, single
routine whose identity/address never appears to change across this matrix and that this
broadened trace did not distinguish from firmware-resident logic, or (b) these operations
are genuinely fixed-function (silicon/firmware-resident, table/tag-selected) with no
per-configuration userspace-supplied executable code at all. This experiment cannot
distinguish (a) from (b); either way, **no program bytes, pointer, or tag were located for
any tested configuration.**

**NOT REFUTED / open:** a program could exist for a configuration outside this matrix
(e.g. an actual programmable-blend/logic-op capability Metal doesn't expose, or a format
this matrix didn't test).

### 2.2 Depth and stencil each add exactly one region; format changes add none (H2 SUPPORTED, refines EXP-0048)

**OBSERVED**, byte-exact, VA-free (size-only multiset, gate-proven address-independent),
reproduced identically across all three independent capture pairs:

| case (relative to `a1-clear-store-draw` baseline) | region-count delta |
|---|---|
| `g1`..`g5` (depth, Private storage, any load/store/write combination) | `{0x20000: +1}` |
| `g3-depth-memoryless-write` (depth, **memoryless** storage) | `{}` (no delta) |
| `h1`..`h3` (stencil, Private storage) | `{0x20000: +1}` |
| `i1-depth-stencil-write` (both, both Private) | `{0x20000: +2}` (additive) |
| `d1`..`d7` (format only, no depth/stencil/MRT change) | `{}` (no delta, every format) |

This directly refines EXP-0048's "depth store-action/ZLS is firmware-managed (not captured)"
claim: a depth- or stencil-attachment-correlated captured region **does** exist in userspace-
visible state, is absent specifically when the attachment is memoryless (consistent with the
existing documented finding "memoryless depth omits the depth surface VA that private depth
embeds"), and is fully additive for combined depth+stencil. This is a genuine new record,
distinct from the four EXP-0048 roles and from the six already-documented PBE format/control
variants.

**INTERPRETED:** the new region is per-attachment-type state directly tied to whether the
depth/stencil attachment has real (non-memoryless) backing that needs a resource
specification — consistent with, though not proof of, a depth/stencil resource-specifier
record analogous to the color attachment's PBE descriptor. Section 2.3 provides direct
structural content evidence (not just a count delta) that this is exactly what it is.

**NOT (yet) established from the gated count-delta alone:** its exact field layout (that
required the field-level content in 2.3, which is only partially/doubly-corroborated, not
gate-proven).

### 2.3 Read-timing flakes and the doubly-corroborated depth/stencil descriptor slot

**OBSERVED (harness reliability, not hardware):** across the 6 total gated runs (2 per pair
x 3 pairs), a named role that is present with identical size in both runs of a pair
occasionally has `content_captured=False` in exactly one of the two runs — a
`mach_vm_read_overwrite` race in the SIGUSR1 snapshot handler, confirmed harness-side because
role/size are otherwise identical and the flake lands on a different case each time (case
`g2-depth-write` in the run03/run04 pair; case `i1-depth-stencil-write` in the officially
gated run05/run06 pair). `verify.py`'s gate (`run.records_reproducibly_equal`) tolerates
exactly this asymmetry (proven by `flake_tolerance_self_check` and the real gated run),
under a hard budget of <=5 such flakes across the 40-case matrix (1 was observed in the
official pair).

**OBSERVED, when the read succeeds** (single-run per sighting, but two *independent*
sightings, from two *different* gated pairs, are byte-identical where they overlap): the
`mrt-attachment-descriptors` region's k-indexed record array — already established
(EXP-0048/EXP-M4-09) as the fixed-stride 0x20-byte-record LOAD(+0x20+k*0x20)/
STORE(+0x220+k*0x20) array used for k=0..(ncolor-1) color attachments — has **additional
populated records beyond k=(ncolor-1)** when depth and/or stencil are present:

- `g2-depth-write` (1 color attachment, depth only; run03, one run of the run03/run04 pair):
  k=1 LOAD/STORE populated.
- `i1-depth-stencil-write` (1 color attachment, depth AND stencil; run06, one run of the
  **officially gated** run05/run06 pair): k=1 **and** k=2 LOAD/STORE populated.
- `g2`'s k=1 LOAD record (`628800f8017c0008` + masked-address + `8010610000100000...`) and
  `i1`'s k=1 LOAD record are **byte-identical**, even though they come from two different
  cases in two different gated runs — the two depth configurations are otherwise identical
  (Depth32Float, clear 0.75, Clear/Store, Private storage), which is exactly what predicts
  byte-identical descriptor content if k=1 is genuinely "the depth attachment's own record."
  `i1`'s k=2 record is new/additional relative to `g2` and is byte-distinct from k=1 only in
  a small number of bytes (see below) — consistent with "k=2 is the stencil attachment's own
  record," appended after depth.

Structural byte comparison (own-tool hex analysis of the captured descriptor bytes, the same
class of activity as EXP-0048/EXP-M4-08/09's field-level decoding — no code disassembly, no
pointer following beyond the already-established address-reconstruction formula):

```text
k0 (color, RGBA8Unorm)  LOAD: 02 0a 88 f6 01 7c 00 00 [addr...] 00 c0 03 00 ...
k1 (depth, Depth32Float) LOAD: 62 88 00 f8 01 7c 00 08 [addr...] 00 00 80 10 61 00 00 10 00 ...
k2 (stencil, Stencil8)   LOAD: 22 40 68 f9 01 7c 00 08 [addr...] 00 00 80 60 61 00 00 10 00 ...
```

Bytes 4-7 (`01 7c 00 08` LOAD / `c0 07 00 08` STORE, not shown) match the already-established
width-1/height-1 packing for a 32x32 target in both the depth and stencil records, exactly as
for color. Byte 3's top nibble is `0xf` in all three (`f6`/`f8`/`f9`), matching the
already-documented "(0xf<<28)|..." format-word top-nibble convention (EXP-M4-08/09). The
depth and stencil records differ from each other in only a handful of bytes, most visibly at
record offset +0x10 (`10` for depth vs `60` for stencil) — a plausible per-slot/attachment-
type selector, not decoded further here.

**Evidence label: STRUCTURAL / doubly-corroborated, NOT byte-exact-gated.** These specific
field values did not satisfy this experiment's own two-run byte-exact requirement for the
*reason* stated above (a harness read race, not a hardware property) — they are reported
because two *independent* gated-run sightings agree exactly where they overlap (k=1 depth
content) and are internally consistent (k=2 appears only when stencil is additionally
present). This is reported as a strong lead, not a validated fact: **a follow-up experiment
should fix the SIGUSR1 read race (e.g. retry-on-failure, or a synchronous post-snapshot
read-verification pass) and re-run specifically the depth/stencil cases to obtain a
genuinely two-run byte-exact confirmation** before this is promoted to `docs/`.

### 2.4 Load/store action, MRT, MSAA, and format changes are visible only as content changes in already-known roles (H3 SUPPORTED for tested formats)

**OBSERVED**, using only the roles whose whole-region content was cross-run-reproducible in
the officially gated pair (`vdm-command-state`, `fixed-function-render-state`, and a small
fixed-VA role this experiment calls `attachment-slot-b`, present regardless of depth/stencil
and therefore NOT itself the depth/stencil-specific region of 2.2/2.3 — its own role is
unresolved, see "what remains" below):

| axis | vdm-command-state varies | fixed-function-render-state varies | attachment-slot-b varies |
|---|---|---|---|
| `action` (7 cases) | yes | yes | yes |
| `depth` (5 cases) | no | yes | no |
| `stencil` (3 cases) | no | yes | no |
| `format` (7 cases) | no | no | yes |
| `mrt` (3 cases) | yes | yes | yes |
| `msaa` (5 cases) | yes | yes | yes |
| `partial` (4 cases, target size/instance count) | yes | yes | (role absent from this axis's cases) |

No axis introduces a distinct new BO role beyond what 2.2 already isolates for depth/
stencil. Format changes are visible in `attachment-slot-b` and in the already-documented
per-attachment color-descriptor k-record format word (field-level content differs per format
in every tested case, confirming EXP-0048/EXP-M4-08/09's existing per-format encoding); they
are **not** visible in `vdm-command-state` or `fixed-function-render-state`, and — critically
for H3 — **no region ever appears or disappears specifically because of a format change**
(2.2's format row: zero delta for every one of 7 formats including RGBA16Float, which would
plausibly need real narrowing/packing logic if any program-level conversion existed).

**INTERPRETED:** for the 7 tested formats (BGRA8Unorm, RGBA8Unorm_sRGB, R32Float, R32Uint,
RGBA16Float, R8Unorm, RG8Unorm; plus RGBA8Unorm as the baseline), conversion is consistent
with fixed-function hardware keyed by the descriptor's format-code field (already documented,
EXP-0048/EXP-M4-08/09), not a userspace/driver-supplied program — because (2.1) no program
of any kind was found for any format, and (2.2) format changes never add/remove a captured
region. This is a **negative** result about program *existence*, not a full pack/unpack rule
characterization (P1.2/EXP-0070/EXP-0079 already own that question in more depth for the
conversion *rules themselves*).

**Caveat:** `attachment-slot-b`'s own field-level content was not extracted in this
experiment (only the two color-descriptor roles got field-level windows); its correlation
with action/format/MRT/MSAA is a real, reproducible, gated fact, but its role and exact
changed bytes are UNKNOWN and are natural next-step work.

### 2.5 Partial-render probe: no new record at the tested magnitude (H4 SUPPORTED, bounded)

**OBSERVED:** `k1` (64x64 target, 1 triangle instance) vs `k2`/`k3`/`k4` (2048x2048 and/or
200,000 instances of a near-full-screen triangle, isolating target size from primitive
count) show the same three control roles varying (`vdm-command-state`,
`fixed-function-render-state`, `tiling-state` — the last is a `known_noisy_named_role` at the
whole-region level in this experiment, so this specific role's variation is not itself
gate-proven, only suggestive) with no new role appearing and no captured region growing
beyond ordinary geometry/viewport-sized content (the `tiling-state` region's own *size*,
`0x88e0`, is identical for every one of the 40 cases including all 4 partial-axis cases, in
both gated runs).

**INTERPRETED:** at this magnitude (up to 4M target pixels, up to ~600,000 triangles), no
distinct userspace-visible partial-BG/partial-EOT record was found. This does **not**
establish that partial-render never occurs at this scale, nor characterize its trigger
condition: (a) command-buffer completion status and readback correctness alone (both
observed OK/correct in this experiment) do not distinguish a single-pass render from a
multi-pass/partial-render sequence executed transparently by firmware; (b) if partial-render
bookkeeping exists, it may live entirely in GPU-private (non-CPU-mapped) allocations outside
this tracer's sel-9-registration-based visibility, exactly as `docs/pipeline/README.md`
already states for the general overflow-to-partial-render trigger ("firmware-managed — no
userspace knob"). This experiment adds a bounded confirmation (no *new userspace-visible
record type* appears, up to the tested magnitude) but does not add trigger-condition or
firmware-interface evidence.

### 2.6 Exploratory-only finding, not part of the gated matrix: depth/stencil clear-value array

**Clean-room / evidence-strength note:** during pre-freeze harness development (`dev/`,
deleted before freezing; see `PROGRESS.md`), an earlier, simpler (non-JSON-config-driven)
version of the probe was used to explore the state surface. In that exploratory harness, a
0x20000-byte "unnamed" region appearing only when a depth or stencil attachment was present
(at an allocation-order-relative VA, not a fixed one) contained, at offset 0, exactly 8
repeated little-endian 4-byte copies of the authored `clearDepth` float (tested at 1.0) or,
for stencil, 8 zero bytes matching an authored `clearStencil=0`. This is a plausible and
attractive candidate for "the depth/stencil clear-value array" (structurally analogous to
the already-documented per-attachment RGBA clear-color float4 array, EXP-M4-09/CMD-3), but:

- it was observed in a **single, informal, non-gated run**, under a harness revision that no
  longer exists in its exact form (the frozen `harness/probe.m` differs in allocation order);
- an attempt to relocate this candidate deterministically by VA arithmetic in the frozen
  harness **failed** — the offset between a client buffer's own registration and "the next
  slab" shifted between two harness revisions that differed only in unrelated JSON-parsing
  code executed before the Metal calls (see `run.py`'s dropped-heuristic note) — confirming
  it is allocation-order-sensitive, not a fixed hardware-facing offset;
- it was **not independently reproduced** under the frozen two-run gate.

**Evidence label: INFERRED (single observation, method later shown fragile).** Reported here
because it is a specific, falsifiable, and plausible lead, per CODEX's "do not quietly drop
what was tried." A follow-up experiment should locate it (or refute it) using a content-
agnostic structural signal computed at capture time (e.g. an interposer-side periodicity/
repeated-word classifier over every captured region, so identification never depends on
allocation-order VA arithmetic), and should vary `clearDepth`/`clearStencil` to
asymmetric, non-1.0/non-0 values to rule out coincidence.

## 3. Tilebuffer addressing, sample/layer selection, and register-level ABI

**No new information was obtained beyond what prior work already establishes** (tile fixed
at 32x32, `docs/pipeline/README.md`; per-attachment color/now depth/stencil descriptor
records with format/dimension/surface-address fields per section 2.3; MSAA sample-count
field in the attachment descriptor `+0x24`; programmable sample positions at a separate fixed
client BO, EXP-0021/RT-4). Because no BG/EOT *program* was found to exist at all (2.1), there
is no register file, calling convention, or instruction-level tilebuffer-load/store ABI to
characterize from this experiment's evidence — the "ABI" observable here is entirely
descriptor/config-field-driven, not a call convention with inputs/outputs/registers. If a
BG/EOT program genuinely does not exist on Apple's implementation for the tested operations
(hypothesis (b) in 2.1), then the Linux driver's equivalent, if it needs one at all, is
likely to be its **own** synthesized routine consuming these same descriptor fields directly,
rather than a reverse-engineered copy of an Apple-authored one — which is squarely
compatible with this project's clean-room mandate (P0.4 explicitly requires independently
generated, authored programs, never a decoded Apple template).

## 4. What P0.4 still requires

Per the closure rules in `docs/P0-P1-CLOSURE.md` and this experiment's own honest scoping
(`PRE_REGISTRATION.md` section 9), still open after this experiment:

- **Whether a BG/EOT program exists at all on this hardware**, and if so, its address/tag/
  resource-specification bit layout — not located here across the tested 40-case matrix; the
  strongest evidence obtained is a *negative* (no such record was found to vary with
  configuration, and the one plausible executable-code region, EXP-0042's code window, never
  changes size).
- **The exact depth/stencil descriptor-slot field layout** (section 2.3): doubly-corroborated
  but not two-run byte-exact-gated; needs a harness fix (SIGUSR1 read-race) and a
  re-targeted, gated capture.
- **`attachment-slot-b`'s role and field-level content** (section 2.4): a real, reproducible,
  gated correlation with action/format/MRT/MSAA with no field-level decoding performed here.
- Independently generated, authored BG/EOT programs the hardware actually consumes and
  executes (P0.4's closure rule 1 — "generated, not merely decoded") — categorically out of
  this experiment's scope (no program was even located to attempt generating an analog of).
- Partial-render/partial-BG/partial-EOT trigger condition and any firmware-interface fields —
  not reached; bounded only to "no new *userspace-visible record* at the tested magnitude."
- Complete pack/unpack/clamp/blend/write-mask rules for the depth/stencil path and for the
  7 tested plus untested formats (owned in more depth by P1.2/EXP-0070/EXP-0079).
- Layered/array rendering, mip levels beyond 0, compressed/ASTC/BC formats, sparse residency,
  indirect/ICB-driven render passes: untested (`PRE_REGISTRATION.md` section 9).
- Any A18 Pro replication (M4-only per current target discipline).

## 5. Gate results

`verify.py --selftest`: PASS (18 checks, including `masking_self_check`,
`projection_self_check`, and `flake_tolerance_self_check` unit tests, plus full-pipeline
mutators proving both that a tampered semantic field always fails the gate and that a
tampered/asymmetric non-deterministic field (timing, named-role whole-region sha256, and a
single content-capture read flake) never does).
`verify.py --seqtest`: PASS (10 checks; `--preflight`/`--between-runs`/`--captured` are each
satisfiable only in their own tree state — `PRE_GPU`/`RUN01_PRESENT`/`RUN02_PRESENT`).
NON-RECORDED smoke gate: PASS, both official runs (one throwaway case into `work/`, before
any `raw/` artifact, per `run.py smoke_gate`).
`verify.py --captured` (officially gated pair `m4-20260828-run05`/`m4-20260828-run06`):
**PASS.** 40/40 `status=OK` both runs; cross-run byte-exact on the reproducible projection
of every case, tolerating exactly 1 content-capture read-timing flake (budget: <=5).
Two earlier full capture pairs (`raw_superseded/`) are preserved as evidence of the gate's
own iterative hardening; see `PROGRESS.md` milestones M2/M3 and `run.py`'s `RUNS`-constant
comment for the exact history.

## Clean-room provenance

```text
Clean-room provenance: HW-PROBE / DATA-TRACE / OWN-SHADER
Inputs inspected: complete authored MSL generated per case from harness/probe.m; authored
  render-pass config JSON; IOKit call/resource-map metadata for every BO the process
  registers; capped content for a pre-registered, bounded set of small structured control/
  descriptor regions (PRE_REGISTRATION.md section 6); structural (offset/byte-pattern) hex
  analysis of descriptor-class content only, never of the excluded code window
Apple binary introspection: NONE
Apple auxiliary/helper program bytes committed: NONE (hash-only outside the bounded named-
  role set; the code window is excluded from content capture entirely, by construction in
  harness/wtrace.c, never merely by policy statement)
Pointer following: NONE (region identification is either a fixed named VA or a VA-free
  size/hash comparison; the one address-reconstruction formula used, EXP-0048/EXP-M4-08's
  low40<<4, is applied only to already-established color/depth/stencil descriptor k-records,
  never to select or follow into another region's content)
Reproduction: see README.md
Evidence: raw/m4-20260828-run05/, raw/m4-20260828-run06/, raw_superseded/ (historical),
  analysis.json, manifest.json
```
