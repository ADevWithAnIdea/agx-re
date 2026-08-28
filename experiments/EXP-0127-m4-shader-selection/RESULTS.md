# EXP-0127 results -- M4 shader selection: token rule, FS selector
# redirect/boundary, code-window relocation

## Verdict

**P0.2 remains OPEN**, but this experiment resolves the three questions it
was dispatched to answer, and one of the answers is a REFUTATION of the
working hypothesis EXP-0042 left open, not a confirmation:

1. **VS token rule: SOLVED.** `token(n) = 0x2c0 + 0x80*n` for the n-th
   pipeline-state object bound in a queue's lifetime (n >= 1, 0-indexed),
   independent of the underlying VS code's compiled size; the very first
   bind (n=0) is a distinguished non-formula case. The field is at least
   32 bits wide (observed values exceed 0xFF within 3 creations and reach
   `0xe40`+ well before any boundary), refuting the earlier "8-bit token"
   framing. At a reproducible, precise capacity boundary (the 507th bind,
   token `0xff40`, i.e. one step short of the small code container's own
   `0x10000`-byte size) the *addressing base itself* discontinuously
   changes: a brand-new, separately GPU-registered 0x40000-byte BO appears
   at a completely different, non-4GiB-aligned VA, and the SAME `+0x80`
   linear rule continues relative to the NEW base. **HW-VALIDATED**
   (reproduced byte-identical across two independently gated official
   runs, and materially corroborated by a third partial run and multiple
   pre-registration pilots).
2. **FS selector `0x58000+0x08`: NOT the code selector.** Independently
   constructing and splicing a real, freshly-discovered alternate FS
   pipeline's own natural selector value into a bound pipeline's live pool
   record, strictly pre-commit, completes without a fault and renders AS
   THE ORIGINALLY BOUND FS in all four tested directions (red<->green,
   red<->blue) -- the redirect **never** worked. This directly refutes
   EXP-0042's implicit "this field selects which FS executes" reading.
   The field is not inert bookkeeping either: driving it with genuinely
   out-of-range values (`+0x2000000`, the top bit set, the field's own
   `0xffffffff` ceiling) reliably FAULTS (`PageFault`), proving hardware or
   firmware does dereference it for *something*. The most defensible
   reading, given the redirect negative plus the fault positive plus
   EXP-0042's own structural finding that the value points at the payload
   of an auxiliary 0x80-byte record following the FS code: this field
   feeds a RESOURCE/METADATA fetch associated with the currently selected
   FS, not the code-selection decision itself. **HW-VALIDATED negative**
   for redirect; **HW-VALIDATED positive** for the fault boundary; the true
   consumer/purpose of the field is **UNKNOWN**, narrowed from "probably
   the FS code pointer" to "probably not."
3. **Code-window relocation category: INVARIANT, like VDM/FF-state, not
   like CDM.** The code BO's registered GPU VA (`0x10000000000`), and the
   VDM/FF-state-pool family (`0x18000`/`0x58000`), are all UNCHANGED under
   64 MiB of ordinary client buffer padding and under four additional
   command queues created before any pipeline work -- the same
   perturbations EXP-0110 used to show the CDM command-segment chain DOES
   move. **DATA-TRACE-VALIDATED**, reproduced across two gated official
   runs plus prior pilots. Separately (finding 1 above) the code window's
   own CAPACITY is finite and, once exhausted, relocates a *growth region*
   to an entirely different, non-4GiB-aligned base -- a different kind of
   relocation than EXP-0110's heap-pressure-driven one, triggered by
   demand, not by client allocator load.
4. **`usc_exec_base` mapping: STILL NOT DEMONSTRATED, and now positively
   COMPLICATED.** The first ~505 VS binds are consistent with a single,
   stable, 4 GiB-aligned base (`0x10000000000`) exactly matching the shape
   Mesa's own `agx_usc_addr()`/`shader_base` reference implementation uses
   (PUBLIC source, informs hypothesis only). But the capacity-boundary
   growth region sits at raw VA `0x2b0000` -- far BELOW `0x10000000000`,
   not reachable by an unsigned `addr - shader_base` subtraction the way
   Mesa's own helper computes it. No Linux submission was made; this
   remains **INFERRED, not demonstrated**, and the new observation is a
   reason for caution, not confidence, about a single-window model.

All results are M4/G16G only; A18 Pro not run (hands-off per `CLAUDE.md`).

## 1. VS token derivation rule (task 1)

### Observed

`vstoken --mode varied` (8 vertex functions of sizes `[0, 48, 4, 40, 12,
32, 20, 24]` unrolled FMA ops, created/drawn in that fixed interleaved
order), gated, byte-identical `m4_20260828_run04`/`run05`:

| n | ops (size) | token | delta from previous |
|---:|---:|---:|---:|
| 0 | 0 | `0x1c0` | -- |
| 1 | 48 | `0x340` | `0x180` |
| 2 | 4 | `0x3c0` | `0x80` |
| 3 | 40 | `0x440` | `0x80` |
| 4 | 12 | `0x4c0` | `0x80` |
| 5 | 32 | `0x540` | `0x80` |
| 6 | 20 | `0x5c0` | `0x80` |
| 7 | 24 | `0x640` | `0x80` |

Every step after the first is exactly `0x80`, REGARDLESS of whether the
*preceding* function was the smallest (0 ops) or the largest (48 ops) in
the set -- the step from n=1 (48 ops) to n=2 (4 ops) is `0x80`, identical
to the step from n=4 (12 ops) to n=5 (32 ops). This directly falsifies H1's
"code-offset, proportional-to-size" alternative and supports the pure
fixed-stride hypothesis.

`vstoken --mode uniform --count 650` (near-identical vertex functions,
differing only by a per-function integer literal so each compiles to a
genuinely distinct entry at essentially equal size), gated, byte-identical
`run04`/`run05`:

- `linear_base = 0x2c0` (704), `linear_step = 0x80` (128), fit from n=1
  and the next dumped checkpoint, then verified against every other
  dumped checkpoint up to n=505: `token(n) = 0x2c0 + 0x80*n` holds exactly
  for every one of the ~35 checkpoints in that range (n=1..505).
- `first_step_anomaly_token = 0x1c0` (n=0): `0x2c0 + 0x80*0` would predict
  `0x2c0`, not `0x1c0` -- a `0x100`-short anomaly, reproduced identically
  in both the varied and uniform sweeps and in every pre-registration
  pilot. The delta from n=0 to n=1 is always exactly DOUBLE the steady
  step (`0x180` vs `0x80`).
- `boundary_index = 506`: at exactly the 507th bind (0-indexed n=506),
  `token` jumps from the predicted `0xffc0` to `0x2b0040` -- `boundary_delta
  = 0x2a0100`, far too large to be an ordinary off-by-a-few-records
  discontinuity. `new_region_appeared = true`: a BRAND NEW GPU buffer
  object, never seen at any earlier checkpoint, is registered at raw VA
  `0x2b0000`, size `0x40000` (262144 bytes) -- and `token(506) - 0x2b0000
  = 0x40`, i.e. the token now points `0x40` bytes into this NEW region,
  the exact same "record header + 0x40" pattern EXP-0042 established for
  the FS selector (content check, pre-registration pilot: byte `0x2b0000`
  reads literal `0x80` as a little-endian u32, matching the "record size =
  0x80" signature). `post_boundary_step_ok = true`: every checkpoint from
  n=507 through n=649 continues the identical `+0x80` linear rule relative
  to the NEW base (`token(n) = token(506) + 0x80*(n-506)`), with zero
  deviation.
- `readback_status_all_completed = true` for all 650 draws in both official
  runs: no creation failure, no fault, no hang across the full sweep. The
  ordinary Metal pipeline-object resource ceiling (if any) was not reached
  within this tested range; the capacity boundary found here is a code-
  container-capacity event, not a pipeline-count exhaustion event.

### Interpreted

- **H1 (ordinal, not code-offset) is SUPPORTED.** The token is a per-
  pipeline-state creation-ORDINAL counter with a fixed `0x80`-byte stride,
  not a value that tracks the actual compiled code size of the VS it
  names. The `0x80` stride matches the size of the auxiliary record the FS
  selector also points into (EXP-0042), suggesting a shared underlying
  convention (a fixed-size per-pipeline-state metadata slot), not that VS
  and FS use the identical mechanism.
- **H2 (bounded, not free-running) is SUPPORTED**, and more precisely than
  pre-registration's three predicted shapes: neither (a) unbounded linear
  growth, nor (b) a clean pipeline-creation failure, but (c) a capacity-
  triggered RELOCATION of the addressing base to a newly-allocated,
  differently-based growth region, after which the same linear counting
  resumes. This is the "finite-resource mandate" answer the dispatch asked
  for: a driver emitting many distinct VS objects on one queue MUST be
  prepared for the token's own addressing base to change partway through a
  session, at a boundary this experiment pins to exactly 506 same-size
  creations for the tested shader shape (not claimed as a universal
  constant independent of shader size/complexity -- see "what P0.2 still
  needs").
- The n=0 anomaly (a `0x100`-short first step) is reported as an observed,
  reproducible fact; its cause (a queue-lifetime initialization cost
  consuming an unobserved earlier slot, or a distinct first-bind code path)
  is **INFERRED**, not established further here.

## 2. FS selector meaning and redirect (task 2)

### Observed -- baseline and redirect (decisive test)

`fsredirect` independently discovers each run's own natural selector for
three genuinely different-sized fragment functions (`fs_red`: no loop,
`fs_green`: 9-iteration FMA loop, `fs_blue`: 21-iteration FMA loop; all
sharing one vertex function that produces a genuinely-live, non-foldable
varying -- see "Confounder discovered" below) via solo draws, fresh every
run, never hand-copied. Gated, byte-identical `run04`/`run05`:

| discovered | value |
|---|---:|
| `S_RED` | `0x4c0` (1216) |
| `S_GREEN` | `0x880` (2176) |
| `S_BLUE` | `0xcc0` (3264) |

Baseline solo draws (no splice) render correctly (`red`/`green`/`blue`),
`final_status=4` (Completed) in all cases -- confirming the harness and
the three pipelines behave exactly as EXP-0042's own stage-matrix formula
predicts (values consistent with `header + size + 0x40`, increasing with
each function's larger compiled size).

**Redirect (the decisive test):** for each of the four directions below,
the bound pipeline's live pool record is spliced, strictly pre-commit,
with the OTHER pipeline's own freshly-discovered natural selector value,
then committed and read back:

| case | bound | spliced to | rendered | fault? |
|---|---|---:|---|---|
| `redirect_red_to_green` | red | `S_GREEN` (0x880) | **red** | no |
| `redirect_red_to_blue` | red | `S_BLUE` (0xcc0) | **red** | no |
| `redirect_green_to_red` | green | `S_RED` (0x4c0) | **green** | no |
| `redirect_blue_to_red` | blue | `S_RED` (0x4c0) | **blue** | no |

All four: `final_status=4`, `wrote=true` (confirmed by re-reading the same
CPU-mapped field, both PRE-commit -- the harness verifies the write stuck
before committing -- and POST-commit in pre-registration calibration,
which additionally scanned every other captured BO for a stray copy of the
spliced value and found none). The command buffer never faults and always
renders as the ORIGINALLY bound pipeline, never the redirected-to one, in
all four tested directions, gated byte-identical across `run04`/`run05`.

### Observed -- boundary and misalignment sweep

| case | spliced value | fault? | rendered (gate-safe cases only) |
|---|---:|---|---|
| `boundary_zero` | `0` | no (`final_status=4`) | red (stable 4/4 across all four captured runs) |
| `boundary_far_oor` | `S_GREEN+0x2000000` | **YES** (`PageFault`) | -- |
| `boundary_top_bit` | `S_GREEN\|0x80000000` | **YES** (`PageFault`) | -- |
| `boundary_max` | `0xffffffff` | **YES** (`PageFault`) | -- |
| `boundary_near_but_invalid` | `S_RED-0x40` (RED's own record header) | no | black (stable 4/4) |

No case in this experiment produced a HANG or a silent alias (the field is
only 32 bits wide with no unused high-order headroom the way the CDM/VDM
56-bit link target had, so a EXP-0116-style "wraps back to a valid target"
alias was not structurally possible to construct here; the closest analog
-- `boundary_top_bit`, setting the field's own sign/high bit -- faulted
cleanly rather than aliasing).

Misalignment sweep (`S_GREEN` +/- 1/2/4/8 bytes), never faults
(`final_status=4` in every one of 8 cases x 4 runs = 32 observations), but
`result_colour` is **NOT gate-stable** for most offsets -- see next
section.

### A hardware nondeterminism discovered by the cross-run gate itself (a
### first-class result, not a bug hidden)

The first official pair (`m4_20260828_run02`/`run03`, both fully valid,
retained) showed `result_colour` genuinely DIFFER between the two runs for
`misalign_plus4` (black vs red) and `misalign_minus1` (black vs red)
despite BOTH runs reporting a clean `final_status=4` -- i.e. racy even
without a fault, which is a stronger and more surprising claim than
EXP-0116's own fault-time-visibility race. A second pair
(`m4_20260828_run04`/`run05`, the official pair) showed `misalign_minus2`
ALSO flip (red vs black), while `misalign_plus4`/`misalign_minus1` were
STABLE (both black) in that pair. Combining all four captured runs:

| offset from `S_GREEN` | run02 | run03 | run04 | run05 | verdict |
|---:|---|---|---|---|---|
| `+1` | red | red | red | red | **stable red** |
| `+2` | red | red | red | red | **stable red** |
| `+4` | black | red | black | black | **UNSTABLE** |
| `+8` | red | red | red | red | **stable red** |
| `-1` | black | red | black | black | **UNSTABLE** |
| `-2` | black | black | red | black | **UNSTABLE** |
| `-4` | black | black | black | black | **stable black** |
| `-8` | black | black | black | black | **stable black** |
| `0` (`boundary_zero`) | red | red | red | red | **stable red** |
| `S_RED-0x40` | black | black | black | black | **stable black** |

No single offset is reliably the "flip point" across different capture
pairs -- three DIFFERENT offsets (`+4`, `-1`, `-2`) were each seen to flip
in at least one of the two pairs, while none of them flipped in every
pair. **Interpretation:** a value that lands close to, but not exactly on,
a valid selector produces execution behavior that is not deterministic
run-to-run even though the command buffer reports clean completion every
time -- a genuine hardware/timing race, not a capture artifact (the
harness's own `case_valid_setup`/`post_selector` fields, which ARE fully
deterministic, confirm the SAME value was written and read back identically
in every one of these cases; only the rendered pixel varies). This is
recorded honestly as `UNKNOWN` root cause and handled by excluding
`result_colour` from the cross-run gate for any case whose spliced value is
not exactly one of the three discovered natural selectors (`schema.py`'s
`_result_colour_is_racy`; disclosed in `CAPTURE_CONTRACT.json`'s
`post_capture_corrections`). Small positive misalignments (`+1`, `+2`,
`+8`) and the null selector (`0`) were, empirically, always stable across
all four runs captured here (rendering as if unchanged/no-op), while
negative misalignments trend toward corrupting output (black) more often
than positive ones -- an asymmetry recorded as observed, not fully
explained.

### Confounder discovered and fixed during calibration

An early draft of `kernels/fsredirect.metal` scaled the vertex-stage `uv`
varying by a compile-time literal `0.0f`. The Metal compiler constant-folds
`x * 0.0f` to a literal zero regardless of `x`'s runtime value, which
eliminates the actual `[[stage_in]]` data dependency; a fragment function
built this way never populates `0x58000+0x08` at all (`sel8` read back as
`0` for every pipeline, structurally distinguishable from every other
field in the record). The committed kernel instead scales by a RUNTIME
buffer value (`params[0].z`, set to `0.0` at the API level so the visual
output is unaffected), which cannot be constant-folded and reliably
populates the field. This is disclosed as a genuine method pitfall, not
silently corrected away.

### Interpreted

- **H3 (redirect succeeds) is REFUTED** in every one of 4 tested
  directions, HW-VALIDATED (gated, cross-run-identical). Writing a real,
  valid alternate FS's own natural selector into the live field does not
  change which shader executes.
- **H4 (boundary/alias behaves non-uniformly) is SUPPORTED**: moderate
  out-of-range and misaligned values are silently tolerated (no fault,
  though possibly racy output) while sufficiently-far/high-magnitude values
  reliably fault; the field's own bit-width ceiling (`0xffffffff`) faults
  cleanly rather than hanging (unlike EXP-0116's CDM `encoding_max` case,
  which hung) -- a DIFFERENT boundary-failure profile for this field,
  reported as observed rather than assumed to generalize from the CDM
  case.
- Combined with the fault-on-out-of-range positive result, the field is
  real, HW/FW-consumed state (per CLAUDE.md's HW-PROBE method: writing a
  known pattern and observing a consequence), but its content does not
  determine WHICH shader's machine code executes. The most defensible
  standing hypothesis is that it addresses a RESOURCE/metadata structure
  the currently-selected FS reads (consistent with EXP-0042's own
  structural finding that the value points into the payload of the 0x80-
  byte record immediately following the selected FS's code, which was
  never established as consumed-for-selection, only as consumed-for-
  SOMETHING). Confirming or refuting that specific reading is the
  concrete next step (see below), not established here.

## 3. Code-window relocation category (task 3)

### Observed

`vstoken --mode uniform --count 3` under three conditions in the same
official run (baseline `pad0`, `pad64` = 64 MiB of ordinary client padding
allocated before any pipeline work, `extraq` = 4 additional command queues
created before any pipeline work), gated, byte-identical `run04`/`run05`:

| condition | code BO base unchanged? | pool base unchanged? | VDM base unchanged? |
|---|---|---|---|
| `pad64` vs `pad0` | **true** | **true** | **true** |
| `extraq` vs `pad0` | **true** | **true** | **true** |

(Raw, non-gated values, identical across both conditions and both runs:
code BO `0x10000000000`, pool `0x58000`, VDM `0x18000` -- confirming the
"unchanged" booleans are not vacuously true against a moved-together
baseline.) For comparison, EXP-0110's own `vertices`-class ordinary client
resource moved by the FULL padding amount under the same 64 MiB
perturbation in this experiment's own pilot capture (`+0x4080000`,
matching EXP-0110's CDM-chain delta), confirming the padding was genuinely
applied and large enough to move client-heap-relative structures.

### Interpreted

- **H5 is SUPPORTED, DATA-TRACE-VALIDATED.** The code window belongs to
  EXP-0110's INVARIANT category (VDM/FF-state), not its heap-relative
  category (CDM). A driver can treat the code window's base as a stable,
  queue-lifetime constant with respect to ordinary client buffer
  allocation pressure and additional command queues, for the tested
  perturbation range (up to 64 MiB / 4 extra queues).
- This is a DIFFERENT axis from the capacity-triggered relocation task 1
  found: that relocation is driven by DEMAND (creating enough distinct
  code objects to exhaust ~`0x10000` bytes of container capacity), not by
  ordinary allocator pressure from UNRELATED client buffers. Both facts
  must be documented together: the code window's base is stable under
  memory pressure, but not eternally fixed once enough code accumulates.

## GENERATED vs COPIED / OBSERVED vs INTERPRETED (closure-relevant)

| item | status | evidence |
|---|---|---|
| VS token linear formula (`base`, `step`) | **GENERATED + TESTED**: computed fresh each run from that run's own dumped checkpoints, verified against every checkpoint in range, never hand-copied | `raw/m4_20260828_run04,run05/gated.jsonl` |
| Capacity-boundary index and new-region size | **OBSERVED, reproduced across 2 gated runs + 1 partial run + prior pilots** | same |
| FS redirect (4 directions) | **GENERATED + TESTED, HW-VALIDATED negative**: selector values computed fresh from this run's own discovery draws, spliced, executed, read back | same |
| FS boundary/fault map | **GENERATED + TESTED**: every boundary value computed from protocol constants (`0`, `0xffffffff`, `\|0x80000000`, `+0x2000000`) plus this run's own discovered naturals, never a captured Apple value | same |
| Code-window invariance under padding/extra queues | **GENERATED + TESTED**: padding/queue counts are authored parameters; comparison is against this SAME run's own pad0 baseline | same |
| The `0x80`-record's TRUE resource-specification content (what it actually feeds) | **NOT ACHIEVED** -- this experiment shows it is dereferenced (fault positive) and shows it does NOT gate code selection (redirect negative), but does not determine what it DOES do | -- |
| A from-scratch, non-Metal-encoded code container placed and executed via this mechanism | **NOT ACHIEVED** | -- |

## What P0.2 still needs

- **The TRUE FS code-selection mechanism.** This experiment's central,
  load-bearing finding is that `0x58000+0x08` is NOT it. The next
  concrete step is a redirect test structured like this one but targeting
  candidate fields inside the VDM draw record itself (by analogy with the
  VS `+0x1c/+0x20` bind pair, which this experiment did NOT attempt to
  redirect -- see below), or inside the 0x80-byte auxiliary record's OTHER
  bytes (only the record's existence and the `+0x40` payload address were
  probed here; its remaining ~0x70 bytes were never written to).
- **A VS-side redirect test.** This experiment fully characterized the VS
  token's DERIVATION rule but never attempted to SPLICE it (bind pipeline
  A, overwrite its VDM `+0x20` field with pipeline B's own token, and
  check which VS executes) -- the direct VS analogue of this experiment's
  FS redirect, and the natural next falsification target given the FS
  redirect's negative result.
- **Whether the capacity boundary (506 same-size creations) generalizes**
  to different VS code sizes, to FS-side capacity (never pushed to its own
  boundary here -- only 3 FS objects were ever live at once), or to mixed
  VS+FS accumulation in one queue.
- **The racy misalignment outcomes' root cause** (hardware race vs.
  scheduler/timing artifact vs. uninitialized-state read) is UNKNOWN;
  narrowing it further needs many-repetition statistics per offset (this
  experiment ran each case exactly once per official run, four data points
  per offset in total) or a dedicated timing-controlled follow-up.
- **The `usc_exec_base` mapping** is still not demonstrated end-to-end
  (no Linux submission), and the capacity-boundary growth region's raw,
  non-4GiB-aligned VA (`0x2b0000`) is a positive reason to treat a naive
  single-window `addr - shader_base` model with caution rather than
  assume it, pending a controlled test of whether that specific region
  is reachable via the SAME base register as the main code window at all
  (e.g. by probing whether firmware treats it via a per-stage
  `USC_EXEC_BASE_TA`-style register distinct from the fragment path's own
  base, as the pinned Linux UAPI's three independent-but-usually-tied
  registers structurally allow -- PUBLIC source, `mesa/include/drm-uapi/
  asahi_drm.h`, informs this as a hypothesis only, not evidence).
- Direct A18 Pro/G17P replication (hands-off; this M4 result is the
  operational Apple9 evidence per `CLAUDE.md`).

## Gate results

- `verify.py --selftest`: **16/16 PASS** (address-invariant gating for
  both vstoken and fsredirect record shapes; two literal reproductions of
  the discovered racy-result_colour-on-clean-completion shape --
  `misalign_plus4`/`misalign_minus1` -- correctly excluded from the gate;
  a genuine content mismatch, and a genuine result_colour difference for
  an exact-natural case, are NOT masked; no address-shaped key/value in
  any gated fixture).
- `verify.py --seqtest`: **5/5 PASS** (PRE_GPU/RUN01_PRESENT/RUN02_PRESENT
  gate applicability).
- Smoke gate: **PASSED** (`run.py --smoke`) before any `raw/` directory
  existed.
- `verify.py --captured m4_20260828_run04 m4_20260828_run05`: **PASS** --
  25/25 gated records byte-identical, zero mismatches, zero address-shaped
  leaks (`schema.assert_no_address_leak` applied to every record).
- Disclosed process history: `m4_20260828_run01` (partial, a schema
  false-positive crashed it before any perturb/fsredirect record existed)
  and `m4_20260828_run02`/`run03` (both complete and valid, superseded for
  the gate role after the racy-result_colour discovery corrected the
  schema) are retained, not deleted or repaired, per `CAPTURE_CONTRACT.json`
  `post_capture_corrections`.

## Clean-room attestation

Clean-room provenance: HW-PROBE / DATA-TRACE / OWN-SHADER

Inputs inspected: the MSL and Objective-C/Python source in this directory
(all authored here for this experiment); IOKit boundary data and BO
contents captured by the repository's unmodified, read-only
`tools/iotrace/iotrace.c` from this process's own registered GPU buffer
objects; direct CPU writes into this process's own live command-stream
memory (the same class of technique EXP-0116 already validated for the
CDM segment link). No Apple binary was disassembled, decompiled, or
otherwise introspected.

Apple binary introspection: NONE

Reproduction: `README.md` commands, all with hard timeouts (per-commit
watchdogs inside every harness, process-level timeouts in `run.py`,
`alarm()` as an innermost backstop).

Evidence: `raw/`, `raw_manifest.sha256`, `manifest.json`,
`PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json`, `PROGRESS.md`. P0.2 remains
open: this experiment materially narrows and partly REVERSES a prior
working hypothesis but does not provide the true FS code-selection
mechanism, a VS-side redirect, or a Linux `usc_exec_base` end-to-end test.
