# EXP-0128 -- M4 generator envelope: closing EXP-0112's CANNOT-GENERATE list

**Question.** EXP-0112 (M4 program generator, 140/140 HW-VALIDATED) named
five things its generator could NOT synthesize: (a) load-direct-to-store,
(b) the extmode bridge for register R>=64, (c) `iadd2` REGISTER-mode
(only immediate/anchor form worked), (d) general control-flow synthesis
(one parameterized skeleton only), (e) `reg_move` (no validated GPR-to-GPR
move at all). This experiment takes each item and either CLOSES it
(extends generation, proven on real hardware against a host oracle) or
produces a precise, bounded NEGATIVE.

**Method.** OWN-SHADER differential compilation (compile our own small int-
arithmetic MSL kernels with `tools/shdump`, disassemble with
`tools/agx-isa`, correlate against the already-HW-VALIDATED
`device_load` extmode/2==register formula) to generate hypotheses, then
independent HW-PROBE construction (hand-assembled splice via
`tools/agxtest`, bypassing `device_load` entirely via `mov_imm`-seeded
GPRs) to decisively test them. See PROGRESS.md for the full pilot-phase
narrative (disclosed, not hidden, per this project's standing convention).

**Verdicts (full detail in RESULTS.md):**
- (c) iadd2 register-mode: **CLOSED** for a bounded, useful family
  (`d[dst] = r0 (+/-) r_N`, N=0..15, dst freely choosable including
  registers >>63) -- HW-VALIDATED, gated below. Chaining 2+ such
  instructions is a disclosed, bounded NEGATIVE (reproducibly zeroes).
- (a) load-direct-to-store: **CLOSED** for the `addr_mode=0x56`
  direct-forward mechanism (EXP-0090's own finding_3), GENERALIZED this
  experiment (independent load/store index-register addressing, chaining)
  -- HW-VALIDATED, gated below.
- (b) R>=64: **SYNTHESIZED from existing evidence** (db.json/EXP-0112/
  EXP-0113/EXP-0119) plus this experiment's own dst-side reinforcement --
  a hard restriction for the PACKED source-operand register field family
  (falu2/falu2i's srcA_reg/srcB_reg, and this experiment's own iadd2 srcB
  field), NOT a uniform hardware wall (iadd2's/falu3's dst/write side
  reaches further). See RESULTS.md.
- (d) control flow: displacement ARITHMETIC independently verified (no
  GPU); live HW validation CONFOUNDED and STOPPED for safety after 2 real
  (cleanly-recovered) hangs -- reported UNKNOWN, not falsified. CF's
  gated/validated envelope remains EXP-0112's own one-skeleton result.
- (e) reg_move: bounded NEGATIVE, synthesized from three prior experiments
  (EXP-0101, EXP-0090, EXP-0113) -- no new hardware experimentation.

**Gated corpus:** two families, IADD_REG (item c) and LOADSTORE_DIRECT
(item a), 39 cases total (33 `expect_match=True`, 6 `expect_match=False`
adversarial/boundary/positive-control), each an independently GENERATED
program (never a copied byte string), against a real host oracle.

## Reproduce

```sh
python3 -B verify.py --selftest          # no GPU
python3 -B verify.py --seqtest           # no GPU
python3 -B verify.py --preflight         # no GPU, before run01
python3 -B baseline.py                   # GPU: compile-only carrier check
python3 -B run.py --run-id m4-20260828-run01 --execute   # GPU
python3 -B verify.py --between-runs      # no GPU, before run02
python3 -B run.py --run-id m4-20260828-run02 --execute   # GPU
python3 -B verify.py --captured          # no GPU
```

## Clean-room provenance

```text
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: this experiment's own authored generator/harness code
  (isa_helpers.py/families.py/casematrix.py, every instruction built via
  tools/agx-isa's own READ-ONLY isadb.assemble()), our own carrier MSL
  (kernels/carrier_dag.metal -- copied verbatim from EXP-0112's own
  OWN-SHADER compile, cited), our own splice+run harness
  (harness/case_exec.py over tools/agxtest/agxtest.py, tools/shdump for
  carrier compilation). Pilot-phase differential-compilation recon
  (work/pilot/, not committed -- see PROGRESS.md) compiled our own small
  int-arithmetic MSL kernels only.
Apple binary introspection: NONE.
Reproduction: commands above.
Evidence: raw/m4-20260828-run01/, raw/m4-20260828-run02/, manifest.json,
  PROGRESS.md (disclosed pilot-phase narrative).
```
