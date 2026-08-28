# EXP-0110 results: M4 command/container relocation, link grammar,
# state-packet fields, and shader-container/metadata split

## Verdict

**PARTIAL for both P0.5 and P0.7; substantive, bounded advances on both.**
Neither row closes here (closure requires independent generation +
hardware-consumer proof, per `docs/P0-P1-CLOSURE.md`'s six rules). What
this experiment adds beyond EXP-0043/EXP-0049/EXP-0042/EXP-0019/EXP-0024:

- **P0.5 relocation**: the CDM (compute) command-segment chain is
  **client-heap-relative** (moves under 64 MiB of authored padding, by a
  single uniform delta across every segment in the chain) and
  **queue-invariant** (unaffected by 4 additional command queues created
  and used before the probe). The VDM/FF-state chain is the OPPOSITE:
  **invariant under both** the same padding and additional queues/draws.
  This is the first evidence distinguishing relocation behavior BY
  STRUCTURE KIND, not just a second observed target.
- **P0.5 link/chain grammar**: the split-address link transform
  (`target = ((hi32 & 0xffffff) << 32) | lo32`, `tag = hi32 >> 24`) is now
  confirmed against **four distinct target addresses** (two unpadded, two
  under a real 64 MiB relocation) for CDM, and reproduced for VDM at a
  previously-unseen target. Segment capacity is confirmed **uniform across
  first AND continuation segments** (every CDM segment holds exactly 732
  records regardless of position in the chain).
- **P0.5 state-packet schema**: the entire EXP-0019 FF-state pool bit
  layout and VDM bind-pair template (documented A18-only) is reproduced
  **byte-exact on M4** for depth/stencil/blend/cull, closing an M4
  validation gap those rows never had. One previously undocumented field
  is newly observed (`0x58000+0x34` bit 18).
- **P0.7 container**: two new metadata fields (`1`, `3`) track bound-buffer
  count and two more (`38`, `42`) flag texture presence -- none previously
  documented. A live dispatch cross-check shows the CDM launch record is
  **byte-identical regardless of buffer count** while the argument-buffer
  table entry count tracks the compiler's actual (post-dead-code-
  elimination) resource usage, not the raw API binding count -- direct
  evidence for the firmware-consumed vs archive-bookkeeping split the row
  requires.

All results are M4/G16G only (macOS 26.6.2, Metal 4). No A18 Pro/G17P
result exists; per `CLAUDE.md`, the A18 is Apple9-equal for driver-emittable
subsystems, so this is treated as the operational Apple9 evidence, but any
G17P-specific claim would need a direct run.

## Gate results

- `verify.py --selftest`: **15/15 PASS** (synthetic two-run fixture at
  different absolute addresses produces byte-identical gated output;
  corruption/dangling-link/cycle cases correctly rejected/flagged; no
  address-shaped key name in the frozen schema).
- `verify.py --seqtest`: **11/11 PASS** (PRE_GPU/RUN01_PRESENT/RUN02_PRESENT
  gate applicability).
- Smoke gate: **PASSED** before `raw/` was created, both runs.
- `verify.py --captured`: **PASS** -- 31/31 cases' GATED records
  (`02_results.jsonl`) byte-identical between `m4_20260827_run01` and
  `m4_20260827_run02`, with zero mismatches (`analysis/cross_run_report.json`).
  No GPU address appears in that file (`schema.assert_no_address_leak`);
  raw addresses live only in the non-gated `02_results_addrs.jsonl`
  sibling, which legitimately differs between the two runs (confirmed --
  see below).
- Both runs: 31/31 cases `status=ok`, Metal command-buffer status 4, no
  timeout, no fault, no reboot. Results hash identical between the debug
  dry run and both official runs (`9518a9eb...`), i.e. the whole pipeline
  is deterministic at the gated-fact level across three independent
  process-tree executions.
- **Disclosed process deviation (corrected before any evidentiary capture
  existed):** informal pre-freeze calibration built and ran `iotrace.dylib`
  from a path outside the repo, and `verify.py` initially used
  `tempfile.mkdtemp()` with no `dir=` (system temp default). Both are fixed
  (calibration artifacts deleted; `verify.py` now builds scratch under
  `work/selftest_scratch/`). `raw/` was empty when both were found; no
  promoted fact depends on the deviation. See `PROGRESS.md`.

## 1. Relocation (P0.5, task 1)

### Observed

| case | chain (segment count) | delta vs same-run baseline | interpretation |
|---|---|---:|---|
| `cdm_baseline` | 3 segments, 732/732/36 records | 0 (is the baseline) | -- |
| `cdm_pq4` (4 prior queues, each used) | 1 segment (count=2) | **0** | CDM base unaffected by additional queues |
| `cdm_pad_small` (8x4 KiB padding) | 3 segments, 732/732/36 | **0** | matches EXP-0043/EXP-0049's small-padding negative |
| `cdm_pad_big` (16x4 MiB = 64 MiB padding) | 3 segments, 732/732/36 | **+67633152 (0x4080000), uniform on all 3 segments** | CDM chain relocated as one contiguously-shifted region |
| `vdm_baseline` | 2 segments, 603/97 records | 0 (is the baseline) | -- |
| `vdm_pqdraw4` (4 prior queues, each drawing) | 1 segment (count=10) | **0** | VDM base unaffected by additional draw-issuing queues |
| `vdm_pad_big` (64 MiB padding) | 2 segments, 603/97 | **0** | VDM base unaffected by the SAME padding that moved CDM |

(Exact chain VAs, kept out of the gated payload per the capture contract,
are in `raw/*/02_results_addrs.jsonl`: `cdm_baseline` =
`[0x100000b0000, 0x10000150000, 0x100001e0000]`; `cdm_pad_big` =
`[0x10004130000, 0x100041d0000, 0x10004260000]`, each element exactly
`0x4080000` above its baseline counterpart; `vdm_baseline` =
`vdm_pad_big` = `[0x18000, 0x78000]`, unchanged.)

### Interpreted

- The CDM command-segment chain lives in the **general client-visible GPU
  VM heap** -- the same address family ordinary buffers/textures come
  from (`0x100000xxxxx`-style addresses observed adjacent to client
  resources throughout this experiment and prior ones). It is therefore
  genuinely **relocatable** in the ordinary sense: growing the client
  allocation load before it is built moves it, uniformly, by the same
  amount client allocations moved. This directly supports treating CDM
  command-stream placement as an ordinary BO the driver can place anywhere
  legal, consistent with what an unchanged Asahi UAPI expects userspace to
  manage.
- The VDM + FF-state-pool chain lives in a **small, low, per-queue-context
  address range** (`0x18000`/`0x58000`/`0x68000`/`0x48000`-family) that
  did not move under either perturbation tested here. Combined with
  EXP-0043/EXP-0049's identical negative result under smaller padding,
  this is now DATA-TRACE-VALIDATED for the tested load range (up to 64
  MiB), not merely a single unchallenged observation. Two explanations
  remain open and are NOT distinguished by this experiment: (a) a
  genuinely fixed low-VA region reserved per queue/context regardless of
  client heap size, or (b) a region sized/placed independently of the
  *client* allocator specifically (e.g. from a separate firmware-context
  allocator) that would still move under a perturbation this experiment
  did not try (e.g. many additional simultaneous queues, or exhausting
  that region's own capacity).
- **Queue-relative addressing is REFUTED for both structures** in the
  tested range (up to 4 additional queues, with or without those queues
  actually drawing): neither the CDM nor VDM base is queue-indexed. An
  **unresolved, non-reproduced side observation** from informal
  calibration (not part of the gated captures, see PRE_REGISTRATION.md
  "Confounders") saw two distinct sel-9 registrations report the identical
  GPU VA `0x18000` with different CPU-side mappings and different content
  for a `--prior-queues --prior-draws` case; the formal `vdm_pqdraw4` case
  in both official runs shows only one such registration. This is recorded
  as `UNKNOWN`, not promoted -- a dedicated follow-up (vary prior-queue
  count further, and inspect the SIGUSR1 timing more precisely) is needed.

## 2. Link/chain grammar (P0.5, task 2)

### Observed

The link transform `decode_link(hi32, lo32) = (tag, target)` where
`tag = hi32 >> 24` and `target = ((hi32 & 0x00ffffff) << 32) | lo32`
(`analysis/scan.py`) correctly predicted the ACTUAL next segment's address
in **every** linked case in both runs (`transform_ok: true` for all 4
link-bearing segments: `cdm_baseline` seg0/seg1, `cdm_pad_big` seg0/seg1,
`vdm_baseline`/`vdm_pad_big` seg0) -- six independent confirmations across
**four distinct target addresses** for CDM (`0x10000150000`,
`0x100001e0000`, `0x100041d0000`, `0x10004260000`) and one for VDM
(`0x78000`, distinct from EXP-0043/EXP-0049's previously-recorded
`0x88000`).

Tag byte: **CDM = `0x20`** (constant across all 4 CDM link instances
observed here plus EXP-0043/EXP-0049's original pair); **VDM = `0x80`**
(constant across 2 instances here plus EXP-0043/EXP-0049's original pair).

Segment capacity: **every** CDM segment in the 3-segment chain -- the
first AND both continuations -- holds exactly **732** records of the
tested 0x2c-byte shape before rolling over (`1500 = 732 + 732 + 36`); the
terminator/link decision point is therefore a fixed per-segment capacity,
not a property only of the first segment. VDM capacity for the tested
draw shape (identical fragment-color/no-explicit-state-per-draw pattern)
is **603** records for the first segment; this experiment did not push a
VDM chain to a third segment, so continuation-capacity uniformity is
established for CDM only, not yet for VDM.

Terminator words: CDM = `0x40000000` (unlinked case, `cdm_pq4`); VDM =
implicit in every non-link `tail_kind: terminator` segment (`0xc0000000`,
per `analysis/scan.py`'s constant, confirmed in every terminal segment of
both runs).

### Interpreted

- **H3 (link transform generalizes) is SUPPORTED**, now over 4 distinct
  targets including two obtained under a genuine 64 MiB relocation --
  materially stronger than EXP-0043/EXP-0049's single fixed pair. This
  raises the evidence strength for the split-address ENCODING RULE (not
  yet the full packet) from `STRUCTURAL` toward `DATA-TRACE-VALIDATED`:
  the same formula, applied fresh at capture time (never hand-derived
  from a known answer), correctly locates a segment whose address was not
  known in advance of the run.
- **H4 (fixed capacity) is SUPPORTED for CDM**: 732 records/segment is a
  reproducible constant across chain position and across the unpadded vs.
  64-MiB-shifted allocation condition. `732 * 0x2c = 0x7dd0`; the segment
  BO itself is `0x8000` bytes, leaving `0x230` bytes of trailing padding
  after the 8-byte terminator/link -- consistent across all four
  chain-bearing CDM cases in both runs.
- This remains **short of `HW-VALIDATED`**: no link byte was independently
  constructed and executed by this experiment (no splice-and-observe). The
  correct next step named in EXP-0043's own "shortest route to
  HW-VALIDATED" note -- generate a second segment at a deliberately moved
  VA, patch only the captured link address, execute with a watchdog, and
  verify correct completion -- was not attempted here (out of scope for
  the time available; flagged as the concrete follow-up).

## 3. State-packet schema (P0.5, task 3)

### Observed

The VDM bind-pair template at the M4 addresses discovered for
`state_baseline` (pool base auto-detected by address-cluster analysis,
`analysis/scan.find_pool_base`, not assumed) is, in order:

| control | address (delta from pool base) | target |
|---|---:|---|
| `0x0500` | `-0x57e40` (i.e. `0x1c0`, a small immediate, NOT pool-relative) | immediate |
| `0x0700` | `0x0` | pool base |
| `0x0500` | `0x1c` | pool+0x1c |
| `0x0700` | `0x30` | pool+0x30 |
| `0x0500` | `0x4c` | pool+0x4c |
| `0x0a00` | `0x10900` | viewport (pool+0x10900 = `0x68900`) |
| `0x0300` | `0x60` | pool+0x60 |
| `0x0200` | `0x6c` | pool+0x6c |
| `0x0200` | `-0x10000` | context block (pool-0x10000 = `0x48000`) |

This is **byte-exact against EXP-0019's A18-documented template**
(control words AND target sub-offsets all match; only the first
"immediate" pair's value differs, expected since it is a state-dependent
literal, not a pointer). This is the first M4 reproduction of that
template (EXP-0019/EXP-0024 were captured on A18 Pro only).

The `0x58000`-equivalent pool's field decode, swept one Metal draw-state
parameter at a time against an all-off baseline:

| field | baseline (all off) | depth only | stencil only | blend only | cull=back only | all four |
|---|---|---|---|---|---|---|
| `+0x34` flags | `0x00040200` | `0x00000200` | `0x000c0200` | `0x00040200` | `0x00040200` | `0x000c0200` |
| `+0x38/+0x40` depth word | `0x07200f00` | `0x01000f00` | `0x07200f01` | `0x07200f00` | `0x07200f00` | `0x01000f01` |
| `+0x3c/+0x44` stencil word | `0x0e000000` | `0x0e000000` | `0x0e02ffff` | `0x0e000000` | `0x0e000000` | `0x0e02ffff` |
| `+0x50` blend/store | `0x00000200` | `0x00000200` | `0x00000200` | `0x20000200` | `0x00000200` | `0x20000200` |
| `+0x70` raster | `0x00000480` | `0x00000480` | `0x00000480` | `0x00000480` | `0x00000482` | `0x00000482` |

Every value except `+0x34`'s baseline/depth-only bit 18 reproduces
EXP-0019's documented A18 decode exactly: depth compare code `1`=less
write-enabled when depth is on, disabled-pattern `0x07200f00`
(compare=always, write-disabled) when off; stencil reference `0x01` (byte
0) plus write/read masks `0xff`/`0xff` and pass-op `2`=replace,
compare-code `7`=always when stencil is on, disabled-pattern `0x0e000000`
when off; blend `0x20000200` vs `0x00000200`; cull `0x482` (back, code 2)
vs `0x480` (none).

**Newly observed, not in EXP-0019/EXP-0024:** `+0x34` bit 18 (`0x00040000`)
is **set in the all-off baseline** and **clears the instant either depth
or stencil is configured at all** (present in `state_baseline`/
`state_blend`/`state_cull_back` -- none of which touch depth/stencil --
absent in `state_depth`/`state_stencil`/`state_all`). EXP-0019 never
observed this because its own baseline already had depth+stencil enabled.
Interpretation: bit 18 looks like a "no depth/stencil state bound at all"
indicator (distinct from the documented bits 19:18 "stencil test enable"
pair -- bit 18 alone, with bit 19 clear, is neither the `0xc0000`
stencil-enable pattern nor previously attributed to anything), not
independently validated further here.

### Interpreted

- **H5 is SUPPORTED**: the A18 bind-pair template and pool field layout
  reproduce byte-exact on M4. This closes the "M4 was never tested for
  this" gap for the fixed-function state model specifically (EXP-0019/
  EXP-0024's underlying claims were previously `INFERRED`-for-M4 only via
  the general A18=M4 byte-identity finding, `EXP-M4-*`; this is now a
  direct M4 DATA-TRACE confirmation for this specific structure).
  Evidence: `DATA-TRACE-VALIDATED` (both runs, cross-run gated-identical).
- The VDM control-word "nibble" question (task 3's second half) is only
  **partially advanced**: this experiment independently rediscovered the
  exact nibble-to-sub-block correlation EXP-0019 already inferred
  (`0x0700`->pool-block starts, `0x0500`->pool-block continuations,
  `0x0a00`->viewport, `0x0300`/`0x0200`->raster/context), confirming it
  holds on M4, but did **not** newly determine WHY those specific nibble
  values are chosen (no case here changed which nibble a given target
  used). That remains `INFERRED`, as it was before this experiment.

## 4. Container/metadata (P0.7, task 4)

### Observed

`__GPU_METADATA` field survey (`analysis/metadata.py`, archive-only, no
dispatch) across the buffer-count sweep:

| kernel | live buffers (post dead-code-elim) | field 0 (GPR) | field 1 | field 3 |
|---|---:|---:|---:|---:|
| `kbuf0` (0 declared) | 0 | 1 | absent | absent |
| `kbuf1` (1 declared, `b0[i]=b0[i]`) | **0** (eliminated) | 1 | absent | absent |
| `kbuf2` | 2 | 3 | `4` | `16` |
| `kbuf4` | 4 | 6 | `8` | `32` |
| `kbuf8` | 8 | 12 | `16` | `64` |

Field 1 = `2 * nbuf`, field 3 = `8 * nbuf`, for `nbuf >= 2` in this
buffer-only sweep. But the same fields do NOT follow that formula in the
texture sweep: `ktex0_samp0` (1 live buffer, 0 textures) shows field
1=`4`, field 3=`8` -- the values a buffer-only `nbuf=2` case would show,
not `nbuf=1`. **This inconsistency is reported as observed and
UNRESOLVED**, not force-fit to a single formula (`kbuf1`'s single buffer
was almost certainly dead-code-eliminated as a `b0[i]=b0[i]` no-op, which
`ktex0_samp0`'s genuinely-live `out[i]=acc` write is not -- the two
kernels are not directly comparable at "nbuf=1").

Two new fields, never previously documented, appear ONLY when a texture is
declared: field `38` and field `42`, both constant value `8`, present for
every texture/sampler combination tested (`1..4` textures, `0..2`
samplers) and absent for all buffer-only kernels. Because `38`/`42` do not
scale with texture OR sampler count (always exactly `8`), they read as a
boolean "uses a texture-class resource" flag pair, not a count.

Sanity cross-check (not a new claim): the GPR-pressure ladder reproduces
the already-established facts from EXP-0020/EXP-0041/EXP-M4-09 inside this
experiment's own framework: field 0 caps at exactly 96 (`kpress96`), field
41 (scratch bytes) appears only once field 0 hits 96 (`kpress96`: `48`
bytes), and field 32 appears only for the two highest-pressure kernels
(`kpress32`, `kpress96`) -- consistent with EXP-M4-09's "field 32 presence
== occupancy tier" finding.

Live cross-check (`containerdispatch.m` + `tools/iotrace`, dispatching the
`kbuf{0,1,2,4,8}` kernels with 0/1/2/4/8 REAL bound buffers):

| kernel | bound buffers | argument-table entries | CDM record (offset +0x08 normalized) |
|---|---:|---:|---|
| `live_kbuf0` | 0 | 0 | `A` |
| `live_kbuf1` | 1 | **0** | `A` |
| `live_kbuf2` | 2 | 2 | `A` |
| `live_kbuf4` | 4 | 4 | `A` |
| `live_kbuf8` | 8 | 8 | `A` |

(`A` = the single distinct normalized-record hex value; all five cases
produced byte-identical CDM records once the one known per-dispatch-
varying field, `+0x08..+0x0b`, is zeroed -- `schema.normalize_cdm_record`,
proven idempotent and scope-limited in `verify.py --selftest`.)

### Interpreted

- **H6 is SUPPORTED**: the live CDM launch record does not encode buffer
  count in any field this experiment could detect -- it is
  byte-identical across the full 0..8 sweep. Buffer count instead governs
  (a) the argument-buffer table's entry count (already an established
  live structure, EXP-0011) and (b) the compute-preamble BO's
  instruction-length growth (observed structurally: a repeating ~20-byte
  chunk per additional live buffer, consistent with EXP-0020's documented
  per-buffer `device_load`-into-uniform-register preamble pattern; not
  independently re-verified at instruction-semantic level here, per
  clean-room rule 5 -- length only).
- The **argument-table entry count tracks compiler-visible usage, not the
  raw API binding call**: `live_kbuf1` genuinely binds 1 real buffer via
  the public API, yet the table shows 0 entries -- directly matching the
  metadata survey's own field-1/field-3 absence for `kbuf1`. This is
  positive evidence that Metal builds the live resource table FROM the
  compiled shader's own declared/optimized usage (an archive/compile-time
  fact), not from the caller's binding call count, and is exactly the
  kind of fact the P0.7 row asks for: **the metadata's buffer-count-
  correlated fields (1, 3) are archive/compile-time bookkeeping that
  determines table construction; they are not literally copied into any
  live hardware-visible structure this experiment inspected.**
- Fields `0` (GPR), `9`/`14`/`31`/`32`/`41` (already established by prior
  experiments) remain the only fields with a DIRECT documented live-BO
  correlation (occupancy-tier bit, scratch/tgmem BO fields). The four
  newly-surveyed fields here (`1`, `3`, `38`, `42`) are `PARTIAL`: their
  correlation with resource counts is DATA-TRACE-VALIDATED (this
  experiment), but their firmware-vs-archive classification rests on a
  NEGATIVE result (absence from the one live structure checked, the CDM
  record) rather than a positive alternate-structure match; the argument
  table and preamble-length growth are the positive matches, but this
  experiment did not exhaustively rule out every other live BO.

## DECODED vs GENERATABLE, per structure

| structure | DECODED (this experiment + prior) | GENERATABLE (independently construct + hardware-execute, never captured) |
|---|---|---|
| CDM record (0x2c bytes, direct-dispatch shape) | Full field map for this authored shape (config word, code/uniform pointer, grid/tg, reserved words) | **Not attempted here.** Byte-level shape is known; no run in this experiment authored a raw CDM record and executed it without going through `dispatchThreads:` |
| CDM segment link (8 bytes) | Split-address transform validated against 4 distinct real targets (this experiment); tag byte `0x20` | **Not attempted.** No link was hand-constructed, spliced into a captured stream, and executed. This is the single highest-value follow-up named in `PRE_REGISTRATION.md`/EXP-0043's own note. |
| CDM segment capacity (732 records, first+continuation) | Confirmed uniform across position and relocation condition | N/A (a derived constant, not a constructible object) |
| VDM draw record + bind-pair template + FF-state pool | Full field map (this experiment, M4-confirmed byte-exact vs A18) | **Not attempted.** No pool bytes or bind-pair were hand-authored; all captured via the public `MTLRenderPipelineDescriptor`/`MTLDepthStencilState` API |
| VDM segment link (8 bytes) | Same transform, tag `0x80`, validated against 2 targets (1 new here) | Not attempted, same as CDM |
| `__GPU_METADATA` fields `1`/`3`/`38`/`42` | Newly surveyed, correlated with resource counts | N/A -- these are Metal-archive fields; this experiment's finding is that they do NOT need to be independently generated for a hardware-visible object (they inform table construction, which the argument-table mechanism, EXP-0011, already covers as a generatable structure via `setBuffer:offset:atIndex:`) |
| CDM launch-descriptor resource-count encoding | Confirmed ABSENT (no field tracks buffer count) | N/A -- this is a negative result: nothing to generate |

## What P0.5 still needs

- Independent construction + hardware execution of a CDM/VDM link record
  (the concrete next step, above) -- this is what would move the link
  encoding from `DATA-TRACE-VALIDATED` to `HW-VALIDATED`.
- General relocation for VDM/FF-state: this experiment only tested two
  perturbations (padding, prior queues) and got two negatives; it did NOT
  identify ANY perturbation that moves the VDM base, so "queue-context-
  fixed" remains a hypothesis, not a proven mechanism. A follow-up should
  try: many more simultaneous queues/contexts (dozens, to look for a
  capacity limit or an eventual shift), and explicit queue/context
  destruction-and-recreation cycles.
- The unresolved multi-registration-at-identical-VA observation (see
  §1) needs a dedicated, purpose-built probe (this experiment's harness
  was not designed to distinguish "same GPU VA, different queue context"
  from "same GPU VA, same context, reused").
- Full PPP/USC schema: this experiment closed the depth/stencil/blend/
  cull/bind-pair-template gap for M4 specifically; barriers, calls,
  indirect packets, and the remaining `0x58000` sub-blocks EXP-0019 left
  opaque (`+0x39` constant, full write-mask bit isolation, provoking-
  vertex, MRT) are untouched here.
- A18 Pro replication of every M4-only fact above (hands-off per
  `CLAUDE.md`; treated as `INFERRED` via the general A18=M4 byte-identity
  finding until directly run).

## What P0.7 still needs

- The row's "construction of sized code blocks and uniform-preamble
  containers" and "entry point and authoritative program extent" remain
  primarily EXP-0042's territory (code-window selector, FS selector
  formula); this experiment did not extend that, only the resource-count
  metadata fields and their firmware/archive split.
- Positive (not merely negative) identification of where, if anywhere,
  metadata fields `1`/`3`/`38`/`42` DO surface in a live structure besides
  the argument table's entry count and the preamble's length -- this
  experiment checked only the CDM record and a coarse preamble-length
  proxy; the USC BO (`0x10000130000` family) and its per-stage config
  words were not checked against these specific field values.
- Independent shader-record construction/launch "without an Apple-created
  archive" (the row's explicit validation bar): this experiment used
  `tools/shdump` (archive-based extraction) throughout; it did not attempt
  a from-scratch code-block + preamble construction bypassing the archive
  path.
- Texture/sampler resource-specifier fields beyond the coarse `38`/`42`
  presence flags: no field distinguishes 1 vs 2 vs 4 textures, or samplers
  from textures, in this survey.

## Clean-room attestation

```text
Clean-room provenance: HW-PROBE / DATA-TRACE / OWN-SHADER
Inputs inspected: harness/cmdprobe.m and harness/containerdispatch.m
  (authored ObjC/MSL, embedded/loaded source only); kernels/generated/*.metal
  (authored, generated by kernels/gen_container_kernels.py); IOKit boundary
  allocation metadata (filenames only, for unclassified BOs) and content
  (for BOs structurally matching our own authored CDM/VDM signature, chain-
  followed from a uniquely-identified head, or the FF-state pool located
  via that VDM BO's own bind-pair addresses); public command-buffer status/
  readback; our own compiled shader archives via tools/shdump + agxparse.py
  (unmodified, read-only).
Apple binary introspection: NONE.
Unclassified BO content: NEVER read (filename-metadata catalog only, see
  PRE_REGISTRATION.md "Confounders").
Reproduction: README.md's command block; verify.py --selftest/--seqtest are
  self-contained (synthetic fixtures, no device needed).
Evidence: raw/m4_20260827_run01/, raw/m4_20260827_run02/,
  analysis/cross_run_report.json, CAPTURE_CONTRACT.json (authored-file
  hashes), manifest.json.
```

Every shader dispatched or compiled was authored in this experiment's own
`harness/` or `kernels/gen_container_kernels.py`. `tools/iotrace/iotrace.c`
and `tools/shdump/{shdump.m,agxparse.py}` were used exactly as committed,
never edited (hashes recorded per-run in `00_inputs.json`). No Apple
binary, framework, kernel, firmware, or Apple-authored shader was
inspected, disassembled, decompiled, strings-scanned, debugged, or traced.
