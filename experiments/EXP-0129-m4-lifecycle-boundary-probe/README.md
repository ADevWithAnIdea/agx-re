# EXP-0126 -- M4 register-lifecycle boundary probe (H1/H2/H3 closure)

Closes the three remaining unknowns in the register-lifecycle arc
(`docs/isa/register-move-and-liveness.md`; EXP-0086, EXP-0089, EXP-0099,
EXP-0113, EXP-0119):

- **H1** -- do the `falu2`-family `srcA_reg_top`/`srcB_reg_top` bits
  (instruction bits 15/31) stay HW-tested inert for addressing and
  retention under axes EXP-0119 did not reach: a real loop+if/else
  control-flow boundary, a `device_load`-sourced operand, half (b16)
  width, and ~40-register pressure pushing the highest live index near
  EXP-0112's own 64-register-alias boundary?
- **H2** -- is the literal-bit-17-position "release" mechanism ONE thing
  whose visible signature depends on instruction structure, or SEVERAL
  genuinely unrelated mechanisms that happen to share a bit position?
  Built a genuinely discriminating test (not more instances) targeting
  `ibitcount`, the family EXP-0119 found causally INERT to its own
  `cache` bit.
- **H3** -- root-cause the EXP-0119-vs-EXP-M4-14 `ibitcount` contradiction
  (A18 record: cache-bit-clear breaks the result; EXP-0119's M4
  reproduction of the SAME literal bytes: no effect) by varying dispatch
  shape and operand provenance one axis at a time, entirely on M4.

**Method:** MODE A (hand-assembled AGX programs via `tools/agx-isa`'s
`isadb.assemble()`, spliced whole into a carrier kernel's `_agc.main`) for
H1/H2/most of H3; MODE B (a field-level splice into a real compiled
kernel at a symbol-relative offset -- EXP-M4-14's own literal anchor
bytes) for H3's dispatch-shape replication. `carrier_dag.metal` and
`carrier_cf.metal` are reused verbatim from EXP-0112 (both independently
re-confirmed fresh by `baseline.py` before every capture); `iunary_popcount.metal`
is reused verbatim from EXP-M4-14's own corpus.

**Headline results (full detail: RESULTS.md):**

- **H1: CONFIRMED inert** for addressing and retention across all four
  reached axes (control-flow boundary, load-sourced operand, ~40-register
  pressure, and -- with a disclosed construction anomaly -- half width).
  Fragment stage was attempted and is **NOT REACHED** (a located
  compiler-emitted instruction could not be confirmed live on the
  rendered-pixel path within budget); uniform-register operand class
  remains untested project-wide (no validated construction exists).
- **H2: ONE underlying release-concept, relocated per family** -- a
  genuinely new finding. `ibitcount` DOES have a real, working,
  bidirectional release-control bit; it is just NOT at the literal
  bit-17 (`cache`) position EXP-0119 tested. It is `srcdesc` bit4 (byte6
  bit4). With `srcdesc` bit4 cleared, `ibitcount`'s later-read is
  RETAINED (not unconditionally corrupted); `cache`/bit17 stays
  independently inert regardless. A fresh rewrite restores access
  (matching falu2's per-write-instance-suppression signature); the
  corruption is distance-invariant (matching falu2's CandB finding).
- **H3: operand provenance, not dispatch shape, is the deciding axis.**
  EXP-M4-14's own literal bytes break at BOTH grid=1 and grid=4 on a
  fresh M4 compile (ruling out dispatch shape); a MODE A hand-built
  device_load-sourced construction breaks AT GRID=1 (matching EXP-0119's
  own single-lane shape exactly), while the ALU-seeded construction
  (EXP-0119's own) never breaks at either grid size. Both the A18 record
  and EXP-0119's M4 record are correct for their own construction's
  context -- candidate (iii), not (i) or (ii).

## Layout

```
PRE_REGISTRATION.md   frozen hypotheses/falsifiers, pilot-phase findings that shaped them
CAPTURE_CONTRACT.json machine-readable freeze: hashes, schema, gate classes, timeouts
isa_helpers.py         instruction-construction helpers (isadb.assemble() wrappers),
                       incl. build_cf_topbit_program (EXP-0112/EXP-0090's CF skeleton,
                       parameterized) and device_load_fixed (EXP-0101's corrected formula)
casematrix.py           the frozen 58-case matrix (H1_CF/LOAD/HALFWIDTH/PRESSURE,
                       H2_BYTESWEEP/INTERACTION/LATERWRITE/DISTANCE, H3_MODEB/MODEA)
run.py / verify.py      capture runner + fail-closed gate verifier (selftest/seqtest/
                       preflight/between-runs/captured)
baseline.py             fresh re-derivation of every carrier kernel's own compiled facts
harness/case_exec.py    per-case executor (splice-and-run via tools/agxtest/agxtest.py)
harness/fsrun.m         fragment-stage render+splice tool (adapted from EXP-0111/0091,
                       clean-room /tmp fix) -- NOT exercised by any frozen case (H1
                       fragment axis not reached, see PRE_REGISTRATION.md pilot note 1)
kernels/                carrier.metal, carrier_dag.metal, carrier_cf.metal (all reused
                       verbatim from EXP-0119/EXP-0112), iunary_popcount.metal (verbatim
                       from EXP-M4-14), fs_adjacent.metal (authored, unused by the frozen
                       matrix -- see above)
raw/                    two independent gated captures
```

## Reproduce

```sh
cd experiments/EXP-0126-m4-lifecycle-boundary-probe
python3 -B verify.py --selftest
python3 -B verify.py --seqtest
python3 -B verify.py --preflight
python3 -B baseline.py                                  # GPU-adjacent: compile-only
python3 -B run.py --run-id m4-20260828-run01 --execute   # real GPU, append-only
python3 -B verify.py --between-runs
python3 -B run.py --run-id m4-20260828-run02 --execute
python3 -B verify.py --captured
python3 -B analysis.py --write
```

## Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE + PUBLIC
Inputs inspected: kernels/carrier.metal (EXP-0119, our own MSL), kernels/carrier_dag.metal
  + kernels/carrier_cf.metal (EXP-0112, our own MSL), kernels/iunary_popcount.metal
  (EXP-M4-14's own corpus/halfint/iunary.metal, our own MSL), kernels/fs_adjacent.metal
  (authored here, our own MSL, NOT exercised by the frozen matrix), tools/agx-isa's
  isadb.assemble()/disassemble()/decode_one()/imm_encode()/imm_decode() (read-only),
  tools/agxtest (read-only, splice-and-run), tools/shdump (read-only, compile+extract).
  db.json's own field/match tables were READ (to locate genuinely-free bit positions,
  e.g. ibitcount's non-match-forced op_enable/srcdesc/tail bits) but never modified.
  Every byte executed on hardware was independently constructed via isadb.assemble()
  (MODE A) or is EXP-M4-14's own recorded literal anchor bytes, spliced at a
  symbol-relative offset (MODE B) -- never hand-copied from a captured Apple template.
Apple binary introspection: NONE.
Reproduction: see above.
Evidence: raw/m4-20260828-run01/, raw/m4-20260828-run02/, both byte-identical
  01_results.jsonl (see RESULTS.md for the hash), analysis.json, manifest.json.
```
