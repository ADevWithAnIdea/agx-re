# PRE_REGISTRATION -- EXP-0128 M4 generator envelope

Frozen 2026-08-28, before either contracted capture run, AFTER a disclosed
pre-freeze pilot phase (`work/pilot/`, not committed, see PROGRESS.md
Milestones 1-4) that decoded the `iadd2` register-mode encoding, the
`addr_mode=0x56` load-direct-store generalization, and found/fixed a real
bug (`mov_imm`'s `imm8` field is only 7 bits load-bearing, not 8 -- values
>=128 silently zero and, combined with `iadd2`'s N=0 self-read encoding,
were observed to HANG the command buffer twice). This mirrors this
project's own standing convention (e.g. EXP-0101/EXP-0112's own "one
informal pilot-verification run" pattern) -- the pilot's own findings,
including its two hangs and the one refuted adversarial hypothesis, are
disclosed in PROGRESS.md and RESULTS.md, not hidden.

## 1. Question

EXP-0112's own RESULTS.md SS4 named five things its generator could not
yet synthesize (`APPLE9_RE_IMPLEMENTATION_GAPS.md` DRV-ISA-01/P0.6): (a)
load-direct-to-store, (b) the extmode bridge for R>=64, (c) `iadd2`
REGISTER-mode, (d) general control-flow synthesis, (e) `reg_move`. This
experiment closes or bounds each.

## 2. Falsifiable hypotheses

**H_c (iadd2 register-mode, TOP PRIORITY):** for the register-register
tail shape `opc_tail=0x17/opc_tail2=0x05, srcA=0xA8` (db.json's own "reg-
srcB tail" note), `srcA` is a FIXED read of r0 (not `dst`, not zero) and
`srcB`'s scattered field encodes `4*N` for register N, for N in the
`mov_imm`-seedable range 0..15. **Refuter:** any independently-constructed
case (differing `dst`, differing seed values, differing which register
holds which value) where the computed result does not equal `r0 (+/-)
r_N` for the N the `srcB_imm=4*N` formula predicts.

**H_a (load-direct-to-store):** EXP-0090's own `addr_mode=0x56` direct-
forward mechanism (`finding_3`) generalizes to INDEPENDENT load/store
offsets when the byte address is carried by the DYNAMIC CONTENT of an
index register (not `idx_off`, which must stay 0 on both sides), and
CHAINS across multiple pairs in one program. **Refuter:** a
cross-index or chained construction that does not forward the correct
value, or an `idx_off=0`-both-sides construction that still fails.

**H_d (control flow):** the two branch displacements in EXP-0090/
EXP-0112's own CF skeleton (`jump`/`jump_cond`) can be RECOMPUTED (not
copied) for a body of different length, using `target = jump_addr +
offset` (EXP-0115's own derived formula, no +4), and the recomputed
program executes correctly on hardware. **Refuter:** a byte-exact
reproduction of the N=0 case's own already-known-correct offsets (a pure
arithmetic check, no GPU) is the DECISIVE test of the FORMULA; live
hardware execution of N>=1 is a SEPARATE, weaker-evidence test that may be
confounded by unrelated carrier issues (as it was in this experiment's own
pilot phase) and is NOT gated below for that reason -- see PROGRESS.md
Milestone 3 and RESULTS.md item (d).

**H_b (R>=64):** SYNTHESIS ONLY, no new hypothesis -- db.json's own
`falu2`/`falu2i` entry (updated 2026-08-28, citing EXP-0112/EXP-0113/
EXP-0119) already states the closed rule for that field family. This
experiment's own H_c work provides an independent DATA POINT (iadd2's
`dst` field reaching >>63) that is reported alongside it, not a new claim
requiring its own falsification design.

**H_e (reg_move):** SYNTHESIS ONLY -- EXP-0101/EXP-0090/EXP-0113 already
established the bounded negative; no new hypothesis tested.

## 3. Frozen generator, corpus, and pass criterion

**Gated corpus:** `casematrix.py::build_cases()`, 39 cases, two groups:

- **IADD_REG (22 cases):** N=0..15 sweep (`dst=40+N`, `r0val=20+N`,
  `rNval=60+N` for N!=0, all seeds in `mov_imm`'s HW-VALIDATED safe range
  0..127); 2 `dst` boundary probes (dst=90 expect True, dst=110
  EXPLORATORY expect False); 2 subtract-polarity cases (addsub=0, HW-
  VALIDATED this experiment to compute `rN-r0`, not the naive `r0-rN`);
  1 adversarial (`srcB_reg_hi` forced nonzero -- DISCLOSED PILOT SURPRISE:
  this does NOT corrupt the read, kept as pre-registered expect_match=
  False per this project's "carrier-dependent opflags" precedent); 1
  positive-control deliberate mismatch.
- **LOADSTORE_DIRECT (17 cases):** 8 same-index round trips (idx 0..7); 4
  cross-index pairs; 2 chained 2-pair programs; 2 adversarial (`idx_off`
  forced to 1 on the load side / the store side); 1 positive-control
  deliberate mismatch.

Every case's hex is asserted round-trip-clean (`isadb.disassemble` +
re-`assemble`) by `verify.py --selftest`, which also re-checks
determinism across two in-process `build_cases()` calls.

**Pass criterion (frozen before either gated run):**
- Every `expect_match=True` case must show `status=="OK"` and
  `match==True` in BOTH gated runs.
- Every `expect_match=False` case's actual `match` is recorded, not
  required to equal a specific boolean -- each such case's `notes` field
  states its own prediction/disclosure BEFORE capture (per SS2's
  falsifiers). `verify.py --captured` explicitly reports (not fails on)
  any `expect_match=False` case that unexpectedly MATCHES.
- `01_results.jsonl` byte-identical between `m4-20260828-run01` and
  `m4-20260828-run02`.
- Standing gates: `--selftest`, `--seqtest` (PRE_GPU/RUN01_PRESENT/
  RUN02_PRESENT), a NON-RECORDED smoke case before `raw/` is created,
  `--preflight`/`--between-runs`, no nondeterministic field in the gated
  file, append+fflush per record, `PROGRESS.md` per milestone, hard 45s
  timeout per case (own subprocess), each case its own fresh process, no
  post-capture repair, no run-id reuse.

## 4. Pinned source hashes (frozen at this commit)

```
isa_helpers.py                   478f564cc1d529ac27200371761e1d7f7635844d3b438a40471f3a0904085ba8
families.py                      e4370e03991a6e0130912cd9a7c9b6d32d4afe4e862edec3df6a6c2bef8a7380
casematrix.py                    df86baa206e12d601a5bcd94af5ce24e08b7829c714dc582dc520caf9239d444
harness/build.sh                 de1fc448b0fe8d21c5ba73dabedc69f25a5c2db29dd4713c189f65566629a0ed
harness/case_exec.py             8a95443bf79cfcff7c765a2c7a28aecd5582f64f859e658336919f9ce1bc46f1
harness/recorded_fixture_case0.json  3d09eb0853b1603e0b2b555dac5ba9753642e985f3bcad7b28295d731caa7033
run.py                           f9ed6e5341918402e2759ba868d23a1aabceb9220062f56be49b9922ed5f9c80
verify.py                        aaac6196e4925972cc8cf22d2bba71bd355f49ac14117f577fb4940a42cea825
make_manifest.py                 460cd25a424bcaf404e106a9e69a47001f26cd24769db93952248fc6743094bb
baseline.py                      6fdd82962a1f2d6cb9f6352c1b8b9e2e94dfe0efeddb7c869eb4540af3871cf6
kernels/carrier_dag.metal        ed4b7bfef443a813d6e835efb0f34174e7d3c6e64f3e2e79db99630c089b08b4
```

**Pinned repository revision:** `bb0fc6219b2dd9a19aff20f1c56cc30ef69aebf6`
(informational for provenance; captures are gated on the authored-file
hashes above, never on live git `HEAD`, which the orchestrator moves by
committing sibling experiments -- SUBAGENT_BRIEF.md standing instruction).

## 5. Target and scope

Local Apple M4 (G16G) only. Public Metal API (`newLibraryWithSource:` +
`MTLBinaryArchive` splice, `tools/agxtest`/`tools/shdump`, read-only). No
A18 Pro (hands-off, standing directive). No M5 evidence.

## 6. Disclosed pilot-phase safety events (SS0's convention)

Two real GPU hangs occurred during pilot-phase item (d) work (CF
displacement extension, on a since-abandoned confounded padded carrier)
and TWO further real hangs occurred during item (c) pilot work (traced to
the `mov_imm` imm8>=128 boundary, now hard-rejected by `isa_helpers.
mov_imm` and absent from the frozen corpus). All FOUR hangs were reported
cleanly by `agxrun`'s own 15s internal timeout (`kIOGPUCommandBufferCallback
ErrorHang`) with the host remaining fully responsive throughout (confirmed
by uninterrupted continued command execution in the SAME shell session,
no `macvdmtool`, no manual intervention) -- consistent with CLAUDE.md's
own documented recovery model ("Illegal shader encodings on the local M4
are usually fault-contained... Occasional crashes are an expected part of
GPU RE"). No STOP/BLOCKED condition was ever warranted. The frozen corpus
below stays entirely within the mov_imm 0..127 safe range and does not
retry the CF-extension technique.

## 7. Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: this experiment's own authored generator/harness code
  (isa_helpers.py/families.py/casematrix.py -- every instruction built via
  tools/agx-isa's own READ-ONLY isadb.assemble()), our own carrier MSL
  (kernels/carrier_dag.metal, copied verbatim from EXP-0112's own
  OWN-SHADER compile, cited), tools/agxtest (read-only, splice-and-run),
  tools/shdump (read-only, compile+extract).
Apple binary introspection: NONE.
Reproduction: python3 -B run.py --run-id <id> --execute (after verify.py
  --selftest/--preflight/baseline.py all PASS).
```
