# EXP-0083 results — M4 device-buffer base-slot census (MEM-15..MEM-17)

## STATUS: CLOSED — both contracted runs captured, all gates PASS

Successor to the QUARANTINED `EXP-0078-m4-base-slot-census` (see its
`QUARANTINE.md`), whose run01 captured clean but whose frozen verifier
hardcoded the probe-instruction opcode as `0x67` for every kernel (false for
`storeprobe`'s `device_store`, `0xe7`), so `--between-runs` failed
permanently and no MEM-15/16/17 claim could be promoted. Here the ONE shared
opcode definition (`run.insn_opcode`, taking the expected byte from the
recorded `insn_hex` rather than assuming it) is used identically by the
runner's self-check, `verify.py::build_record_checks`, and the `--selftest`
synthetic-tree builder; `verify.py --between-runs` now **passes against real
captured data** (proof the fix works, not just the synthetic selftest). Both
contracted runs completed and the full gate sequence closed:

```
python3 -B verify.py --selftest            PASS 38/38 (PRE_GPU state)
python3 -B make_manifest.py --write/--check PASS
python3 -B verify.py --preflight            PASS
python3 -B run.py --execute --run-id m4-20260827-run01   351/351 ok, 0 faults
python3 -B make_manifest.py --write/--check PASS
python3 -B verify.py --between-runs         PASS   <- the exact gate EXP-0078 could never pass
python3 -B verify.py --selftest             PASS 38/38 (run01-present state)
python3 -B run.py --execute --run-id m4-20260827-run02   351/351 ok, 0 faults
python3 -B analysis.py --run-a ... --run-b ... --write   cross-run gate PASS
python3 -B make_manifest.py --write/--check PASS
python3 -B verify.py --captured             PASS
```

`raw/m4-20260827-run01/04_results.jsonl` and
`raw/m4-20260827-run02/04_results.jsonl` are **byte-identical**
(`results_sha256 = f9f81c2cf652d0c050ef74bcba1a26d8de0e32799cdb08de064c1f187a1880fa`
in both runs' `03_dispatch.json`): every one of the 351 cases reproduced
exactly, including every zero-class and pattern-decodable read. The
cross-run repeat gate (`analysis.json.repeat`) reports zero
`probe_word_differences` — perfect determinism observed, not merely
permitted.

---

## OBSERVED (directly, from `raw/m4-20260827-run01` and `-run02`, before interpretation)

- Target: local Apple M4, device name `Apple M4`, registryID `4294968259`,
  macOS `26.6.2` (build `25G82`), Darwin kernel `25.6.0`, Metal runtime
  compile (`newLibraryWithSource:`) with `fastMathEnabled=YES`,
  `math_mode_raw=2`, `language_version_raw=262144` (both recorded verbatim
  per case, not pinned). Python `3.14.6`. Git revision
  `42d502ba8f5debec672ef3e0c75e2463a392a5be` (repo dirty: untracked
  experiment directories, expected).
- Two runs, `m4-20260827-run01` and `m4-20260827-run02`, 351 cases each,
  one fresh harness process per case (fresh device, library, pipeline, 31
  bound buffers, queue, command buffer). Status counts, both runs
  identical: `ok` 351, `cb_error` 0, `watchdog` 0, `proc_fail` 0,
  `proc_timeout` 0. **No fault, hang, or command-buffer error anywhere in
  702 total case executions**, including every store and atomic through
  every unpopulated and mirrored slot value.
- Probe identification (pre-capture, `02_build.json`, both runs): census31
  diff-single-byte (probe opcode `0x67`, a `device_load`); census4
  diff-single-byte (`0x67`); storeprobe unique non-out `device_store`
  (opcode `0xe7`, selector byte+4); atomicprobe unique atomic (opcode
  `0x67`, selector byte+5, byte+4 live-but-not-selector). All four
  identifications pass the NEW coupling checks (`main[probe_main_off] ==
  insn_opcode(insn_hex)` and `main[probe_main_off:probe_main_off+14].hex()
  == insn_hex`) that replace the quarantined predecessor's hardcoded check.
- **census31 full 0..255 sweep** (256 cases; 31 buffers bound, MSL indices
  0..30, probe = one `device_load`'s base-slot byte, reading word 5):
  - slots **1..30 -> `P(slot,5)`**: every slot returns exactly its own
    buffer's word 5. `witness_ok` true, `changed` empty, all 256 cases.
  - slot **0 -> `P(5,0)`**: buffer 5's word **0** (a word-0 value under a
    word-5 probe), not buffer 0.
  - slots **31..127 -> `0x00000000`** (status `ok`, no fault).
  - slots **128..255 -> exact mirror of 0..127**, byte-for-byte
    (128->P(5,0), 129->P(1,5), ..., 158->P(30,5), 159..255->zero).
  - `mem15.census31_slots_holding_distinct_buffers = 62` (31 populated
    values counted twice, at S and S+128); `first_slot_not_holding_a_distinct_buffer = 31`.
- **census4 boundary subset** (76 cases; 4 buffers bound, MSL indices
  0..3, gid-variant indices force main-program loads, no constant-program
  hoist): slots **0..3 -> `P(slot,5)`** (slot 0 -> `P(0,5)`, i.e. the OUT
  buffer itself — unlike census31's slot 0); slots 4..127 -> zero; slots
  128..131 -> exact mirror of 0..3 (128->P(0,5), ..., 131->P(3,5));
  132..255 -> zero.
- **capacity_baseline** (never spliced; reads all 31 bindings at once):
  status `ok`, `witness_ok` true, probe `P(1,5)`, `changed` empty — every
  one of the 31 simultaneous reads correct, both runs.
- **store cases**: baseline -> `changed=[29]` (probe store wrote buffer
  29 word 5); slot 3 -> `changed=[3]`; slots 31/32/63/127/255 ->
  `changed=[]`, `witness_ok=true`, status `ok` (discarded, no fault);
  **slot 128 -> `changed=[]` but `witness_ok=false`**: the OUT buffer's
  (binding 0's) word 5 now holds `0x5A17C0DE` — the store via slot 128
  landed in binding 0.
- **atomic cases** (32-bit exchange, selector byte+5): baseline -> old
  value `P(29,5)`, `changed=[29]`; selector 3 -> old `P(3,5)`,
  `changed=[3]`; selectors 31/32/63/127/255 -> old value `0x00000000`,
  `changed=[]`, status `ok`; **selector 128 -> old value `P(5,0)`** (the
  same value the LOAD path returns for slot 0), write discarded. byte+4
  probes (values 1 and 255 at fixed selector 29) -> old value `0`, write
  discarded — byte+4 is live but not the selector for this emitted form.
- No case in either run returned a nonzero value that was not a
  `P(k,w)`-decodable pattern word (`mem17.load.nonzero_other_slots = {}`),
  and no case faulted (`mem17.load.fault_slots = {}`).

## INTERPRETED

### MEM-15 — capacity (compute stage, direct-binding path)

**At least 31 base slots are simultaneously usable and independently
correct.** The `capacity` kernel reads all 31 MSL bindings at once and every
value is correct (`H1_MEM15_capacity_all_reads_correct = True`, both runs).
The census independently confirms a 30-slot bijective load map (slots
1..30) plus binding-0 behavior on the store/atomic paths. **First failing
slot by the mandated scan: slot 31** (the first slot whose census-load probe
value is `0x00000000` rather than a distinct buffer value) —
`mem15.first_slot_not_holding_a_distinct_buffer = 31`. This is a
**direct-binding-population edge**, not a demonstrated architectural
ceiling: MSL's `[[buffer(N)]]` compiles only for N = 0..30 (compiler error
`'buffer' attribute parameter is out of bounds: must be between 0 and 30`),
so the direct-binding method cannot populate, and therefore cannot probe,
past 31 slots. Slots 31..127 are simply *unpopulated* by this binding path
(see MEM-17: they read zero, no fault, no different from an in-range
unpopulated slot) — this experiment establishes 31 as the **usable capacity
via the direct-binding API**, not an upper bound on what the base-slot
register file itself could hold if populated by another mechanism (e.g. an
argument buffer / bindless path, out of scope here).

### MEM-16 — alias/hole/reservation map (tested range: the complete 0..255 byte, every value, on census31; a 76-value boundary-focused subset plus interior sample on census4, justified in `PRE_REGISTRATION.md`)

- **No aliasing and no holes among populated slots.** Slots 1..30
  (census31) and 1..3 (census4) hold exactly their own binding, bijectively,
  including boundaries 7/8 and 15/16, which behave identically to their
  neighbors (`mem16.boundaries_31["7"]="buffer_k7_word_w5"`,
  `["8"]="buffer_k8_word_w5"`, etc. — no discontinuity at any tested
  boundary).
- **Slot 0 is a reservation candidate, and its behavior is
  pipeline-configuration-dependent, not a single fixed reservation.** In
  census31 (whose thread-invariant witness loads hoist into the
  constant/uniform-pipe program, per EXP-0078's disclosed pre-freeze
  finding), load slot 0 returns `P(5,0)` — buffer 5's word 0, not buffer 0 —
  consistent with a uniform-register-window overlap rather than "buffer 0."
  In census4 (gid-variant indices, no hoist), load slot 0 returns the plain
  OUT buffer's own value (`P(0,5)`), i.e. NOT reserved there. The STORE and
  ATOMIC paths' base 0 (via the 128-mirror) hit plain binding 0 in both
  forms (store: OUT buffer word 5 overwritten; atomic: old value equals the
  census31 load-path's slot-0 anomaly `P(5,0)`, since `atomicprobe`'s
  witness reads are also constant-index and subject to the same hoisting).
  **This sharpens H2 exactly as hypothesized**: slot 0's anomalous content
  is tied to whether the compiler hoisted thread-invariant loads into the
  constant program for that specific kernel, not to a hardware-fixed
  "slot 0 is always X" rule. Full characterization of the constant-program
  slot table is out of scope (flagged for MEM-18/19 below).
- **The selector is effectively 7-bit.** Values 128..255 mirror 0..127
  byte-for-byte, exactly, on every op path tested — census31 load (256/256
  cases), census4 load (128..131 vs 0..3), store (128 -> binding 0, same as
  a hypothetical "0"), and atomic (128 -> the slot-0 load-path value). No
  case anywhere in the 0..255 range showed a value that was NOT either (a)
  its own populated buffer's content, (b) the load-path slot-0 anomaly
  value, (c) exact zero, or (d) the exact mirror of its value−128
  counterpart. **This refutes the naive "slots outside 0..30 are simply
  zero" framing for slots 128..158** (they are NOT zero; they mirror
  1..30's non-zero content) — which is exactly why the automated
  `H3_MEM17_unpopulated_load_zero_no_fault` verdict below is `False`: the
  hypothesis as originally stated conflated "unpopulated" with "outside
  0..30," and 128..158 are outside 0..30 but not unpopulated in the
  7-bit-mirror sense. Bit 7 (value 128) is discarded by this decode path;
  no evidence anywhere of a distinct encoded meaning above 127.

### MEM-17 — unpopulated/out-of-range behavior, per op class (fault-containment characterization, not license for a compiler to emit an invalid slot)

- **LOAD**: reads `0x00000000`, command-buffer status OK, no bound-buffer
  change, for every slot in `{31..127} ∪ {159..255}` (194 zero
  observations across both censuses, including every boundary value
  31/32/63/64/127/255). Slots in `{128..158}` are NOT zero — they mirror
  their `-128` populated counterpart (the 7-bit-selector finding above),
  which is itself part of the fault-containment answer: there is no third
  behavior (alias-to-a-different-slot, garbage, or fault) anywhere in the
  space; every value is exactly one of {own buffer content, zero, exact
  mirror of value−128}.
- **STORE**: discarded through an unpopulated in-range or out-of-range
  slot (31/32/63/127/255: no buffer change, no fault); through a populated
  slot it writes that slot's buffer (slot 3 -> buffer 3); through 128 (the
  mirror of slot 0) it writes binding 0 (the OUT buffer) — i.e. the STORE
  path's slot-0 behavior is "plain binding 0," distinct from the LOAD
  path's slot-0 anomaly in census31.
- **ATOMIC (32-bit exchange)**: returns `0x00000000` and discards its
  write through an unpopulated selector (31/32/63/127/255: no fault);
  through a populated selector it exchanges that buffer (selector 3 -> old
  `P(3,5)`, buffer 3 word 5 exchanged); through 128 it returns the
  load-path slot-0 value (`P(5,0)`) and discards its write — consistent
  with the atomic probe's own witness reads being subject to the same
  constant-program interaction as census31's. Perturbing byte+4 (values 1,
  255 at a fixed, otherwise-valid selector 29) kills the access (old value
  0, discarded) — byte+4 is LIVE but is NOT the selector for this emitted
  atomic form (the selector is byte+5); this is unchanged from EXP-0078's
  disclosed finding and reconfirms `tools/agx-isa`'s `atomic_rmw`/
  `atomic_mem` descriptors (which place `base_slot` at byte+4) are at
  minimum PARTIAL/incorrect for this emitted form on M4 — flagged for the
  orchestrator; `tools/agx-isa` is read-only for this experiment.
- **Fault containment: no case in 702 total executions (2 runs x 351
  cases) faulted the command buffer or the harness process.** A bad or
  out-of-range slot is a silent zero/discard/mirror, never a fault — this
  is fault-containment information for a driver's defensive posture, not a
  license to emit an invalid slot.

## Hypotheses verdicts (automated, `analysis.json.hypotheses`, unchanged classifier from EXP-0078)

| Hypothesis | Verdict | Note |
|---|---|---|
| H1 MEM-15 capacity, all 31 reads correct | **True** | both runs |
| H2 MEM-16 slots 1..30 hold own buffer; slot 0 does not hold buffer 0 | **True** | slot-0 pipeline-dependence further characterized above |
| H3 MEM-17 unpopulated load reads zero | **False** | refuted exactly by the 7-bit mirror (128..158 are non-zero); the mirror sub-clause itself holds for every tested pair |
| H4 MEM-17 store discarded when unpopulated | **True** | slot 128 -> binding 0 is "populated" under the 7-bit reading, consistent |
| H5 MEM-17 atomic (observation only, no automated verdict) | n/a | see OBSERVED/INTERPRETED atomic sections above |
| H6 census4 binding-count independence | **False** | refuted by the SAME 7-bit mirror (census4 slot 128 holds buffer 0, not zero, and 128≠0) |

H3 and H6 being `False` is not a defect: both hypotheses, as literally
coded, required every out-of-population slot to read *exactly zero*, which
the 7-bit-mirror region (128..158 for census31; 128..131 for census4)
falsifies by construction. `PRE_REGISTRATION.md`'s sharpened H3 explicitly
anticipated this ("128..255 hypothesized as a 7-bit mirror of 0..127") and
that extension is confirmed; the negative automated verdict is the honest,
expected classification of a real, useful finding (per `CODEX.md` §7,
negative results are first-class), not a gate failure — the *gate* that
matters (`verify.py --captured`) is unrelated to these advisory verdicts
and passed cleanly.

## Exact tested range

census31: every slot byte value 0..255 (256 cases, both runs). census4: 76
boundary values (0..16, 24..40, 56..72, 120..136, 248..255). store: baseline
+ slots {3, 31, 32, 63, 127, 128, 255}. atomic: baseline + selectors {3, 31,
32, 63, 127, 128, 255} + byte+4 in {1, 255} at fixed selector 29. capacity:
one unspliced baseline. 351 cases x 2 runs = 702 total executions, all on
the local **Apple M4 (G16G)**, compute stage, direct `setBuffer:atIndex:`
binding, runtime MSL compile, one spliced byte per case, 1x1 thread
dispatch. **No A18 (G17P) claim** (hands-off per `CLAUDE.md`); no Linux/UAPI
claim; no constant-program/uniform-pipe slot-table claim beyond the
load-path slot-0 observation (flagged below for MEM-18/19); no claim about
vertex/fragment-stage reservations (out of scope; the known vertex-stage
slot-3 vertex-buffer base from prior work is unrelated to this compute-stage
census).

## Process notes addressed post-capture (coordinator directives, 2026-08-27)

Both contracted runs and the full gate sequence (including `--captured`)
completed before these directives arrived; addressed here rather than by
touching any frozen `AUTH_CODE` file, since editing `verify.py`/`run.py`
now would break the capture-time hash binding in `00_inputs.json` (the
exact EXP-0075/0078 quarantine class).

**EXP-0081 fourth defect class (byte-exactness gate applied to a record
containing nondeterministic fields) — CHECKED, NOT PRESENT.** Verified by
direct inspection of the frozen, already-hashed code:
- The only cross-run gate is `run.cross_run_problems` (shared by
  `analysis.py` and `verify.py`), which compares exactly two fields per
  case: `status` and `probe_word` from `CASE_KEYS`. `CASE_KEYS = {i, name,
  kernel, op, slot, status, exit, timed_out, cb_status, err, probe_word,
  witness_ok, changed}` — no timing, duration, address, or pid field is a
  member. `04_results.jsonl` (the byte/field-compared record) is built by
  `run.case_line`, which never copies `library_compile_seconds`,
  `dispatch_seconds`, `registry_id`, or `started_utc` from the harness's
  raw JSON into the case line.
- `05_receipts.jsonl` (`RECEIPT_LINE_KEYS`, which DOES carry `started_utc`
  and embeds the harness's timing fields inside its `stdout`) is never
  compared across runs anywhere in `run.py` or `verify.py` — confirmed by
  grep: `receipts_sha256` is checked only for self-consistency WITHIN a
  single run's own `06_run_manifest.json` (`rm["receipts_sha256"] ==
  sha(d/"05_receipts.jsonl")`), never as an equality between run01's and
  run02's values. This separation was already stated as frozen design in
  `PRE_REGISTRATION.md`'s schema section ("`05_receipts.jsonl`: ... process
  history, not byte-compared across runs") and inherited unchanged from
  EXP-0078, which never reached this gate to exercise it.
- The run02 provenance gate (`GATE_PROV`, `run.main`) compares exactly
  `git_revision`, `git_dirty`, `authored_code_sha256`,
  `authored_doc_sha256` between run01's and run02's `00_inputs.json` — also
  none of these are timing/duration/address/pid fields.
- Consistent with this design being timing-safe, `results_sha256` (a hash
  of the entire timing-free `04_results.jsonl`) came out **byte-identical**
  between run01 and run02 without being a gate requirement in itself — a
  positive, unforced confirmation that the compared record excludes
  nondeterministic content.
- **Residual gap, honestly noted, not fixed here:** the selftest does not
  carry a DEDICATED fixture that mutates only a receipt's timing field
  across synthetic run01/run02 trees and asserts the gate still PASSES
  (distinct from the existing `repeat_garbage_differ_is_reported_not_gated`
  case, which covers a garbage-class *semantic* value difference, not a
  timing-only one). The property holds by code inspection above, but is
  not selftest-proven as gate item (d) asks. Adding it now would change
  `verify.py`'s hash and break the closed captures' hash binding, so it is
  left as a documented improvement for whichever successor next touches
  `verify.py` (e.g. the MEM-18/19 increment), not applied post-capture.

**EXP-0086 (0x54/0x56 bit-17 "cache/last-use hint" register-liveness
question) — caveat.** This experiment's splices target only the base-slot
selector byte of the 14-byte memory-family encoding (byte+4 for
`device_load`/`device_store`, byte+5 for the emitted `atomic_exchange`
form, plus two dedicated byte+4-on-atomic probes characterizing that byte
as "live but not the selector"). None of these are the opcode byte
identified with the 0x54/0x56 family EXP-0086 is investigating: the probed
instructions here have opcode byte `0x67` (load/atomic) or `0xe7` (store)
at offset+0. Byte value `0x54` does appear at offset+2 of the observed
atomic encoding (`67 11 54 00 00 1d 80 80 01 02 00 00 7c 02`), but that is
a fixed, never-spliced byte within a *different* instruction family than
whatever EXP-0086 is probing, and no case in this experiment's frozen
matrix touches it. Every spliced field here (base_slot) intentionally
changes which BASE/buffer an instruction reads by design — that is the
subject under test, not a general-purpose-register operand — so no splice
in this matrix targets a register-source field. No caveat is added to the
MEM-15/16/17 findings themselves; this note is procedural, in case
EXP-0086 later shows byte+2=`0x54` in this exact instruction family is
also load-bearing, which would be a new, separate MEM-18/19-adjacent
question, not a revision of the base-slot findings above.

## What this establishes vs. what remains open

**Established (HW-VALIDATED: independently generated splices, executed on
real M4 hardware, reproduced byte-identical across two independent
captures):**
- MEM-15: 31 simultaneously usable, independently correct base slots via
  the direct-binding path; first non-distinct slot = 31.
- MEM-16: no aliasing/holes among populated slots 1..30 (any binding
  count); the base-slot selector decodes as effectively 7-bit (128..255
  exact mirror of 0..127) on every load/store/atomic form tested; slot 0 is
  a load-path reservation candidate whose exact content is
  pipeline-configuration-dependent (tied to constant-program hoisting), not
  a fixed hardware constant — census4's non-hoisted form shows slot 0 as
  plain binding 0.
- MEM-17: LOAD/STORE/ATOMIC through an unpopulated or out-of-range slot are
  uniformly fault-free; LOAD reads zero (non-mirror region) or mirrors
  (mirror region); STORE and ATOMIC discard silently (non-mirror region) or
  redirect to the mirrored binding (mirror region). No fault anywhere in
  702 executions.

**Remains open / flagged for the successor (MEM-18/19):**
- The constant-program (uniform-pipe) slot table itself: census31's
  witness loads for slots {1..7, idxbuf} hoisted into
  `_agc.main.constant_program`, whose own base-slot encoding is
  currently undecoded. This directly bears on explaining slot 0's
  census31-vs-census4 discrepancy and is the natural next increment.
- Whether the 7-bit-selector finding holds for non-32-bit atomic forms,
  other memory-family op encodings, or the fragment/vertex stages (out of
  scope here; compute stage only).
- Whether an architectural base-slot ceiling exists above 31 via a
  non-direct-binding population mechanism (argument buffers / bindless);
  the direct `[[buffer(N)]]` API caps authored population at 31 and this
  experiment cannot probe past that ceiling.
- `tools/agx-isa`'s atomic_rmw/atomic_mem `base_slot`-at-byte+4 mapping is
  reconfirmed PARTIAL/incorrect for the emitted forms observed here
  (selector is byte+5); flagged for the orchestrator, not corrected here
  (`tools/*` read-only for this experiment).

## Clean-room provenance

```text
Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API
Inputs inspected: authored MSL/harness/runner/verifier/analysis sources;
tools/shdump, tools/agxtest, tools/agx-isa invoked read-only (never edited)
Apple binary introspection: NONE (only our own compiled shader bytes were
spliced and executed; harness/probe.m and run.py touch only public
Metal/Foundation API and our own archives)
Reproduction: python3 -B verify.py --selftest && python3 -B make_manifest.py
--write && python3 -B make_manifest.py --check && python3 -B verify.py
--preflight && python3 -B run.py --execute --run-id m4-20260827-run01 &&
python3 -B make_manifest.py --write && python3 -B make_manifest.py --check
&& python3 -B verify.py --between-runs && python3 -B verify.py --selftest
&& python3 -B run.py --execute --run-id m4-20260827-run02 && python3 -B
analysis.py --run-a m4-20260827-run01 --run-b m4-20260827-run02 --write &&
python3 -B make_manifest.py --write && python3 -B make_manifest.py --check
&& python3 -B verify.py --captured
Evidence: raw/m4-20260827-run01/ (7 files: 351 case lines + 351 receipts +
build/identification/matrix/inputs/manifest records), raw/m4-20260827-run02/
(same shape), analysis.json (147802 bytes, cross-run gate PASS, zero
probe_word differences), manifest.json (CAPTURED state, all hashes verified)
```
