# EXP-0076 progress log (append-only)

Operational note recorded at open (2026-08-27): per coordinator direction the
A18 Pro (192.168.170.254) is **hands-off** — no SSH, no probing, no reference —
and `macvdmtool` is never to be run against any target. All work for this
experiment is **local M4 only**, through the public Metal API. No cross-target
inference will be drawn. If the host itself wedges: STOP, mark BLOCKED, wait
for manual reboot; never attempt any tool-based recovery.

## 2026-08-27T23:05:00+00:00 — open

- Milestone: experiment opened as the successor of the superseded scaffold
  `../EXP-0068-m4-robustness-contract` (see its `SUPERSEDED.md`: gate scaffold
  only, nothing captured, binds nothing). Question cluster: Part-II items
  **MEM-06, MEM-07, MEM-08, MEM-09, MEM-10** (+ MEM-11-adjacent observations,
  MEM-12-input) of `APPLE9_RE_IMPLEMENTATION_GAPS.md`, per the user-directed
  load/store/SSBO priority. Scope frozen by the dispatch: public-Metal
  owned-buffer BEHAVIORAL evidence on the local M4 — no native-encoding, no
  ISA-field, no Linux, no A18 claims.
- Frozen design summary (to be fully specified in PRE_REGISTRATION.md before
  any build):
  - One 64-byte owned `MTLBuffer` per case (exact length, no slack), CPU-filled
    with the frozen positional pattern `F(i) = (0xA5 + 0x1B*i) mod 256`;
    256-byte guard allocations before (0x5A) and after (0xC3), checked after
    every case; result buffer with 0x5A/0xA5 guards around a 32-byte zeroed
    payload.
  - Widths 8/16/32/64/128-bit via frozen per-class MSL pointer idioms
    (`*(device uint *)p` etc.); offset classes: aligned in-bounds (32),
    misaligned by 1 (33), misaligned by width/2-1 where different (35/64-bit,
    39/128-bit), last full element (64-W), first fully out-of-allocation
    element (64), far (+1 KiB, 1088), and boundary-straddling (start in-bounds,
    cross the end by 1..W-1 bytes). Loads and stores as separate cases; a
    2-case 32-bit atomic-exchange stretch (in-bounds control + one OOB),
    probed only in its own cases.
  - 106 frozen cases per run, one case per fresh harness process, per-case
    hard timeout 120 s (in-process watchdogs 120 s compile / 100 s dispatch;
    subprocess timeout as the outer belt). A faulted/killed case is recorded
    as a result and never retried in place.
- Process pattern adopted from EXP-0074 (single authoritative record schema,
  single shared key-set constants imported by the verifier from the runner,
  --selftest pre-capture proof, non-recorded smoke gate, two byte-comparable
  capture runs, fail-closed verify, deterministic analysis, manifest) with one
  EXP-0075 refinement: env/build/smoke failures happen BEFORE the append-only
  raw tree is created (STOP retained under work/), so a pre-capture defect
  does not burn the run number.
- Pre-registered deviation from EXP-0074's global byte-exact-repeat gate,
  frozen here before any build: out-of-allocation behavior is exactly the
  unknown under test and may legitimately be nondeterministic, so the two
  capture runs are required to be byte-identical for every IN-BOUNDS case
  (classes align_in, mis1, mishalf, last) and status-identical for every case;
  per-case byte-identity of out-of-allocation/straddle/atomic observations is
  REPORTED as an observed determinism result, not gate-required. A
  nondeterministic OOB read is a first-class answer to MEM-08, not a
  quarantine.
- Files written: `kernels/`, `harness/` (empty dirs), this file.
- Exact next action: author `kernels/robustness_matrix.metal` and
  `harness/probe.m`, then `run.py` (with the single-source frozen matrix),
  `analysis.py`, `verify.py`, `make_manifest.py`; scratch link-check the
  harness (no Metal); then freeze `PRE_REGISTRATION.md` +
  `CAPTURE_CONTRACT.json` with freshly derived hashes.

## 2026-08-27T23:35:00+00:00 — contract frozen; self-test 25/25; preflight PASS

- Milestone: all authored blobs final and hash-frozen in `CAPTURE_CONTRACT.json`
  (8 blobs: PRE_REGISTRATION.md, README.md, kernels/robustness_matrix.metal,
  harness/probe.m, run.py, analysis.py, make_manifest.py, verify.py). Contract
  state `PRE_GPU`. No Metal compilation or execution has occurred for EXP-0076
  (the only host-side build was a throwaway `clang` link check in a scratch
  dir, since deleted; its only execution was argv-less, exiting 2 before any
  Metal call).
- `verify.py --selftest` passes **25/25** with no Metal, no device, no Apple
  binary: preflight/captured/between-runs gates each proven SATISFIABLE on a
  clean synthetic two-run capture built through `run.case_line` (the real
  record builder), and 16 broken shapes each fail for the right reason —
  over/under-keyed case line, bad status enum, malformed hex, broken
  in-bounds byte-exact repeat, cross-run status difference (with the receipt
  kept coupled so the failure surfaces at the cross-run gate), tampered matrix
  echo, wrong dispatch counts, mismatched results hash, missing/over-keyed
  receipt line, stray raw file, authored-hash drift, stale manifest,
  cross-run revision difference. Six smoke-validator purity checks prove the
  pre-capture smoke gate passes a clean record and rejects the EXP-0072
  truncation class, over-keyed payloads, wrong identity, nonzero exit, and
  false integrity flags. One deliberately positive case proves a
  guard-corrupting OOB-store observation (`store_w32_oob1` with `g1_ok=false`)
  is VALID evidence — guard flags are results here, not gate conditions.
- The self-test caught two real pre-capture inconsistencies before any GPU
  work (a contract/verifier gate-text mismatch and a synthetic-receipt argv
  mismatch), both fixed before freeze — the gates are load-bearing.
- Contract frozen content: 106-case matrix (52 load + 52 store + 2 atomic
  stretch; widths 8/16/32/64/128 bits; offset classes align_in/mis1/mishalf/
  last/oob1/far/straddle_1..15), 64-byte exact allocation with fill
  `F(i)=(0xA5+0x1B*i) mod 256`, store pattern `S(j)=(0xC7+j) mod 256`, guard
  allocations 256 B `0x5A`/`0xC3`, per-case process with 120 s hard timeout,
  in-bounds-only byte-exact cross-run gate (frozen deviation, justified in the
  preregistration: OOB nondeterminism is an observation, not a quarantine).
- Files written: everything except `raw/` (no raw tree exists; preflight
  verified PRE_GPU).
- Exact next action: `python3 -B run.py --execute --run-id m4-20260827-run01`
  (the runner re-runs --selftest and --preflight itself, then the non-recorded
  smoke gate, then captures the 106 cases one process each), then
  `python3 -B verify.py --between-runs`.

## 2026-08-27T23:47:00+00:00 — first run01 attempt: pre-capture smoke STOP (harness JSON quoting defect); repaired pre-capture

- The first `run.py --execute --run-id m4-20260827-run01` attempt stopped at the
  pre-capture smoke gate, exactly as designed: `raw/` was never created; the
  failure record is retained at `work/m4-20260827-run01/{STOP.json,smoke/smoke.json}`.
- Defect: the harness printed the `obs` hex field WITHOUT JSON string quotes
  (`"obs":05203b56`), so the (otherwise complete and correct) 563-byte record
  did not parse as one JSON object. One-line fix in `harness/probe.m`
  (quote the hex_out payload). This repair class is pre-capture authorized:
  nothing was captured, the matrix and all expectations are unchanged, and no
  hardware observation influenced any frozen decision. For full disclosure:
  the smoke dispatch did run one real GPU case (the in-bounds aligned control
  `load_w32_align_in`) and returned `obs` `05203b56` — which happens to equal
  the frozen fill expectation for bytes 32..36 — during this diagnosis. The
  smoke gate itself checked shape only, and the capture re-observes this case
  like every other; no frozen parameter was touched after seeing it.
- Post-repair freeze refreshed: harness hash updated in PRE_REGISTRATION.md
  and CAPTURE_CONTRACT.json; manifest regenerated; selftest 25/25 and
  preflight re-verified before the next capture attempt.
- Exact next action: delete the retained `work/` stop tree (it is the recorded
  failure evidence; its content is duplicated in this entry and the raw STOP
  is preserved verbatim below), then relaunch run01.
  STOP.json verbatim: {"schema":1,"phase":"pre_capture_smoke","case":"load_w32_align_in",
  "problems":["smoke stdout is not exactly one JSON object (563 bytes)"],
  "automatic_retry":false,"raw_created":false}

## 2026-08-28T00:20:00+00:00 — both captures written; every gate green

- Milestone: capture complete and verified end to end on the second attempt
  (the first stopped pre-capture at the smoke gate; see the 23:47Z entry).
  No STOP, no fault, no timeout, no watchdog, no command-buffer error, no
  guard mutation in either run.
  - run 01: 106/106 cases, all `ok`; smoke gate passed pre-capture.
  - `verify.py --between-runs` PASS after `make_manifest.py --write`.
  - run 02: 106/106 cases, all `ok`; provenance matched run 01 exactly
    (same revision `203c3138ab88...`, same authored hashes).
  - `raw/*/04_results.jsonl` are **byte-identical** (`cmp` clean) — every
    observation, including all out-of-allocation values, is deterministic
    across the two runs.
  - `analysis.py --run-a ... --run-b ... --write` exit 0 (in-bounds repeat
    gate green); `make_manifest.py --write`; `verify.py --captured` PASS;
    `make_manifest.py --check` PASS.
- OBSERVED RESULT (headline): no fault anywhere in the matrix (incl. +1 KiB
  OOB accesses and an OOB atomic exchange); OOB reads all-zero at every
  tested width/offset (10/10); OOB stores fully discarded (10/10); unaligned
  in-bounds accesses never fault and never corrupt neighbors but access the
  address **rounded down per access unit** (8/16-bit one unit; 64-bit two
  32-bit units; 128-bit four 32-bit units, each rounded down to 4) — all 6
  misaligned loads and all straddling reads diverge from the requested-byte
  models for exactly this reason. One unified model predicts 108/108
  load-side and 108/108 store-side observations across both runs (0
  exceptions).
- Harness store-value word-packing slip discovered post-capture (uploaded
  words' LE image is `ca c9 c8 c7..` instead of the intended `c7 c8 c9 ca..`);
  the hardware wrote exactly the words supplied (proven byte-for-byte), so
  no conclusion is affected; recorded as an erratum in RESULTS.md.
- Files written: `raw/m4-20260827-run01/{00..06}`, `raw/m4-20260827-run02/{00..06}`,
  `analysis.json`, `RESULTS.md` (final, with per-question response blocks for
  MEM-06..MEM-10 + MEM-11-adjacent/MEM-12-input).
- Exact next action: regenerate the manifest over the final tree and re-run
  `verify.py --captured`, `make_manifest.py --check`, and `verify.py
  --selftest` so the last word on disk is a passing gate over the exact
  final bytes.

## 2026-08-28T00:35:00+00:00 — experiment complete; final gates green over exact final bytes

- Milestone: EXP-0076 complete. The manifest was regenerated over the final
  tree and all gates re-run and passed on those exact bytes:
  `verify.py --captured` PASS, `make_manifest.py --check` PASS (CAPTURED),
  `verify.py --selftest` 25/25 PASS, `analysis.py` deterministic (re-run
  reproduces `analysis.json` byte-exactly). Raw trees untouched since
  capture; 34 artifacts hashed, no symlinks, no binaries, no `work/` or
  `selftest/` scratch left behind.
- Nothing outside `experiments/EXP-0076-m4-buffer-robustness-matrix/` was
  created or modified by this experiment; no `git commit` was made (the
  orchestrator commits). No Apple binary, archive, BO, command stream, or
  compiled-shader byte was inspected at any point; no remote target was
  contacted; no `macvdmtool` was run.
- Verdicts recorded in RESULTS.md: MEM-06 = No (unaligned loads work but
  access the aligned-down window; no fault); MEM-07 = Yes (no adjacent-byte
  corruption; aligned-down addressing; value bits written exactly);
  MEM-08 = Yes (OOB reads zero at every tested width/offset, deterministic);
  MEM-09 = No (mix model refuted; per-unit aligned-down reads with zero
  fully-OOB units); MEM-10 = Yes (OOB stores discarded, guards intact);
  MEM-11 closed nothing (adjacent observations recorded); MEM-12 synthesis
  constraints recorded.
- Exact next action: none for this experiment. Recommended successors: (1)
  MEM-12 synthesis rules written from this data (byte-address clamping
  before unit decomposition); (2) a variant matrix at other allocation
  sizes (e.g. 256 B / 4 KiB / non-power-of-two) and larger OOB distances to
  bound the zero-fill/discard region; (3) a corrected store-value packing
  re-run if the literal `c7..` byte-order confirmation is wanted; (4)
  64-bit atomic and vector-atomic stretch; (5) the same matrix through a
  vertex/fragment stage. A18 replication is out of scope while the A18 is
  hands-off.
