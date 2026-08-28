# PROGRESS — EXP-0112 M4 program generator

Timestamped milestone log. Append-only; never edited retroactively except to
fix a typo. Written incrementally so a kill/wedge costs at most one milestone.

## Milestone 0 — 2026-08-28T07:13Z — setup

- Read CLAUDE.md, CODEX.md, experiments/SUBAGENT_BRIEF.md.
- Read foundation docs: EXP-0101 RESULTS.md (load-to-ALU bridge SOLVED, the
  extmode=2*R / dst_lo,dst_ext9 verbatim / falu2i mods=0xC0 rule), EXP-0090
  RESULTS.md (4 hand-built programs, P4 negative result, per-family verdict
  table), docs/isa/register-move-and-liveness.md (liveness bit contract,
  silent-zero failure mode, opflags=3 for falu2 both-real), EXP-0102
  (INT/PACK semantics), EXP-0104 (CF/SIMD -- P3-style CF skeleton scope),
  EXP-0082 (memory operand address formulas, MEM-01..05).
- Inspected tools/agx-isa/db.json field widths for falu2/falu2i/device_load/
  device_store/iadd2/icmp_pred/if_push/jump/jump_cond/pop_reconverge/isel10/
  get_sr/mov_imm/reg_move_c1/stop -- confirms falu2/falu2i `dst` is a HARD
  4-bit nibble (r0-r15), srcA_reg/srcB_reg are 7-bit fields (EXP-0099: only
  6 bits load-bearing, top bit inert in ONE tested context -- register
  literal-index, not the load-bridge extmode context).
- Inspected EXP-0101 isa_helpers.py (device_load_fixed, falu2_raw/falu2i_raw
  builders) and EXP-0090 isa_helpers.py/programs.py (iadd2 verbatim anchor,
  P3 control-flow skeleton, register-pressure/move lessons from P4's
  failure). These are the two direct ancestors this experiment builds on.
- Received coordinator scope reinforcement: for every field the generator
  touches, construct values at min/max/first-invalid/holes, both positive
  and negative results, not just replay compiler-observed values. Folding
  in a dedicated REGBOUNDARY sweep (extmode load-bridge target register,
  0..127, crossing the EXP-0099-adjacent 64 boundary) as a first-class
  corpus family, not an afterthought.

## Milestone 1 — generator design frozen (see PRE_REGISTRATION.md)

Design decisions (rationale in PRE_REGISTRATION.md):
- Register plan: POOL = r0..r13 (14 registers) for DAG value nodes,
  R_UNWRITTEN=14, R_IDX=15 (mov_imm'd to 0, EXP-0082/0031 convention).
- 3-pass generator: (1) structure (types/operands/consumer-budgets, greedy
  live-count cap at POOL_SIZE=14, deterministic, no backtracking), (2)
  linear-scan register allocation with reuse (free-list, smallest-first),
  (3) instruction emission (isa_helpers builders) + host oracle (exact
  float32 arithmetic matching isadb's own minifloat/address-formula
  codecs).
- Consumption discipline (liveness safety): a node's consumers are either
  (a) 1+ falu2i/falu2-srcA "A-reads" (multi-read liveness bit0 tracked,
  last one True) and NOTHING else, or (b) exactly one falu2-srcB "B-read"
  (untouched node only, closes immediately, no bit), or (c) exactly one
  device_store leaf-read (untouched node only, closes immediately, no
  bit). Mixed A+B or A+store on the same node is explicitly OUT of this
  generator's synthesis envelope (never independently validated) --
  documented as a known unexplored combination, not silently assumed safe.
- Families: MAIN_DAG (random DAG, register reuse exercised once node count
  exceeds 14), REGBOUNDARY (systematic extmode-target sweep for the
  EXP-0101 load bridge, 0..127 crossing the top-bit boundary, own family
  per the coordinator's reinforcement), IADD_ANCHOR (EXP-0090's verbatim
  device_load->iadd2->device_store anchor, srcB_imm swept incl. the
  128-wraps-to-0 encoding boundary), CF (EXP-0090 P3 skeleton reused
  verbatim, loop trip count / branch selector / cond field varied),
  ADVERSARIAL (deliberate rule violations: expect_match=False, proves the
  harness/oracle detects known failure modes -- mirrors EXP-0101's
  positive-control convention).

## Milestone 2 -- 2026-08-28T07:20Z-07:48Z -- pilot-phase debugging (informal, no GPU gate)

Wrote generator.py/isa_helpers.py/families.py/cf.py/casematrix.py/
kernels/carrier_dag.metal/kernels/carrier_cf.metal/harness/case_exec.py/
baseline.py/run.py/verify.py. Compiled+disassembled both carriers
(CARRIER_LEN=1590 actual/1536 used for dag, 152 for cf; base_slot mapping
re-derived fresh, never assumed). Ran an informal 161-case dry sweep on
real M4 hardware (not gated, not committed as evidence) and found + fixed:

1. **Generator bug**: a `load` DAG node stored directly (no ALU consumer)
   used the EXP-0101 ALU-bridge shape for a bare device_store, which was
   never validated for that path -- ~50% of a small MAIN_DAG sample failed
   (all 3 stores in one case read the SAME stale first value). Root cause:
   conflated EXP-0101's extmode bridge (validated for falu2/falu2i
   consumption only) with EXP-0090's structurally different addr_mode=0x56
   load->store direct-forward mechanism. Fixed: every `load` node now
   always gets a trivial +0.0 finalizer A-read before storage. Re-ran:
   100/100 MAIN_DAG cases pass.
2. **Allocator headroom bug**: live-count cap used the full POOL_SIZE=14,
   leaving no slack for the finalization pass to bootstrap a free register.
   Fixed: EFFECTIVE_CAP=POOL_SIZE-2. Verified 0 violations across a wide
   (seed, n_nodes) sweep.
3. **CF base_slot bug**: derived carrier_cf.metal's base_slot mapping from
   a SEPARATE, simpler probe kernel instead of the carrier itself -- got it
   backwards. 5 repeats of one case: 4x a stable wrong value (67108864.0 =
   2^26, consistent with a garbage huge loop trip count saturating float32
   accumulation), 1x CMDBUF_ERROR. Fixed by disassembling carrier_cf.metal's
   own compile directly (base_slot=2 for 'a', =1 for 'n', matching
   EXP-0090's carrier_p3.metal exactly). baseline.py now asserts base_slot
   ORDER (first load / second load), not just the unordered set, to catch
   this bug class before any GPU dispatch. Re-ran: 12/12 CF cases pass.
4. **REGBOUNDARY finding (real, not a bug)**: R<64 all pass (dense 15-point
   sweep, extends EXP-0101's own {0,3,7,16,20} spot-check); R in [64,112]
   silently aliases to r(R mod 64) (confirmed via 4 poison-register
   controls: poisoning r(R mod 64) with 30.0 makes the output read back
   30.0, not 0.0 or the loaded value); R in {126,127} FAULTS the command
   buffer (CMDBUF_ERROR) -- a second, different failure mode at the top of
   the 7-bit range. expect_match updated to reflect this pilot finding.
5. **Carrier-dependent opflags discrepancy (real, not a bug, NOT fixed)**:
   a decisive 8-run sweep (opflags in {0,1,2,3}, two operand-production
   shapes) on kernels/carrier_dag.metal found opflags has NO effect at all
   -- every combination gives the correct sum, contradicting EXP-0090's own
   finding_1 (opflags=2 silently zeroes srcB) established on a DIFFERENT
   carrier (carrier_p1.metal). Labelled and gated as its own case
   (`adv_opflags1_bothreal_carrier_dependent`, expect_match=True, matching
   this carrier's actual behavior), full detail in PRE_REGISTRATION.md SS5
   item 4 and RESULTS.md.

Full 161/161 pilot re-run after all fixes: 0 unexpected results (every
case's actual match matches its now-refined expect_match prediction).
PRE_REGISTRATION.md + CAPTURE_CONTRACT.json written and frozen against this
code state (SHA-256 hashes recorded there). Next: standing gates, then the
two contracted capture runs.

## Milestone 3 -- 2026-08-28T07:52Z-08:10Z -- gated capture, both runs, CLOSED

- `verify.py --selftest` (986 checks), `--seqtest` (PRE_GPU), `--preflight`,
  `make_manifest.py --check`: all PASS before run01.
- `run.py --run-id m4-20260828-run01 --execute`: 161 cases, 140 matched,
  21 mismatched -- EXACTLY the pilot-phase prediction, 0 surprises.
- `verify.py --seqtest` (RUN01_PRESENT) + `--between-runs`: PASS.
- `run.py --run-id m4-20260828-run02 --execute`: 161 cases, 140 matched,
  21 mismatched -- identical counts to run01.
- `verify.py --captured`: PASS -- `01_results.jsonl` byte-identical across
  both runs (sha256 `568afb98c1...`), 0 unexpected deviations in either
  run.
- `make_manifest.py --write`: manifest.json written (16 authored files +
  both raw/ trees hashed).
- `analysis/summarize.py`: pass-rate/failure-taxonomy summary written to
  `analysis/summary.json` -- 140/140 (100%) of `expect_match=True`,
  21/21 (100%) of `expect_match=False` as predicted, 0/161 unexpected.
- RESULTS.md written: headline verdict, per-family breakdown, the
  REGBOUNDARY decisive finding (R<64 correct / R in [64,112] aliases to
  r(R mod 64), confirmed by poison controls / R in {126,127} faults), the
  carrier-dependent `opflags` discrepancy (disclosed, not resolved), the
  full generation envelope (CAN/CANNOT lists), and the DRV-ISA-01
  statement.
- No STOPs, no timeouts, no host wedge, `macvdmtool` never invoked, A18 Pro
  never touched. **Experiment CLOSED.**
