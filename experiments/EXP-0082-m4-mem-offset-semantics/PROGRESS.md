# EXP-0082 progress log

- **2026-08-28T00:5xZ — M1: successor created.** EXP-0082 succeeds the
  terminal EXP-0081 (both contracted runs captured cleanly, 2164 cases each;
  quarantined only because its cross-run byte-exactness gate compared a
  record embedding GPUTIME_NS/duration_ms, both inherently nondeterministic
  -- unsatisfiable by construction, not a hardware-reproducibility problem).
  Root fix: `run.py::parse_agxtest` splits stdout into a deterministic
  `semantic` dict (MAIN_LEN/DEVICE/FUNCTION/PIPELINE_SOURCE/STATUS/OUT/a hash
  of RESULT) and a separate `gputime_ns`; `run_one_case` now writes TWO
  records per case -- `public` (CASE_KEYS) to `04_results.jsonl` (the ONLY
  file the cross-run gate compares) and `timing` (TIMING_KEYS) to the sibling
  `04_timing.jsonl` (schema-checked, never cross-run compared). New
  `verify.py::timing_isolation_checks()` structural guardrail (CASE_KEYS can
  never regain a timing field); new selftest fixture
  `cross_run_timing_only_diff_passes` proves the gate PASSES when only timing
  differs, and `cross_run_semantic_field_tampered` proves it still FAILS on a
  one-field semantic difference confined to a NEW field (`device`). Matrix,
  kernels, and splice form byte-identical to EXP-0081's frozen design (not
  tuned from EXP-0081's unpromoted observations). Additionally: independently
  re-ran EXP-0081's own hand-validation cross-check against its raw run01
  data and found a THIRD divergence beyond the two the dispatch named
  (`ld_wrap_ffffffff_p1`, matching QUARANTINE.md's "3 hand-set divergences"
  count) -- applied identical treatment (removed from the hard gate,
  re-registered as hypothesis H-DIV-3 in PRE_REGISTRATION.md). Run ids dated
  2026-08-28 (UTC).

- **2026-08-28T00:5xZ — M2: first run01 attempt captured, then discarded
  pre-promotion (environmental, not a data defect).** All pre-capture gates
  passed (`--selftest` 23/23, `--seqtest` 15/15, `--preflight`).
  `run01` captured cleanly: 2164 cases, `status_counts {CMDBUF_ERROR: 2, OK:
  2162}` (matches EXP-0081 exactly), all 7 retained hand-validation entries
  matched, and the three re-registered hypotheses (H-DIV-1/2/3) reproduced
  EXP-0081's characterization exactly (`ld_scale1_code1`/`code2` both read
  byte offset 0 instead of 1/2; `ld_wrap_ffffffff_p1` read raw `0x00000000`,
  undecodable, not a genuine wrap to word 0) -- an early, non-gated signal
  that these are real reproducible hardware behaviors. `run02` then refused
  at the `cross_run_provenance_gate` (before any `raw/`/`work/` artifact for
  run02 was created -- clean stop, no run id burned): another agent's
  unrelated concurrent work in this shared repo advanced `HEAD` from
  `a7d9880e` (run01's captured revision) to `2b5ab5ab`
  (`docs(provenance): record MEM-15/16/17 answers and EXP-0083 evidence
  chain`) between the two captures. Since `raw/` immutability protects
  PROMOTED evidence and this single unpromoted run could never be paired
  (the frozen revision is gone from `HEAD` and cannot be restored without a
  disallowed history rewrite), the stale `raw/m4-20260828-run01` was deleted
  and `manifest.json` regenerated back to `PRE_GPU` -- not a repair-in-place
  of a defect, a clean restart of an incomplete, not-yet-cross-verified
  capture sequence at a stable revision. Also cleaned up a stray
  `__pycache__/casematrix.cpython-314.pyc` left by an ad-hoc `python3 -c`
  diagnostic invocation that omitted `-B` (my error, not the harness's --
  every harness-internal subprocess invocation uses `-B` and none write
  bytecode). PROGRESS.md itself is NOT part of `manifest.json`'s hash set
  drift concern for the frozen `authored_sha256` (it is intentionally
  excluded from `AUTH_ALL`/`CAPTURE_CONTRACT.json`'s hash-pinned set, unlike
  `PRE_REGISTRATION.md`/`README.md`), so appending here does not require a
  re-freeze.

- **2026-08-28T01:03Z-01:07Z — M3: run01+run02 re-captured back-to-back at a
  stable revision (`ab874936`, unchanged across both).** `04_results.jsonl`
  is **byte-identical** across the two runs (`results_sha256
  b29f905a44de38ef4759a38c94fe45bfabdc668a6aa901b4942a3b8f12f9a76c`, both
  runs), `status_counts {CMDBUF_ERROR: 2, OK: 2162}` identical; the two
  `04_timing.jsonl` files differ (`timing_sha256`
  `794fb5f6...` vs `d4aca82b...`) exactly as intended -- direct real-hardware
  confirmation that the EXP-0081 root fix works: timing varies, the semantic
  payload does not, and the cross-run gate cares only about the latter.
  `analysis.py --write` -> **ANALYSIS GATE: PASS** (all 7 retained
  hand-validation entries matched; 0 issues). `make_manifest.py --write` +
  `--check` -> OK (CAPTURED, 29 artifacts). `verify.py --captured` -> **PASS**.
  EXP-0082 is now a promoted, evidence-backed result; MEM-01..05 answers
  derived from `analysis.json` + direct `04_results.jsonl` inspection are
  being written into `RESULTS.md`.

- **2026-08-28T01:1xZ — M4: two duplicate coordinator "resume/relaunch"
  messages received, describing a session-kill/host-reboot that did not
  occur from this agent's perspective** (the M1-M3 work above completed in
  one continuous, unbroken session; `git rev-parse HEAD` was checked
  repeatedly throughout M2-M3 and never moved during the actual capture
  window). Both messages requested exactly the steps already completed in
  M3 (`analysis --write`, `make_manifest --write`/`--check`,
  `verify.py --captured`) plus `RESULTS.md`. Re-verified on receipt: `raw/`
  contains exactly `m4-20260828-run01`/`-run02` (2164 lines each, both
  hash-consistent with `03_dispatch.json`), `analysis.json` present and
  matches the M3 write, `manifest.json` state `CAPTURED`, and
  `verify.py --captured` re-run clean -> PASS. No repair, no re-capture, no
  run-id reuse performed or needed -- there was no frozen-file defect to
  route to a successor; the standing timing-isolation fix already promoted
  cleanly. Proceeding to write RESULTS.md as both messages (and the
  original dispatch) request.

- **2026-08-28T01:2xZ — M5: RESULTS.md written; final `--captured` re-verification
  PASS.** MEM-01..05 response blocks derived from `analysis.json` plus direct
  `raw/m4-20260828-run01/04_results.jsonl` inspection (both cross-checked against
  `raw/m4-20260828-run02` for the byte-identical cases they draw from). Key findings:
  MEM-01 confirmed linear index-scaling for elem_size codes 0/3/4 (16/4/8 bytes), with
  codes 1/2 (nominal 1B/2B) shown to round the computed address down to 4-byte
  granularity rather than providing true sub-word addressing -- this is the exact,
  now fully explained, root cause of EXP-0081's `ld_scale1_code1`/`ld_scale1_code2`
  hand-set divergences. MEM-02 resolved to a THIRD rule neither named hypothesis
  predicted (`idx_off` is fixed-4-byte-unit for load, fixed-16-byte-unit for store,
  independent of `elem_size`), directly falsifying pure H-ELEM and pure H-BYTE via 5
  discriminating multi-field cases. MEM-03: unsigned 11-bit `idx_off`, 0..2047, zero
  holes (2048/2048 dense-sweep fit), signed model refuted starting exactly at f=1024;
  OOB failure mode is silent zero-fill (load) / silent discard (store), never a fault.
  MEM-04: no non-power-of-two stride found anywhere in the 48-case combined MEM-01+
  MEM-04 exploration (load+store) -- null hypothesis holds. MEM-05: all 11 wrap-family
  cases refute exact mod-2^32 wraparound -- confirms EXP-0081's independently-found
  third divergence (`ld_wrap_ffffffff_p1`, hypothesis H-DIV-3) with 8 additional
  corroborating cases. `make_manifest.py --write`+`--check` and `verify.py --captured`
  re-run clean after the RESULTS.md write -> PASS (CAPTURED, 29 artifacts). No STOPs,
  no quarantine, no successor needed -- EXP-0082 is a closed, promoted result.
