# EXP-0139 PROGRESS (append-only; timestamped per milestone)

## M0 — 2026-08-28 — orientation
Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
`experiments/FIELD-SWEEP-PROTOCOL.md`, `docs/evidence-classification.md`.
Extracted the blocking-field list for the 16 integer-ALU mnemonics from
`tools/agx-isa/validation.json` vs `db.json`: **137 blocking fields confirmed**
(iadd2 12, ibfe 16, ibfe_mesh_attr 3, ibfins 12, ibitcount 1, icmp_pred 6,
icmpsel 12, imad 15, iminmax 6, isel10 10, isel10_c 10, isel8 8, isel_reg 9,
isel_reg8 7, ishift 9, iunary 1).
Read the load-bearing prior results: EXP-0128 (iadd2 register mode), EXP-0102
(`extract_bits` three-way contract), EXP-0129 (`ibitcount` srcdesc bit4),
EXP-0113 (`iminmax` nondeterminism), EXP-0112 (register aliasing, mov_imm 4-bit
dst), EXP-M4-14 (ibitcount splice sweep).

## M1 — 2026-08-28 — pilot: tooling + carriers  (DISCLOSED, NON-GATED)
`work/pilot/` (retained). Built `work/bin/{shdump,agxrun_persist,agxrun}` from
the unmodified repo tool sources.
- `p1_smoke.py`: reproduced EXP-0128's `iadd2` register-mode rule on a
  SYNTHESIZED program (N=2/7/0, dst=5/40/6 -> 30/77/42) and got a clean
  synthesized `ibitcount` popcount (85->4, 127->7, 1->1). **`db.json`'s
  `mov_imm` descriptor has since been renamed `imm8` -> `imm7`+`imm_top`
  (EXP-0128's own finding landing in the DB); EXP-0128's copy of
  `isa_helpers.mov_imm` therefore no longer assembles. Fixed in this
  experiment's own copy, documented at the call site.**
- `p2/p4/p6_recon*.py`: compiled 30 authored MSL probe kernels and tokenized
  each `_agc.main` with `tools/agx-isa`. Located live anchors for **13 of the
  16** target mnemonics. NO anchor anywhere in our own compiled corpus for
  `ibfe_mesh_attr` (fragment/mesh-stage only), `isel_reg8`, `iunary`.
- `p7_time.py`: throughput on the persistent runner measured at **~0.7 ms per
  dispatch** for these small carriers -> a full dense sweep is affordable.
- `p8_iunary.py`: **found live `iunary`-tokenizing members** by construction
  (byte0=0x27, byte+1=0x2d/0x35/0x3d, byte+2 anything but 0x54/0x56 -> the
  tighter `ibitcount` match loses). They still compute popcount and their
  operand bytes are LIVE, so `iunary.operand` is sweepable after all.

## M2 — 2026-08-28 — harness frozen
`harness/{sweeprun,anchors,casematrix,run,verify}.py`, `kernels/ialu_probes.metal`,
`kernels/carrier_dag.metal`. `verify.py --selftest` = 457 checks PASS with no
device. Case matrix: **29,685 cases**, matrix_sha256 recorded in
`CAPTURE_CONTRACT.json`. 40-case smoke run confirmed real dispatch (the `dst`
relocation model flips exactly at dst=12/13 = r6) and was then deleted as
pre-freeze pilot output.

## M3 — 2026-08-28T09:39:08Z — PRE_REGISTRATION.md + CAPTURE_CONTRACT.json FROZEN
sha256 PRE_REGISTRATION.md = be3a1b0b7ccf96407b53a12fd02e6ac7f79c95c3ce2f69f163caf2db462a1fb5
sha256 CAPTURE_CONTRACT.json = 6449e6d859f84639ed06b15050c95f1ba121302f647f388441e7a8efd3e27511
matrix_sha256 = 8bb3683479d3fa1540725406a2e321db7bbdccc9428ea696f7f3b16c0f19fdd5 (29,685 cases)
Starting gated run01.

## M4 — 2026-08-28 — gated run01 COMPLETE (original contract)
`raw/m4_20260828_run01/`: **29,685 / 29,685 cases**, 340.8 s, **0 hangs**,
matrix_sha256 matches the frozen contract. Status split: 28,554 OK /
1,131 CMDBUF_ERROR (rep 1) and 28,612 OK / 1,073 CMDBUF_ERROR (rep 2);
**596 cases disagreed between their two in-run repeats**.

## M5 — 2026-08-28T10:55:11Z — CONTRACT AMENDMENT 01 (disclosed)
`FIELD-SWEEP-PROTOCOL.md` gained a binding §7 (*concurrent sweeps contaminate
each other*) after this contract was frozen and after run01 finished. Amended
the harness to record the OS fault-classification string, re-validate the
unmutated baseline every 250 cases with a runner restart on failure, and added
`harness/revalidate.py` (a third pass that re-runs every non-OK case 5× in a
fresh process with bracketing baseline checks). **The case matrix is
byte-identical**, so `matrix_sha256` is unchanged and run01/run02 stay
comparable. run01 is retained exactly as captured; its faults are covered by
the revalidate pass. Concurrent GPU experiments this batch: **EXP-0141 (MEM)**
and **EXP-0146 (integer misc)**; EXP-0148 is desk work and does not contend.
The 596 rep-disagreements in run01 are now expected to be largely sibling
contamination rather than field properties — the revalidate pass decides.

## M6 — 2026-08-28 — gated run02 COMPLETE (amendment-01 instrumentation)
`raw/m4_20260828_run02/`: 29,685/29,685 cases, 284.9 s, **0 hangs**, matrix_sha256 identical
to run01. Periodic baseline re-validation fired for two arms — **both false alarms that the
mechanism correctly surfaced**: `ISEL_REG8`'s baseline is an *extrapolated* construction
pre-registered `mismatch`, and `ICMPSEL` was being fed the integer input vector while its host
oracle used the float vector (a harness defect, recorded as `db_defects` DEF-0139-6; the
captured bytes are exactly `(a<b)?1:0` over the integer vector reinterpreted as float32 with
denormals flushed, so the arm's observations are sound). **No GPU error cascade occurred.**

## M7 — 2026-08-28 — fault re-validation passes
`reval01` (every non-OK case, 5× in a fresh process, baseline before/after): 1,580 cases,
7,900 attempts → 811 reproducible_fault, **692 transient (did not reproduce at all)**, 66
intermittent, 11 baseline-unhealthy. **1,552 attempts carried the OS's own
`kIOGPUCommandBufferCallbackErrorInnocentVictim` string.**
`reval02` (every OK-but-unstable case, 7×): 457 cases, 3,199 attempts → 388 transient, 52
intermittent, 14 baseline-unhealthy, **only 3 genuinely nondeterministic**.
**Without FIELD-SWEEP-PROTOCOL §7, 692 legal field values would have been labelled `fault`.**

## M8 — 2026-08-28 — analysis, verdicts, write-up
`analysis/verdicts.py` + `analysis/emit_verdicts.py` → `analysis/field_verdicts.json`
(153 field verdicts + `db_defects` + emittability roll-up), `analysis/field_stats.json`.
Three host-side oracle EXPRESSIONS corrected in analysis, each disclosed with the competing
model scored on the same data; raw captures untouched. One pre-registered model REFUTED
(`ibfe.width` is mod-32, not literal-clamp).
**Headline: 73 of 137 blocking fields reached emitter grade (39 hardware-run, 34
isolated-byte-diff); 64 still blocked, 44 of them operand/condition selectors.
`ibitcount` and `iunary` are now EMITTABLE.** 129,839 GPU dispatches, 0 hangs, 0 reboots.
`README.md`, `RESULTS.md`, `manifest.json` written. NOT committed (orchestrator owns commits).
