# EXP-0107 pre-registration — M4 scratch/helper ABI boundary at high pressure

Date frozen: 2026-08-27. Target: local Apple M4 / G16G only (`CLAUDE.md` target
discipline; A18 Pro is hands-off, never touched). Frozen git revision:
`0f1af7fa1d3e21a9996c3b49d7d91f6377427225` (informational provenance only —
see `CAPTURE_CONTRACT.json` — never a live gate).

## Predecessors and why this is a fresh registration

- **`EXP-0041-scratch-helper-abi`** is valid, non-quarantined P0.1 evidence:
  authored M4 CS/VS/FS programs with 208–576 B of compiler-declared per-thread
  scratch executed correctly, while a narrowly allowlisted boundary trace (four
  pre-established command/state BOs) exposed no separately observable
  helper/scratch record, launch-descriptor change, or allocation change. This
  is the last valid state of P0.1 (`docs/P0-P1-CLOSURE.md` row P0.1).
- **`EXP-0057-m4-scratch-pressure-envelope` is QUARANTINED / NON-EVIDENCE**
  (`experiments/EXP-0057-.../QUARANTINE.md`, 2026-08-20): its metadata
  collector exceeded its own frozen metadata-only boundary (generic
  archive/Mach-O enumeration where its registration promised a narrower
  extraction), and its raw records lacked full readback/guard data and a
  complete environment/revision record. **Nothing from EXP-0057 — no file, no
  number, no kernel design — is read, reused, or cited as evidence by this
  experiment.** Its RESULTS.md/QUARANTINE.md were read only to learn the
  *process* mistake to avoid (a stated boundary narrower than the actual
  implementation); this pre-registration's own metadata boundary matches the
  established EXP-0041/EXP-0020 pattern instead (see `CAPTURE_CONTRACT.json`
  `clean_room_boundary.metadata_extraction`), which is not narrower than what
  `harness/metadata.py` actually does.

## Question and driver decision

`APPLE9_RE_IMPLEMENTATION_GAPS.md` DRV-UAPI-01 requires recovering enough
Apple9 helper/scratch semantics to exercise VS/FS/CS/preamble scratch, decode
helper doorbell/SR/ABI fields, map every `binary`/`cfg` tag, specify the
scratch header/block-list/bucket/topology geometry, and establish
reset/growth/failure/device-loss behavior — all against the *unchanged* Asahi
UAPI, which assigns the scratch allocator and helper-program construction to
**userspace**. EXP-0041 tested only 208–576 B and found nothing; the
dispatching brief's instruction is to go **substantially higher**, vary
**shape** (stage, occupancy, total thread count), and to **locate** a scratch
BO or helper record if one is discoverable by widening the boundary trace
beyond EXP-0041's four-BO allowlist.

The driver decision: whether pushing pressure and trace scope further either
(a) locates a scratch-correlated BO/record we can then map field-by-field, (b)
locates a distinct helper-program record, (c) reproduces EXP-0041's negative
at a much larger scale (strengthening, not just repeating, the existing
negative), or (d) locates a clean failure/growth boundary that itself
constrains the userspace allocator's required behavior.

## Falsifiable hypotheses

- **H1 (spill-correlated boundary record, at scale).** Across a K-pressure
  ladder from clearly-no-spill through the largest per-thread scratch this M4
  compiler/pipeline path will accept, the **address-free** resource-map shape
  (`(class,size)` multiset) and the **first-seen-order content sequence**
  of every BO our own process registers changes in a way that tracks
  declared scratch bytes, independent of the compiled program's own code size.
  *Falsified* if resource-map shape and BO content sequence are identical
  across the full tested K range once code-size effects are controlled for
  (this experiment's array-loop kernel design — `kernels/generate.py` — is
  built so declared scratch bytes and compiled code size vary largely
  independently; see below).
- **H2 (stage-specific helper state).** VS/FS spill produces boundary changes
  distinct from CS spill at a matched declared-scratch level. *Falsified* if
  the same K level produces the same resource-map shape / BO-content pattern
  across CS/VS/FS (modulo the render-only BOs already known to exist only for
  draws).
- **H3 (thread-count-scaled allocation).** A pool/BO whose size scales with
  **total dispatched thread count** (not just per-thread declared bytes) is
  observable in the O-family occupancy ladder (same K, total threads from
  1,024 to 4,194,304). *Falsified* if resource-map shape and BO sizes are
  identical across the full occupancy range at fixed K — which would instead
  support a bounded/pooled backing sized by hardware concurrency, not by
  total dispatched threads (a first-class, well-bounded finding either way).
- **H4 (monotone failure frontier).** As declared per-thread scratch
  increases (K family) there is a first point of clean failure (compile
  rejection, pipeline-creation rejection, or dispatch-time error), and every
  smaller tested level succeeds. *Falsified* by a non-monotone or
  irreproducible boundary, or by silent wrong-answer corruption instead of a
  clean error/fault (both are recorded as first-class results either way).
- **H5 (distinct helper-program record).** Some captured BO or command/state
  region changes shape or content specifically when a kernel spills, in a way
  not explained by (a) compiled code-size growth or (b) the input/output
  buffers' own sizes — i.e., a *helper program* control-flow/data record
  distinct from the main program becomes observable. *Falsified* if no such
  region is found across the full tested range (this would extend EXP-0041's
  negative rather than reverse it, and would be reported with the same
  epistemic care: absence of an *observed* record is not proof of absence of
  a helper mechanism, only a bound on what ordinary Metal execution exposes
  to this trace).

## Known confounders (named up front, not discovered post hoc)

- **Compiled code size.** A naive register-pressure kernel (K live named
  scalars) grows source/instruction count with K, confounding "does a new BO
  appear because of scratch" with "because of code size." This experiment's
  kernel design (a genuine runtime loop over a `thread float a[K]` array,
  `kernels/generate.py`) was chosen and pre-verified (recorded below) to keep
  compiled `_agc.main` byte length roughly constant across three orders of
  magnitude of K, decoupling the two.
- **Input/output buffer size.** `harness/probe.m`'s compute input buffer is a
  FIXED 4096 words regardless of K or grid (kernels index it modulo 4096),
  so no client buffer's own size scales with K or with total thread count —
  a buffer that did would be a second, unrelated explanation for any observed
  BO-size change.
- **Allocator layout non-determinism.** Absolute GPU VAs are excluded from
  every cross-run/cross-case **gated** comparison (`casematrix.CASE_KEYS`
  has no address field); comparisons use address-free shape and first-seen-
  order content hashing instead (`traceparse.py`). Raw VAs remain available
  in ungated per-run logs for descriptive analysis only.
- **Numerical blow-up in the `n>1` "hot" cases.** An unbounded `fma`-growth
  recurrence overflows to non-finite output within a few dozen passes — a
  kernel-authoring artifact, not a hardware/memory fault. The H family uses a
  bounded contraction update instead (`kernels/generate.py`'s `array_body`),
  verified finite up to the pre-registered pass counts before being locked in.
- **Pre-registration-stage reconnaissance is not evidence.** Every numeric
  claim in this document (the array-loop scratch formula, the compile-time
  stack-space boundary location, the successful huge-occupancy dispatches)
  was observed while designing this harness, on throwaway sources never
  written under `raw/`. None of it is cited as a result; the same cases are
  re-run fresh under the gated pipeline (`run.py`) as `raw/<run-id>/` records,
  and only those are reported as evidence.

## Frozen authored workload

`kernels/generate.py` emits, for a fixed set of `(stage, K)` pairs, a compute/
vertex/fragment MSL source of the shape:

```c
float a[K];
for (i = 0; i < K; ++i) a[i] = input[(index*K + i) % 4096];   // seed, bounded input
for (pass = 1; pass < n; ++pass) {                             // n runtime-supplied
    t = input[pass % 4096];
    for (i = 0; i < K; ++i) a[i] = <bounded update using a[i], a[(i+1)%K], t>;
}
sum = reduce(a); <stage output> = sum;
```

Reconnaissance (throwaway, not evidence) observed this compiler reports
`scratch_bytes = 4*K + 16` from K≈192 up to at least K≈65,430, with compiled
`_agc.main` size roughly constant (~2.4–2.7 KB) from K≈192 to K=49,152 —
i.e. genuinely decoupled from K over roughly three orders of magnitude — and
located a clean compile-time `newComputePipelineStateWithFunction` rejection
("Compute function exceeds available stack space") starting somewhere in
K∈(65,430, 65,440], with no rejection at any tested K below that. It also
observed two very large executed dispatches complete successfully
(K=1,536×1,048,576 threads; K=49,152×1,048,576 threads; K=65,430×4,194,304
threads) with numerically plausible (not obviously corrupted) checksums, on a
16 GB host — incompatible with a naive
`declared_bytes × total_dispatched_threads` allocation model. **None of these
numbers is asserted as a result of this experiment; `casematrix.py` locks in
the exact case list below, and `run.py` re-executes it fresh under the gated
pipeline.**

`casematrix.py` (imported by `run.py`/`verify.py`/`analysis/*.py`, never
restated) is the frozen case list: family **K** (CS pressure ladder, K=8..
49,152 plus the boundary pair 65,430/65,440, n=1, grid=64/tg=32), family **S**
(VS/FS at K∈{96,1536,6144}), family **O** (CS, K=1536 fixed, total threads
1,024..4,194,304, threadgroup shapes 32/256/1024), family **X** (compound:
K=49,152×1,048,576 threads; K=65,430×4,194,304 threads), family **H** (n>1
hot execution: K=1536×1000 passes; K=6144×200 passes). Escalation/abort policy
is stated in `casematrix.py`'s module docstring and enforced by `run.py`.

## Safety and stop rules

- Every subprocess (metadata compile, probe compile, probe run, generator,
  smoke case) has a hard timeout from `casematrix.TIMEOUTS`, sized from this
  experiment's own reconnaissance timings with a wide margin.
- `harness/probe.m` independently caps `--grid` at 4,194,304 regardless of
  what any case requests (defense in depth, not solely relying on the case
  matrix being correct).
- Within families K/O/X (ascending risk), a clean STATUS-reported failure
  stops that family's remaining cases (K gets one grace case past its first
  failure, to capture the immediate post-boundary point); a TIMEOUT or
  unhandled exception in *any* case stops the *entire* remaining run, in every
  family, immediately.
- If the host does not recover normally after a fault/timeout: stop, mark
  BLOCKED, leave recovery to the operator. No `macvdmtool`, no automated
  reboot, ever (`CLAUDE.md`).

## Acceptance and analysis rules

Before interpreting a case as a positive scratch-correlation or a
helper-record candidate: the analyzer must show the shape/content difference
survives the code-size and buffer-size controls above, must show it
reproduces identically (address-free) across run01 and run02, and must state
the exact tested K/grid/tg/n range the claim covers. `RESULTS.md` states
OBSERVED vs INTERPRETED separately, the exact tested range, target (M4 only),
alternative explanations not excluded, and the safe driver fallback — no
byte size or shape is promoted to a hardware allocation rule, block geometry,
or helper-ABI fact merely because it correlates once; it needs the
independent-run reproduction plus the code-size/buffer-size controls.

## Required artifacts and provenance

`raw/m4-20260827-run{01,02}/` (append-only, run ids never reused): per-case
JSONL records (`02_cases.jsonl` gated, `03_timing.jsonl`/`05_raw_maps.jsonl`
ungated), `00_inputs.json` (provenance), `01_summary.json` (hashes),
`dumps/<case>/` (maptrace `.log` + per-BO `.hex` prefixes). `PROGRESS.md` gets
one line per case/milestone. `manifest.json` (via `make_manifest.py`) hashes
every committed artifact. The clean-room attestation is restated verbatim in
`README.md`/`RESULTS.md`:

```text
Clean-room provenance: OWN-SHADER / DATA-TRACE / PUBLIC API
Apple binary introspection: NONE
Apple helper-program bytes inspected: NONE (none located, or none exists to inspect)
Reproduction: README.md commands
Evidence: raw/, analysis/, manifest.json
```
