# EXP-0083 progress log (append-only)

Operational note recorded at open (2026-08-27): per the governing directives
(`CLAUDE.md` / `CODEX.md`) all testing runs **locally on the M4** through the
public Metal API; the A18 Pro is **hands-off** (no SSH, no probing, no
reference); `macvdmtool` is never run against any target. Splice probes run
one changed field per case, every case in its own process, hard timeouts
everywhere. If the host wedges: STOP, mark BLOCKED, wait for manual reboot.

## 2026-08-27 (open) — M1: tasking + mandatory reading complete

- Read in order: `CLAUDE.md` (governing law), `CODEX.md` (binding process),
  `experiments/SUBAGENT_BRIEF.md`. Then the QUARANTINED predecessor
  `../EXP-0078-m4-base-slot-census/QUARANTINE.md`, `PRE_REGISTRATION.md`,
  `CAPTURE_CONTRACT.json`, `run.py`, `verify.py`, `kernels/`, `harness/`,
  and `raw/m4-20260827-run01/` in full, plus its `RESULTS.md` and
  `PROGRESS.md` for the exact failure narrative and successor requirements.
- Task: Part-II questionnaire items **MEM-15, MEM-16, MEM-17**
  (`APPLE9_RE_IMPLEMENTATION_GAPS.md`, "P0 — Memory addressing and
  robustness"): same question as EXP-0078; EXP-0078 is QUARANTINED (not a
  redo/repair-in-place, per `CODEX.md` §8: a successor takes a new
  experiment number and a fresh pre-registration).

## 2026-08-27 — M2: root-cause of the EXP-0078 defect confirmed by reading

- `verify.py::build_record_checks` (EXP-0078, line ~345) hardcoded
  `main[ir["probe_main_off"]] == 0x67` for EVERY kernel's identified probe
  instruction. True for census31/census4 (device_load, 0x67) and
  atomicprobe (atomic, 0x67 for the emitted form), FALSE for storeprobe's
  `device_store` (0xe7) — correctly identified and recorded in
  `02_build.json` by `run.py::identify()`'s `decode_unique_nonout_store`
  method, but rejected by the verifier's wrong uniform assumption.
- The self-test could not catch this because its synthetic-tree builder
  (`_build_kernel_records`) independently poked the SAME hardcoded `0x67`
  into the synthetic storeprobe main — internally consistent with the
  broken verifier, reality-inconsistent with the real captured bytes
  (whose `insn_hex` for storeprobe correctly starts with `e7`).
- Root cause: TWO independent hardcodings of the same wrong assumption
  (verifier check, selftest fixture) that agreed with each other but not
  with the real per-op-class opcode. Fix: ONE shared definition
  (`run.insn_opcode(insn_hex) = int(insn_hex[0:2], 16)`), used by (a) the
  runner's own capture-time self-check in `compile_and_identify`, (b)
  `verify.py::build_record_checks` (replacing the hardcoded `0x67`), (c)
  `verify.py`'s synthetic-tree builder (`_build_kernel_records`, which now
  writes the FULL recorded 14-byte `insn_hex` at the probe offset instead
  of poking three independently-chosen bytes). `SYNTH_IDENT`'s `insn_hex`
  literals were corrected to be self-consistent per kernel (census31/
  census4/storeprobe now encode their own `orig_value`/`byte4_value` at the
  right offset instead of a `"67"+"00"*13` placeholder that was overridden
  by pokes; atomicprobe's `insn_hex` was already the real captured
  instruction and needed no change).

## 2026-08-27 — M3: kernels + harness reused verbatim; runner/verifier fixed

- `kernels/*.metal` (9 files) and `harness/probe.m`/`build.sh` copied
  unchanged in design from EXP-0078 (only the `EXP-0078` -> `EXP-0083`
  label in comments changed); the frozen 351-case matrix in `run.py` is
  byte-for-byte the same generation logic.
- `run.py`: added `insn_opcode()` (the one shared definition) and a
  capture-time self-check in `compile_and_identify` asserting
  `mains[a][r["probe_main_off"]] == insn_opcode(r["insn_hex"])` for every
  identified kernel, immediately after `identify()` returns.
- `verify.py::build_record_checks`: replaced the hardcoded `0x67` opcode
  check with `main[probe_main_off] == R.insn_opcode(insn_hex)`, and added a
  full 14-byte coupling check (`main[probe_main_off:probe_main_off+14].hex()
  == insn_hex`) so a truncated/partially-tampered `insn_hex` is caught even
  when only the opcode byte happens to agree.
- `verify.py`'s selftest: `SYNTH_IDENT`'s `insn_hex` literals corrected
  (census31/census4: `6700000001000000000000000000`; storeprobe:
  `e70000001d000000000000000000`; atomicprobe: unchanged, already the real
  captured instruction); `_build_kernel_records` now writes the full
  recorded `insn_hex` bytes (with self-check assertions) instead of poking
  a hardcoded opcode. Two new selftest cases added: PASS
  `ident_opcode_realistic_per_kernel_passes` (run01-present state, routed
  through `gate_between`, per-kernel-correct opcodes) and FAIL
  `ident_opcode_mismatch_storeprobe` (corrupts the captured storeprobe main
  byte away from its own recorded `insn_hex`, must be rejected with "ident
  probe opcode").

## 2026-08-27 — M4: PRE_REGISTRATION.md / README.md / CAPTURE_CONTRACT.json frozen

- `PRE_REGISTRATION.md`: predecessor lineage + defect + fix documented up
  front; EXP-0078 run01's disclosed observations (census31/census4/
  capacity/store/atomic slot maps, zero fault rate) added as a new
  "Disclosed prior evidence" section, explicitly NOT evidence for this
  experiment; H2 sharpened (slot-0 load-path reservation candidate) and H3
  extended (128..255 hypothesized as a 7-bit-mirror of 0..127) to carry
  those disclosed observations as hypotheses to independently re-establish,
  not facts. Frozen method, matrix, schemas, timeouts, and gate sequence
  are otherwise unchanged from EXP-0078 (same kernels, same 351 cases).
- `CAPTURE_CONTRACT.json`: `experiment` renamed; `predecessor` block added
  (defect/fix/unchanged-artifacts summary); `H2_MEM16`/`H3_MEM17_load`
  hypothesis text extended (prefixes preserved for `contract_checks`);
  `authored_sha256` regenerated against the final EXP-0083 file bytes.
- Selftest run locally (no Metal, no device) to validate the fix before
  going further; see M5 below for the result.

## 2026-08-27 — M5: selftest green (fix validated on synthetic + against defect class)

- `python3 -B verify.py --selftest` -> **PASS 38/38** (no Metal, no device),
  including the two new fixtures: `ident_opcode_realistic_per_kernel_passes`
  (run01-present state via `gate_between`, per-kernel-correct synthetic
  opcodes — the positive regression proof) and
  `ident_opcode_mismatch_storeprobe` (a captured storeprobe main byte
  corrupted away from its own recorded `insn_hex`, correctly rejected with
  "ident probe opcode" — the negative regression proof).
- `make_manifest.py --write/--check` PASS, `verify.py --preflight` PASS
  (PRE_GPU, no raw).

## 2026-08-27 — M6: run01 captured, `--between-runs` PASSES (the fix proven against reality)

- `run.py --execute --run-id m4-20260827-run01`: 351/351 cases recorded,
  all status `ok` — zero `cb_error`/`watchdog`/`proc_fail`/`proc_timeout`.
  No host wedge; no reboot; `macvdmtool` never run.
- `make_manifest.py --write/--check` PASS. **`verify.py --between-runs`
  PASSES** — this is the exact gate that failed permanently in EXP-0078
  (`FAIL ident probe opcode m4-20260827-run01 storeprobe`); it now passes
  against REAL captured data (storeprobe's real opcode is `0xe7`, correctly
  derived from its own recorded `insn_hex` rather than assumed as `0x67`).
- `verify.py --selftest` run again with run01 present -> PASS 38/38
  (confirms gate (a)/(b) of the standing gate set: selftest runnable and
  green in both PRE_GPU and run01-present states).

## 2026-08-27 — M7: run02 captured, full gate sequence closed

- `run.py --execute --run-id m4-20260827-run02`: 351/351 `ok`, zero
  faults. `04_results.jsonl` is **byte-identical** to run01's
  (`results_sha256 = f9f81c2c...1880fa` in both `03_dispatch.json`
  records) — perfect cross-run determinism observed, not merely permitted.
- `make_manifest.py --write/--check` PASS. `analysis.py --run-a
  m4-20260827-run01 --run-b m4-20260827-run02 --write` -> cross-run gate
  PASS, `analysis.json` written (147802 bytes, zero
  `probe_word_differences`). `make_manifest.py --write/--check` PASS.
  **`verify.py --captured` PASSES.** MEM-15/16/17 are CLOSED for this
  configuration (compute stage, direct-binding, local M4).
- Findings independently re-establish EVERY one of EXP-0078 run01's
  disclosed (non-evidentiary) observations, now HW-VALIDATED across two
  fresh captures: 31-slot direct-binding capacity; bijective slots 1..30;
  slot-0 load-path anomaly (census31: `P(5,0)`, pipeline-hoist-dependent;
  census4: plain binding 0, no hoist); the base-slot selector decoding as
  effectively 7-bit (128..255 exact mirror of 0..127) on every op path;
  zero-fault containment for LOAD (zero)/STORE (discard or redirect to
  binding 0)/ATOMIC (return 0 + discard, or redirect) through every
  unpopulated/out-of-range/mirrored slot; atomic byte+4 live-but-not-
  selector (selector is byte+5).
- `RESULTS.md` rewritten in full: OBSERVED vs INTERPRETED, MEM-15/16/17
  response blocks, hypotheses verdicts table (H3/H6 automated `False`
  explained as the honest, expected 7-bit-mirror refutation of an
  overly-strict literal hypothesis, not a defect), exact tested range,
  clean-room attestation.

## 2026-08-27 — M8: coordinator directives addressed post-capture

- Checked for the EXP-0081 fourth contract-defect class (a byte-exactness
  gate applied to a record containing nondeterministic timing/duration/
  address/pid fields) by direct code inspection of the ALREADY-CAPTURED,
  hash-frozen `run.py`/`verify.py` (not by editing them, which would break
  the capture-time hash binding). **Confirmed NOT present**: the only
  cross-run gate (`run.cross_run_problems`) touches only `status` and
  `probe_word` from `CASE_KEYS`, which contains no timing/duration/
  address/pid field; `05_receipts.jsonl` (which does carry `started_utc`
  and embeds harness timing in its `stdout`) is never compared across runs
  anywhere in the frozen code, only self-hash-checked within one run's own
  manifest. Full evidence and the one honestly-noted residual gap (no
  DEDICATED selftest fixture proving "timing-only receipt differences
  don't fail the gate," though the property holds by inspection) recorded
  in `RESULTS.md`'s new "Process notes addressed post-capture" section;
  left for a successor to add rather than repairing `verify.py` now.
- Checked the EXP-0086 caveat (0x54/0x56 bit-17 hint / register-liveness):
  this experiment's spliced field is the base-slot selector (byte+4 for
  load/store, byte+5 for the emitted atomic form), never the opcode byte
  (`0x67`/`0xe7`) or the byte+2=`0x54` position observed-but-never-spliced
  in the atomic encoding. No direct overlap identified; noted as a
  procedural caveat in `RESULTS.md`, matrix left unchanged per instruction.
- No further device operations after run02. Experiment CLOSED.
