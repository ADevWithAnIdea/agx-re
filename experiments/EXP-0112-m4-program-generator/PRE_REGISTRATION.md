# PRE_REGISTRATION -- EXP-0112 M4 program generator

Frozen 2026-08-28, before either contracted capture run. This document
freezes the generator, the seed and recurrence, the corpus size, and the
pass criterion. Everything below reflects the generator and case matrix
AFTER an informal pilot-verification run (161/161 cases, `work/pilot_out.txt`,
not gated/not committed -- deleted before capture) surfaced and fixed three
real bugs and refined two `expect_match` predictions, exactly per this
project's standing convention (EXP-0101 RESULTS.md's own "one informal
pilot-verification run" pattern). The bugs and their fixes are first-class
findings, not swept under -- see SS5 and RESULTS.md.

## 1. Question

`APPLE9_RE_IMPLEMENTATION_GAPS.md` DRV-ISA-01 / P0.6 requires proving a
compiler backend can **synthesize arbitrary legal AGX9 programs** from
RULES, not merely tokenize or hand-replay captured ones. EXP-0090 hand-built
FOUR specific programs (3 promoted). EXP-0101 solved the load-to-ALU bridge
rule but validated it only via individually hand-constructed splice cases.
Neither proves a GENERATOR exists that can compose these per-family rules
into novel, randomly-shaped programs and get them right without per-program
tuning. This experiment builds that generator and validates it against a
randomized corpus.

## 2. Falsifiable hypothesis

**H0 (the generator works):** a program generator built purely from the
documented, HW-VALIDATED per-instruction-family rules (EXP-0101's load-to-ALU
bridge, EXP-0090's opflags/extmode/liveness rules, EXP-0082's address
formulas, EXP-0006's minifloat codec), applied to randomly-generated
dataflow DAGs with register reuse, produces programs that match an
independently host-computed oracle at a high rate (>=95% of
`expect_match=True` cases), with every deviation traceable to a specific,
named field-rule gap rather than a generator implementation bug.

**Refuter:** a pass rate below 95% on `expect_match=True` cases with
deviations that do NOT resolve to a clean, nameable rule (i.e. look like
generator bugs, not hardware facts) would refute H0 -- exactly what
happened in the pilot phase for the initial (buggy) generator, see SS5.

**Independent variable:** DAG shape/depth/register-reuse pattern (seeded
RNG). **Controlled:** every per-instruction-family field rule (frozen code).
**Confounders considered:** float32 overflow-to-NaN via a random
multiplication chain (mitigated: bounded MEM_WORDS magnitude + IMM pool +
a NaN/Inf detector with deterministic seed-bump fallback, never triggered
in the frozen 100-case MAIN_DAG corpus -- see `casematrix.py`); carrier-
dependent splice behavior (a REAL, documented risk in this project,
EXP-0099 PROGRESS.md Milestone 3 -- re-encountered here for a DIFFERENT
field, see SS5 item 3).

## 3. Frozen generator, seed, recurrence, corpus size

**Generator code** (SHA-256, frozen at this commit):

```
isa_helpers.py    9789063b51612bf152766eb3c8b6891a8effe91992794fd1725453cc8a45dca5
generator.py      71338b5c6e41304fcbb3cd605f63f07fb53174fe8a234a219bda1a20faf3ed7d
families.py       757f6e58d01eca257e76d548cc97f9eb7cee741e2c51cfa96496dbb473fbd4cd
cf.py             217bc9105817e9355efd7a8c2c6cc2c84c3db124cb74db61298c23054e1f7a83
casematrix.py     bebce6367bd9cf5ec1f6968e292167172cfd6bacd7b2fa2dd6e3908da6f5e825
harness/build.sh          7f983be6fd0de63e8f62d2aea8156bf22394ac02d117d96a825d5b02f0b0a546
harness/case_exec.py      42a7b932e85140c6e6989f7fb2f503a6e1a899f751e066b6136b04e22ef63d8b
run.py            3b24022d6dd95109a16628242e7664748edd8b0652daccc347fbea703758d24c
verify.py         f4e2cb75422a9cc5a98ad35cc0dcb6f91056a9ba472a5512c031b5ae3c5aa62c
make_manifest.py  ba756238a257196e5e3b9d7d9008dcaa90c48f2aeed020780e454df83bf7efff
baseline.py       b622720ed002de20043b09290bafa20ebe5359319542ed1bf0921b769f5cd1e8
kernels/carrier_dag.metal  ed4b7bfef443a813d6e835efb0f34174e7d3c6e64f3e2e79db99630c089b08b4
kernels/carrier_cf.metal   49740e671e78c571ba8c8deaa9cf990dad1e2c96a7c63e2322f9e23a21477726
```

**Pinned repository revision:** `72c2dde8afd896e384afa20050bdd040f657ca78`
(informational for provenance; per SUBAGENT_BRIEF.md, captures are gated on
these authored-file hashes, never on live `git HEAD`, which the
orchestrator moves by committing sibling experiments).

**Recurrence (`casematrix.py::build_cases()`, pure function of the frozen
files above -- calling it twice, on any machine, on any day, produces
byte-identical output as verified in SS4):**

- **MAIN_DAG (100 cases):** `for i in range(100): seed=i, n_nodes =
  SIZE_CYCLE[i % 24]` where `SIZE_CYCLE = [2,3,4,5,6,7,8,9,10,11,12,13,14,
  15,16,18,20,22,24,26,28,30,32,35]`. `generator.generate_dag(seed,
  n_nodes)` is a pure function seeded as `random.Random("EXP-0112-dag-%r" %
  seed)`. If the resulting oracle contains a non-finite value (see SS "float
  overflow" confounder), the seed is deterministically bumped by
  `+100000*k` until clean (never triggered for this frozen 100-case set;
  `seed_bumps=0` in every case's `notes` field, independently checkable).
- **REGBOUNDARY (32 cases):** a fixed, hand-enumerated register sweep `R in
  {0,1,2,3,7,15,16,20,31,32,47,48,61,62,63,64,65,66,67,68,79,80,95,96,111,
  112,126,127}` (28 cases) plus 4 poison-control cases at `R in
  {64,65,67,79}`. Deterministic by construction (no RNG).
- **IADD_ANCHOR (12 cases):** fixed `K in {0,1,2,63,64,65,100,127,128,129,
  200,255}`. Deterministic by construction.
- **CF (12 cases):** fixed, hand-enumerated `(a_val, n_val, cond_override)`
  tuples. Deterministic by construction.
- **ADVERSARIAL (5 cases):** 4 deliberate single-rule violations plus 1
  positive control with an unreachable oracle. Deterministic by
  construction.

**Total corpus: 161 programs** (exceeds the 100-minimum). `verify.py
--selftest` asserts `len(build_cases()) >= 100`, determinism across two
in-process calls, unique names, dense 0..N-1 indices, every oracle value
finite, and every case's hex round-trips through `tools/agx-isa`'s own
`assemble`/`disassemble`.

## 4. Pass criterion (frozen before either gated run)

- Every `expect_match=True` case must show `status=="OK"` and
  `match==True` in BOTH gated runs.
- Every `expect_match=False` case's actual `match` value is recorded, not
  required to equal a specific boolean beyond "matches its own pre-registered
  prediction" -- each such case's `notes` field states the SPECIFIC
  predicted failure mode (silent-zero, aliasing, fault) BEFORE capture.
- `01_results.jsonl` (the gated fields: `i,name,group,carrier,oracle,
  expect_match,notes,status,pipeline_source,out_hex,observed,match`) must
  be byte-identical between `m4-20260828-run01` and `m4-20260828-run02`.
- Standing gates: `--selftest`, `--seqtest` (PRE_GPU/RUN01_PRESENT/
  RUN02_PRESENT), a NON-RECORDED smoke case before `raw/` is created,
  `--preflight`/`--between-runs`, no nondeterministic field in the gated
  file, append+fflush per record, `PROGRESS.md` per milestone, hard 45s
  timeout per case (own subprocess), each case its own fresh process, no
  post-capture repair, no run-id reuse.

## 5. What the pilot run found and fixed (disclosed, not hidden)

Three bugs and one carrier-dependence discrepancy were found and fixed
during the pre-freeze pilot phase (informal, on real M4 hardware, never
gated/committed as evidence -- this is exactly the role a pilot phase plays
per this project's convention):

1. **Generator bug (structural, MAIN_DAG, ~50% of a small sample):** a
   `load` DAG node that became a LEAF (stored directly, with no ALU
   consumer) used the SAME extmode-bridge construction EXP-0101 validated
   only for falu2/falu2i CONSUMPTION -- but a bare `device_store` reading
   that register directly is a DIFFERENT, unvalidated path (the real
   load->store mechanism is EXP-0090's structurally distinct
   `addr_mode=0x56` adjacent-pair direct-forward, which bypasses the GPR
   file entirely and cannot be mixed into a general register-addressed DAG
   model). **Fix:** every `load` node now ALWAYS gets a trivial `+0.0`
   finalizer A-read before being stored, so every stored load value passes
   through a real, validated falu2i consumption first. Excluded from the
   generator's synthesis envelope, not silently worked around.
2. **Register allocator off-by-headroom bug:** the live-count cap used the
   full POOL_SIZE (14), leaving no slack for the finalization pass (closing
   several leftover open nodes sequentially needs at least one temporarily
   free register to bootstrap). **Fix:** `EFFECTIVE_CAP = POOL_SIZE - 2`
   during DAG structure generation; verified empirically clean (0
   violations) across a wide (seed, n_nodes) sweep, re-checked again by
   `verify.py --selftest`.
3. **Methodology bug, CF family base_slot (a real, reproducible hardware
   failure, not merely wrong-looking output):** `cf.py` initially derived
   `kernels/carrier_cf.metal`'s buffer(1)/(2)->base_slot mapping from a
   SEPARATE, structurally simpler probe kernel, and got base_slot=1/2
   swapped relative to the actual carrier's own compile (base_slot=2/1,
   identical to EXP-0090's own carrier_p3.metal). Running the swapped
   version 5 times produced 4x a stable wrong value (67108864.0 = 2^26,
   consistent with the trip-count buffer being read from an unrelated
   address, causing a very large loop count that saturates float32
   accumulation) and 1x `CMDBUF_ERROR`. **Fix:** derive base_slot ALWAYS
   from the real carrier kernel's own compile (`baseline.py`), never a
   stand-in probe; `baseline.py` now asserts the FIRST/SECOND load's
   base_slot explicitly, not merely the unordered set, specifically to
   catch a recurrence of this bug class before any GPU dispatch.
4. **Carrier-dependent opflags discrepancy (NOT fixed -- a genuine, disclosed
   finding, not a bug):** a decisive re-derivation swept falu2
   register-register `opflags` over all 4 raw values on
   `kernels/carrier_dag.metal`, in two shapes (load-bridged operands, and
   an exact re-creation of EXP-0090's own adjacent-const-producer shape).
   Every one of 8 runs returned the correct sum -- `opflags` did not matter
   at all on THIS carrier, contradicting EXP-0090's own finding_1
   (`opflags=2` silently zeroes srcB, established on `carrier_p1.metal`).
   The only variable changed was the carrier file. This is additional
   evidence for this project's already-documented carrier-dependent-splice
   caveat (EXP-0099 PROGRESS.md Milestone 3), now extended to a different
   field. `casematrix.py`'s `adv_opflags1_bothreal_carrier_dependent` case
   is labelled and gated `expect_match=True` (matching what this specific
   carrier actually and reproducibly does), with the discrepancy recorded
   in its own `notes` field. This finding does NOT weaken any MAIN_DAG
   result: the generator's own policy (always `opflags=3` for a both-real
   falu2) is unconditionally safe under EITHER carrier's behavior.

None of these four items were repaired by "tuning a program to pass" --
items 1-2 are corrections to the GENERATOR's own rules (affecting the
entire MAIN_DAG family uniformly, not any single case), item 3 is a
harness/methodology correction, and item 4 is a disclosed, unresolved
discrepancy with prior work, not a masked failure.

## 6. Target and scope

Local Apple M4 (G16G) only. Public Metal API (`newLibraryWithSource:` +
`MTLBinaryArchive` splice, `tools/agxtest`/`tools/shdump`, read-only). No
A18 Pro (hands-off, standing directive). No M5 evidence.

## 7. Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: this experiment's own authored generator/harness code
  (generator.py/families.py/cf.py/casematrix.py/isa_helpers.py), our own
  carrier MSL (kernels/carrier_dag.metal, kernels/carrier_cf.metal), and
  tools/agx-isa's own READ-ONLY isadb.assemble()/disassemble()/imm_encode/
  imm_decode (no edits).
Apple binary introspection: NONE.
Reproduction: python3 -B run.py --run-id m4-20260828-run01 --execute
  (after verify.py --selftest/--preflight/baseline.py all PASS).
```
