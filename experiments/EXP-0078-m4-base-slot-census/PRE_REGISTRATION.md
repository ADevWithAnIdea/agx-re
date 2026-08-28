# EXP-0078 pre-registration — M4 device-buffer base-slot census (MEM-15/16/17)

**Frozen state: PRE-GPU.** No contracted Metal compilation or execution has
occurred for EXP-0078 at freeze time. A **pre-freeze authoring-feasibility
probe** DID run (disclosed in full below and in `PROGRESS.md` M2, scratch
deleted): it fixed the MSL buffer-index limit, the kernel shapes, the probe
identification rules, and the atomic selector byte, so that this registration
freezes kernels that compile and a matrix that is executable. Nothing from the
probe is evidence; every contracted claim below is established (or refuted) by
the two contracted runs. Anything that could not be frozen before the build is
a STOP, not an improvisation.

## Question

Part-II questionnaire items **MEM-15, MEM-16, MEM-17** of
`APPLE9_RE_IMPLEMENTATION_GAPS.md` ("P0 — Memory addressing and robustness"):

- **MEM-15** — maximum number of simultaneously usable device-buffer base
  slots for one shader stage.
- **MEM-16** — are all encoded `base_slot` values below that maximum
  independently selectable, with no aliasing, holes, or stage-specific
  reservations (boundaries 7/8, 15/16, 31/32, 63/64, 127/128, 255)?
- **MEM-17** — does accessing an unpopulated or out-of-range base slot return
  zero, alias another slot, or fault — for load, store, and atomic
  operations separately (fault-containment information, not a license for a
  compiler to emit an invalid slot)?

This is the user-directed top-priority load/store/SSBO cluster increment.
Compiler consequence (recorded, not implemented here): the answers bound how
many SSBO/base-pointer slots a Vulkan compiler may assume per stage, whether
every encoded slot value is legal, and what fault containment to expect for a
bad slot.

## Disclosed pre-freeze feasibility findings (scratch, deleted; NOT evidence)

1. `[[buffer(N)]]` compiles for N = 0..30 only — the compiler error is
   verbatim `error: 'buffer' attribute parameter is out of bounds: must be
   between 0 and 30` — so the direct-binding population maximum is
   **31 buffers**.
2. `census31` probe-vs-variant differ in exactly ONE byte of `_agc.main` (the
   probe load's base_slot byte); same for `census4`. This is the frozen
   identification rule for the census kernels.
3. Thread-invariant loads hoist into `_agc.main.constant_program` (a
   uniform-pipe program whose own loads use a different, currently-undecoded
   slot encoding); gid-variant indices keep loads in the main program.
4. Spot splices on the un-contracted probe: slots 2/29/30 returned the correct
   buffers' word 5; slots 31/32/63/127/255 read 0x00000000 with no fault;
   slot 0 returned `P(5,0)` (buffer 5's word 0 — a word-0 value under a
   word-5 probe; hypothesis: a **uniform-register window**, not buffer 0);
   slot 128 returned slot 0's value (alias). These motivate H2/H3; the
   contracted sweep re-establishes every one of them.
5. The emitted atomic form's base selector is **byte+5** (values 29/28
   tracking the abuf MSL index; splice 29->28 retargeted the exchange);
   byte+4 stays 0x00 but is LIVE (0->1 made the exchange read 0). The
   `tools/agx-isa` DB places atomic base_slot at byte+4 — at minimum PARTIAL
   for these forms. `tools/*` are read-only here: recorded for the
   orchestrator, not edited.

## Hypotheses (falsifiable; refuters are per-case and recorded verbatim)

On this machine (Apple M4 / G16G, macOS 26.6.2 build 25G82, Metal 4, runtime
compile with `fastMathEnabled=YES`), for MSL authored by us, one 1-thread
compute dispatch per case, all 31 MSL buffer indices bound to 64-byte buffers
filled with the frozen pattern:

- **H1 (MEM-15).** The `capacity` kernel — which independently reads a
  distinguishable value through every one of the 31 MSL buffer indices at
  once — returns every value correctly (all 30 witness words plus the probe
  match the fill model). Refuted by any witness mismatch, fault, or nonzero
  `changed` in `capacity_baseline`.
- **H2 (MEM-16).** In the 31-binding census, slot k for k = 1..30 holds
  exactly buffer k's base: the spliced probe returns `P(k,5)` with word index
  5. Slot 0 does NOT hold buffer 0 (feasibility: it returned `P(5,0)`); its
  content is characterized, not assumed. Refuted by any slot 1..30 whose
  probe returns another buffer's word, zero, garbage, or a fault.
- **H3 (MEM-17 load).** Every census slot outside the populated set reads
  `0x00000000` with command-buffer status OK and no bound-buffer change; and
  slots 128..255 behave identically to their value−128 counterparts
  (feasibility: 128 aliased 0). Refuted by any nonzero non-pattern read, any
  fault status, any `changed` list, or any 128+ slot differing from its
  −128 counterpart.
- **H4 (MEM-17 store).** A store through an unpopulated slot is discarded
  (no bound buffer changes, no fault); a store through a populated slot
  writes that slot's buffer at word 5 (`0x5A17C0DE`). Refuted by any
  `changed` entry at an unpopulated slot, or any fault.
- **H5 (MEM-17 atomic).** An exchange through an unpopulated selector
  returns `0x00000000` and its write is discarded, no fault; through a
  populated selector it exchanges that buffer's word 5. The two
  `at_b4probe` cases (byte+4 spliced at a fixed selector) characterize
  byte+4's role. Refuted analogously.
- **H6 (control).** With only 4 buffers bound (`census4`), slots 1..3 hold
  the same buffers as in the 31-binding census and every other tested slot
  reads zero — per-slot content independent of binding count below the
  direct-binding maximum. Refuted by any census4 slot 1..3 disagreeing with
  census31, or any other tested slot returning a pattern word.

Independent variable: the frozen 351-case matrix (kernel x spliced slot
byte). Controlled variables: kernel sources, compile options, the 31-buffer
fill, dispatch geometry, the harness process model, and the
one-spliced-byte-per-case rule.

## Exact frozen method

1. **Kernels** (`kernels/`, nine authored files): `census31`(+`_v2`) — 31
   bound buffers, constant-index witness reads for b1..b29, probe
   `out[0] = b1[i0]` with `i0 = idxbuf[0] = 5`; `census4`(+`_v2`) — 4 bound
   buffers, gid-variant indices (forces main-program loads); `capacity` —
   gid-variant reads of all 31 bindings, never spliced; `storeprobe`
   (+`_v2`) — 31 bindings, probe store `tgt[5] = 0x5A17C0DE` (tgt at MSL 29
   / 28 in v2); `atomicprobe`(+`_v2`) — 31 bindings, probe
   `atomic_exchange_explicit(&abuf[5], 0x5A17C0DEu, relaxed)` (abuf at MSL
   29 / 28 in v2).
2. **Fill model (single source of truth in `run.py`).** Word w of buffer k =
   `P(k,w) = 0xC0DE0000 | (k<<8) | w`; the idxbuf binding (MSL 30, or 3 in
   census4) carries word 0 = 5 (the probe element index). Every 32-bit read
   anywhere in any buffer decodes uniquely to (buffer, word). The harness
   itself constructs and echoes the binding layout (index -> contents) in
   every record: the public-API binding capture, not a guess.
3. **Probe identification (pre-capture, recorded in `02_build.json`).**
   census kernels: the v1/v2 `_agc.main` diff must be EXACTLY one byte, at
   +4 of a 14-byte `0x67` load. storeprobe: the unique `device_store` whose
   base slot is not the out buffer's (cross-checked against v2). atomicprobe:
   the unique atomic instruction (byte0 `0x67`, byte+1 `01`/`11`), selector
   byte+5 (cross-checked against v2). Walks use the read-only
   `tools/agx-isa` DB; archives come from `tools/shdump` on our own sources.
4. **Harness** (`harness/probe.m`, public API only): one case per process;
   compiles the kernel source, loads the (runner-spliced) archive, forces
   the pipeline with `MTLPipelineOptionFailOnBinaryArchiveMiss`, binds all
   31 buffers filled with the pattern, dispatches 1x1, waits synchronously,
   and prints one complete JSON record (out dump + every bound buffer
   dump). Single-threaded, SIGALRM watchdogs (120 s compile exit 97,
   100 s dispatch exit 98), fflush/ferror exit discipline.
5. **Runner** (`run.py --execute --run-id <id>`): refuses without
   `--execute`; requires `verify.py --selftest` then the
   preflight/between-runs gate; records git revision + dirty flags +
   `sw_vers` + `xcrun --version` + python/machine + all authored SHA-256;
   builds the harness + shdump; compiles the nine kernels; runs the
   identification; runs the NON-RECORDED smoke invocation
   (`c31_load_slot_1`, an identity splice) into `work/` — only then creates
   the append-only raw tree and dispatches the 351 cases, one fresh process
   each. A faulted/hung/killed case is a recorded result, never retried in
   place; only 3 consecutive OS-level spawn failures stop the run.
6. **Two fresh runs**: `raw/m4-20260827-run01` and `raw/m4-20260827-run02`;
   run 02 additionally requires identical revision and authored hashes to
   the closed run 01 record.

## Frozen case matrix (351 cases per run, exact)

- **census31 full sweep (256):** `c31_load_slot_S`, S = 0..255 — the probe
  load's base_slot byte spliced to S. The complete encoded range of the
  8-bit field, every value its own case: no sampling, no equivalence-class
  shortcut, on the maximal-binding kernel.
- **census4 boundary subset (76):** `c4_load_slot_S`, S in 0..16, 24..40,
  56..72, 120..136, 248..255 — every MEM-16 boundary (7/8, 15/16, 31/32,
  63/64, 127/128, 255) with 16-value context windows on both sides, plus
  the alias-check tail. Sampling justification (the finite-resource
  mandate): the 4-binding control's question is per-slot content vs the
  31-binding census at the boundary classes; its interior beyond the
  populated set is covered by the same classes, and the FULL population
  range (0..30) is exhaustively covered by census31.
- **capacity (1):** `capacity_baseline`, unspliced — the MEM-15 direct
  method (independent distinguishable reads through every slot at once).
- **store (8):** `st_store_baseline` plus `st_store_slot_S` for
  S in {3, 31, 32, 63, 127, 128, 255} — 3 = populated (b3 bound), 31 =
  first beyond the 31-slot direct-binding range, 32/63/127/128 = the MEM-16
  power-of-two boundaries, 255 = max encoded.
- **atomic (10):** `at_axch_baseline` plus `at_axch_sel_S` for the same
  seven values (selector byte+5), plus `at_b4probe_1` / `at_b4probe_255`
  (byte+4 spliced at the fixed selector 29) characterizing the atomic
  byte+4 field.

Slot-value classes are structural (frozen before any contracted
observation); the census's observed populated set re-labels each MEM-17 case
as unpopulated-in-range or out-of-range in the INTERPRETATION, never by
editing the matrix. Example case names: `c31_load_slot_0`,
`c31_load_slot_128`, `c31_load_slot_255`, `c4_load_slot_128`,
`capacity_baseline`, `st_store_baseline`, `st_store_slot_3`,
`st_store_slot_255`, `at_axch_baseline`, `at_axch_sel_31`,
`at_b4probe_255`. Prior context the interpretation must consider for
reserved values: EXP-0012 observed threadgroup loads using base_slot 0x08
(a local descriptor) and the vertex stage using slot 3 as the vertex-buffer
base — any slot the census shows holding a non-buffer value (or aliasing)
is recorded as a reservation candidate, with the threadgroup/uniform-pipe
distinction flagged for the MEM-18/19 successor.

## Per-case record schema (frozen; single authoritative key sets)

- `04_results.jsonl`, one line per case, exactly 13 keys: `i, name, kernel,
  op, slot, status, exit, timed_out, cb_status, err, probe_word,
  witness_ok, changed`. `probe_word` = out word 0 (8 hex chars);
  `witness_ok` = all non-probe out words match the fill model; `changed` =
  bound buffer indices (1..30) whose post-run dump differs from the fill.
- Statuses (frozen enum): `ok` (exit 0, command-buffer status 4), `cb_error`
  (full record, status != 4), `watchdog` (in-process SIGALRM exit 97/98),
  `proc_fail` (process died / unparseable record), `proc_timeout` (outer
  120 s). All five are results.
- `05_receipts.jsonl`: one subprocess receipt per case (9-key receipt +
  `i`, `name`) — process history, not byte-compared across runs.
- `02_build.json`: the host-build receipt, the read-only tool hashes, the
  nine kernel records (`archive_sha256`, `main_off`, `main_len`,
  `main_hex`), and the four probe identification records — all BEFORE any
  case runs.
- Witness mismatches and buffer changes are OBSERVATIONS, not gate
  conditions: a `witness_ok=false` or nonempty `changed` on a spliced case
  is exactly the alias/corruption answer, and `verify.py` accepts it as
  valid evidence (proven by the self-test case
  `witness_corrupt_case_is_valid_evidence`).

## Cross-run repeat policy (frozen before any build)

Every case must have **identical status** in the two runs, and `probe_word`
must be identical whenever either run's value is in a **deterministic
class** (exactly zero, or pattern-decodable `P(k,w)`). Only garbage-class
values (nonzero, non-decodable — e.g. reads of uninitialized/unmapped
memory) may legitimately differ, and `analysis.py` REPORTS every such
difference as the observed determinism answer for MEM-17. The gate is
implemented once (`run.cross_run_problems`) and shared by `analysis.py` and
`verify.py`.

## Environment, timeouts, and raw schema (frozen)

- Target: the local Apple M4 (G16G) through public Metal only; harness built
  with `xcrun clang -fobjc-arc -framework Metal -framework Foundation`.
- Hard timeouts: environment commands 10 s; host build 120 s; per-kernel
  compile 120 s; identification commands 60 s; per-case process 120 s
  (outer belt) with in-process watchdogs 120 s compile / 100 s dispatch.
- Raw schema per run: `00_inputs.json`, `01_matrix.json`, `02_build.json`,
  `03_dispatch.json`, `04_results.jsonl`, `05_receipts.jsonl`,
  `06_run_manifest.json`. Raw is append-only, regular files only, no
  symlinks, text/JSON only (archives live in `work/`, hashed in
  `02_build.json`, deleted with `work/`). Pre-capture failures (environment,
  host build, kernel compile, identification, smoke gate) retain
  `work/<run-id>/STOP.json` and never create the raw tree; a post-capture
  infrastructure failure writes `raw/<run-id>/STOP.json` and ends that run.
  Nothing is retried automatically.

## Promotion rule and full gate sequence

Before any capture, in this exact order and all passing:
`python3 -B verify.py --selftest` (schema gates + smoke purity + the
gate-sequence state machine: every contracted gate proven runnable and
satisfiable at the state where the contract invokes it, and fail-correct
where it must not pass), `python3 -B make_manifest.py --write`,
`python3 -B make_manifest.py --check`, `python3 -B verify.py --preflight`.
Then `python3 -B run.py --execute --run-id m4-20260827-run01`; then
`make_manifest.py --write` + `--check` and `python3 -B verify.py
--between-runs`; then `python3 -B verify.py --selftest` again (proving the
self-test still runs in the run01-present state — the EXP-0075 fix); then
`python3 -B run.py --execute --run-id m4-20260827-run02`; then
`python3 -B analysis.py --run-a m4-20260827-run01 --run-b
m4-20260827-run02 --write` must exit zero (cross-run repeat gate green);
then `make_manifest.py --write` + `--check`; then `python3 -B verify.py
--captured` for exactly the two contracted runs. The identical sequence is
frozen verbatim in `CAPTURE_CONTRACT.json` (`full_gate_sequence`); a
contract whose gate order cannot be walked is an automatic pre-capture
stop. Until then MEM-15, MEM-16 and MEM-17 remain **Open** for this
configuration.

This experiment cannot establish: behavior of any other compiler version or
OS, Linux/UAPI behavior, the constant-program (uniform-pipe) slot table
beyond what the main-program census observes (a MEM-18/19 successor
question), the content of slots the direct-binding path never populates
beyond their observable read/store/atomic behavior, or any A18 (G17P) claim
— the A18 is hands-off for this work and no cross-target inference is drawn.
Slot semantics here are the **compute stage**; fragment/vertex stage
reservations (e.g. the known vertex-stage slot 3 vertex-buffer base) are out
of scope and flagged for the successor.

## Authored blob hashes at freeze (SHA-256)

Every value below is derived from this experiment's own final bytes and is
independently enforced by `CAPTURE_CONTRACT.json` (`authored_sha256`), which
`verify.py` re-checks at every gate.

- `kernels/census31.metal`, `kernels/census31_v2.metal`,
  `kernels/census4.metal`, `kernels/census4_v2.metal`,
  `kernels/capacity.metal`, `kernels/storeprobe.metal`,
  `kernels/storeprobe_v2.metal`, `kernels/atomicprobe.metal`,
  `kernels/atomicprobe_v2.metal`, `harness/probe.m`, `harness/build.sh`,
  `run.py`, `analysis.py`, `make_manifest.py`, `verify.py`: see
  `CAPTURE_CONTRACT.json` (`authored_sha256`, exact key-set equality).
- `PRE_REGISTRATION.md`: self (hash frozen in `CAPTURE_CONTRACT.json`).
- `README.md`: frozen in `CAPTURE_CONTRACT.json`.

Clean-room provenance: OWN-SHADER + HW-PROBE + PUBLIC API (planned only)
Inputs inspected: authored MSL/harness/runner/verifier/analysis sources and
the read-only repo tools (`tools/shdump`, `tools/agxtest`, `tools/agx-isa`)
invoked, never edited
Apple binary introspection: NONE (our own compiled shader bytes only)
Reproduction: `python3 -B verify.py --selftest` then
`python3 -B make_manifest.py --write && python3 -B make_manifest.py --check`
then `python3 -B verify.py --preflight`; capture requires explicit
`run.py --execute`
Evidence: no raw observations exist at freeze; `CAPTURE_CONTRACT.json` is
the frozen grammar
