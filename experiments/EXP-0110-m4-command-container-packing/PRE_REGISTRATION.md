# EXP-0110 pre-registration: M4 command/container relocation, link grammar,
# state-packet fields, and shader-container/metadata split

Date: 2026-08-27. Target: local Apple M4 / G16G only (macOS 26.6.2, Metal 4).
No result from this experiment is an Apple A18 Pro / G17P fact.

This file is frozen before the first GATED capture (`raw/`). Development of
the harness, scanner, and case matrix was calibrated against **throwaway,
non-evidentiary** dry runs (kept only under `work/`, never committed to
`raw/`) exactly as `CODEX.md` §3 anticipates ("capture the baseline before
mutation" presupposes a working probe) -- this is standard pre-registration
practice, not a violation of "pre-register before building": no fact in
`RESULTS.md` is sourced from those dry runs; every claim is re-derived from
the two frozen `raw/` captures below.

## Question and bounded purpose

`docs/P0-P1-CLOSURE.md` rows P0.5 (`DRV-CMD-01`) and P0.7 (`DRV-SHADER-01`)
are both stuck at "STRUCTURAL, single observed pair, no relocation proof"
(EXP-0043/EXP-0049) and "record framing located, resource-spec/firmware
split undetermined" (EXP-0042) respectively. This experiment asks four
narrower, falsifiable questions within that scope:

1. **Relocation.** For the CDM (compute) and VDM (draw) command-segment
   chains EXP-0043/EXP-0049 already located, which of {absolute address,
   client-heap-relative, queue-relative, fixed-per-process} does each
   segment's base address behave like, under (a) additional command queues
   created and used before the probe queue, and (b) large authored client
   allocations made before the probe's own resources?
2. **Link/chain grammar.** Does the single observed CDM link pair
   (`0x20000100 0x00158000` -> `0x10000158000`) and VDM link pair
   (`0x80000000 0x00088000` -> `0x88000`) generalize to a formula that
   correctly predicts DIFFERENT target addresses obtained under different
   allocation conditions, and what is the exact per-segment record capacity?
3. **State-packet fields.** For the VDM bind-pair template and `0x58000`-
   equivalent FF-state pool EXP-0019/EXP-0024 documented **only on A18
   Pro**, does the same template and field layout reproduce on M4, and can
   the VDM control-word "nibble" (`0x0200/0x0300/0x0500/0x0700/0x0a00`)
   be tied to which FF-state sub-block/role it targets by toggling one
   Metal draw-state parameter (depth test, stencil test, blend, cull) at a
   time?
4. **Container/metadata (P0.7).** Do specific `__GPU_METADATA` FlatBuffer
   field values (buffer/texture/sampler-count-correlated fields newly
   surveyed here) reappear verbatim in the live CDM launch record when the
   corresponding shader is actually dispatched, or are they consumed only
   by Metal's own archive/argument-table construction?

## Hypotheses and falsifiers

**H1 (CDM base is client-heap-relative, not queue-relative).**
Support: creating and using 4 additional command queues before the probe
queue leaves the probe's own CDM segment addresses unchanged (delta 0
against a same-run zero-padding baseline); a large (64 MiB) authored client
allocation made before the probe's resources shifts every segment in the
chain by a single uniform delta.
Falsifier: prior-queue creation changes the CDM base by a queue-indexed
step: OR the 64 MiB padding leaves the CDM base unchanged; OR the shift is
non-uniform across segments (would indicate the chain is not built inside
one contiguously-relocated region).

**H2 (VDM/FF-state base is NOT client-heap-relative).**
Support: the same 64 MiB padding that shifts CDM leaves the VDM chain's
segment addresses at delta 0 against the same run's zero-padding baseline.
Falsifier: VDM addresses shift under padding (would refute the asymmetry
between the two structures and require re-examining EXP-0043/EXP-0049's
"padding does not move the link targets" result as coincidental rather
than structural).

**H3 (the split-address link transform generalizes).**
Support: `decode_link(tail_hi, tail_lo) = ((tail_hi & 0x00ffffff) << 32) |
tail_lo, tag = tail_hi >> 24` predicts the ACTUAL next segment's address
(not merely one previously-known pair) for at least three distinct target
addresses obtained under different case conditions (unpadded baseline
segment 2, unpadded segment 3, and the 64 MiB-shifted segment 2/3), for
both the CDM tag and the VDM tag.
Falsifier: the formula fails to predict the actual next segment address in
any tested case; or the tag byte is not constant within a structure kind
across cases.

**H4 (fixed per-segment record capacity).**
Support: every CDM segment in a multi-segment chain (first and any
continuation) holds exactly the same authored-record count before rolling
over, for the fixed authored record shape used here (0x2c-byte compute
records, grid 64x1x1 / tg 32x1x1).
Falsifier: segment capacity differs between the first segment and a
continuation segment.

**H5 (VDM bind-pair template reproduces on M4).**
Support: the M4 VDM header region (`VDM_HEADER_START` through the first
draw record) contains the same `(control, address)` pair sequence EXP-0019
documented on A18 (specifically: pairs with addresses `+0x00, +0x1c, +0x30,
+0x4c` relative to a pool base, plus a viewport pair and a context pair),
and the pool-region field decode (depth/stencil/blend/cull bit layout)
matches EXP-0019's documented bit positions exactly when the same Metal
state is set.
Falsifier: any pair or pool field value contradicts the documented A18
layout under matched Metal state.

**H6 (container metadata fields are archive-only for resource counts).**
Support: dispatching kernels with 0/1/2/4/8 real bound buffers produces a
BYTE-IDENTICAL CDM launch record (after normalizing the one known
per-dispatch-varying field) regardless of buffer count, while the
argument-buffer table's entry count DOES track the real bound-buffer count.
Falsifier: the CDM record changes with buffer count in a field-attributable
way (would mean the hardware-visible descriptor itself encodes resource
count, contradicting the "archive/table-only" classification).

## Independent / controlled variables

Per case group, exactly one variable changes vs that group's baseline
(`casematrix.py` is the single frozen source of the matrix):
- CDM: dispatch count, prior-queue count, padding count/size.
- VDM: draw count, prior-queue count (with/without those queues issuing a
  draw of their own), padding count/size.
- State: one of {depth test, stencil test, blend, cull mode} at a time vs
  an all-off baseline, plus one "all four together" adversarial case.
- Container: buffer count (0/1/2/4/8), texture/sampler count
  (0/0..4/0..2), and a GPR-pressure ladder (4/32/96) reproduced as an
  in-experiment sanity cross-check of the already-established field-0/
  field-32/field-41 semantics (EXP-0020/EXP-0041/EXP-M4-09) -- not a new
  claim on its own.
- Container-live: buffer count (0/1/2/4/8), each actually dispatched.

Controlled: authored MSL source and grid/threadgroup dims (fixed at
64x1x1/32x1x1 for CDM; a fixed 3/6-vertex-alternating triangle draw for
VDM), M4 target, macOS build, tool revisions, one fresh process per case.

## Confounders considered

- **Allocator nondeterminism across processes.** Absolute addresses are
  expected to vary run-to-run even for an identical case (ASLR-like
  per-process placement); this is exactly why raw addresses are kept OUT
  of the gated cross-run-compared payload (`schema.py`) and only
  *deltas relative to that same run's own zero-padding baseline case* are
  gated -- the delta is the quantity the hypotheses above actually predict
  to be invariant.
- **Dead-code elimination.** A single trivially-round-tripped buffer
  (`kbuf1`: `b0[i]=b0[i]`) may be eliminated by the compiler; observed
  identically to the zero-buffer case in both the metadata survey and the
  live argument-table entry count. Reported as a bound, not resolved
  further (would need `-O0`-equivalent control, unavailable via the public
  runtime compile API).
- **Multi-registration aliasing.** An early informal (pre-freeze) probe
  observed TWO distinct sel-9 registrations reporting the identical GPU VA
  `0x18000` with different CPU-side mappings and different content, for a
  `--prior-queues --prior-draws` case; a later run of the nominally
  identical case surfaced only one such registration. This is recorded as
  an unresolved, non-reproduced observation (see RESULTS.md), not promoted
  to a claim.
- **iotrace dumps every registered BO.** Per EXP-0043/EXP-0049 precedent,
  analysis is restricted to (a) BOs whose content structurally matches our
  own authored CDM/VDM signature, chain-followed from a uniquely
  identified head, and (b) the FF-state pool located via bind-pair cluster
  detection from within an already-classified VDM BO. No other BO's
  content is read by `run.py`/`analysis/scan.py`; unclassified BOs
  contribute only their filename-encoded metadata (VA/size/handle) to the
  non-gated catalog.

## Capture / gating discipline (see `CAPTURE_CONTRACT.json`)

- `verify.py --selftest`: synthetic fixtures only (two fake "runs" of a
  known 3-segment CDM chain at different absolute addresses, plus
  deliberately corrupted records); proves the scanner/decoder/schema
  round-trip and the address-non-leak property. Runnable in every tree
  state.
- `verify.py --seqtest`: walks PRE_GPU / RUN01_PRESENT / RUN02_PRESENT
  synthetic states and proves each gate `run.py`'s caller invokes is
  runnable and satisfiable in the state it is invoked from.
- `verify.py --preflight --run-id <run01>`: PRE_GPU gate before run01.
- `verify.py --between-runs --run01-id <run01> --run02-id <run02>`:
  RUN01_PRESENT gate before run02.
- `verify.py --captured --run01-id <run01> --run02-id <run02>`:
  RUN02_PRESENT gate; requires the GATED `02_results.jsonl` to be
  byte-identical, case for case, between the two runs (raw addresses are
  never in that file; see `schema.py`).
- `run.py`'s NON-RECORDED smoke case (`cdm`, count=2) executes into
  `work/`, not `raw/`, before `raw/<run-id>/` is created; a smoke failure
  is a pre-capture STOP.
- Every case is its own process, with a hard per-kind timeout
  (`run.py:TIMEOUTS`); every JSONL record is appended and `fsync`'d as it
  completes; a faulted/timed-out case is recorded with a `status`, never
  silently dropped or retried in place.
- Repository revision is pinned at pre-registration time: `0f1af7fa1d3e21a9996c3b49d7d91f6377427225`.
  Later runs are compared against this recorded value, not against
  whatever `HEAD` is when `run02` starts (sibling-experiment commits
  moving `HEAD` are not contamination; only a change to THIS experiment's
  own authored file hashes, recorded per-run in `00_inputs.json`, would
  be).
- Run ids: `m4_20260827_run01`, `m4_20260827_run02`. Never reused.

## Clean-room boundary for this experiment

Allowed inputs: public Metal API; MSL authored in `harness/cmdprobe.m`
(embedded), `harness/containerdispatch.m` (loads a file path), and
`kernels/gen_container_kernels.py`-generated sources; the read-only,
unmodified `tools/iotrace/iotrace.c` interposer and `tools/shdump/
shdump.m` + `tools/shdump/agxparse.py` container parser (invoked, source
hashes recorded, never edited); public command-buffer status/readback.

The interposer's SIGUSR1 dump snapshots every BO it has registered
(capture-layer capability, not a per-experiment choice -- same tool used
unmodified by EXP-0009/0011/0019/0024/0043/0049). Analysis is restricted
per the confounders section above: content is read only for (a) BOs whose
bytes structurally match our own authored dispatch/draw signature and are
reached by chain-following from a uniquely-identified head, and (b) the
FF-state pool located via that same VDM BO's own bind-pair addresses.
Every other registered BO contributes only its filename metadata (VA,
size, handle) to a catalog; its content is never opened by any script in
this experiment. No Apple binary, framework, kernel, firmware, or
Apple-authored shader is inspected, disassembled, or introspected.

## Minimum experiment record checklist (CODEX.md)

Addressed in `README.md` (question/method/commands/clean-room category),
this file (hypothesis/falsifier/variables), `manifest.json` (target/tool
revisions), `raw/` (complete captures including the addresses sibling
file), and `RESULTS.md` (observed vs interpreted, tested range, target,
independent validation, remaining unknowns).
