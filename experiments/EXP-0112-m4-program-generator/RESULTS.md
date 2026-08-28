# RESULTS -- EXP-0112 M4 program generator (DRV-ISA-01 / P0.6 generation proof)

**STATUS: CAPTURED / PROMOTED.** Both contracted runs (`m4-20260828-run01`,
`m4-20260828-run02`) complete, 161/161 cases each, `01_results.jsonl`
**byte-identical** across both runs (sha256
`568afb98c13f7c896163d0853b12356a1d7686f8eeaec445fbf97f3344a1bc96`).
**140/140 `expect_match=True` cases PASSED in both runs (100%). 21/21
`expect_match=False` cases behaved exactly as pre-registered (0
unexpected deviations, either direction, in either run).** `verify.py
--selftest` (986 checks), `--seqtest`, `--preflight`, `--between-runs`,
`--captured` all PASS. Target: **local Apple M4 / G16G only** (macOS
26.6.2/25G82, arm64). No A18 Pro replication (hands-off). No M5 evidence
used anywhere.

---

## 0. Headline verdict

**A generator built purely from documented, previously-HW-VALIDATED
per-instruction-family rules can synthesize arbitrary-shaped dataflow
programs -- across randomly varying DAG depth/width, register count and
REUSE, immediates at boundaries, and memory offsets -- and get every one of
them bit-exactly correct, with zero hand-tuning per program.** This is a
qualitatively different and stronger claim than EXP-0090 (four individually
hand-built programs) or EXP-0101 (individually hand-constructed splice
cases): here, 100 independently generated dataflow DAGs (2-35 nodes,
44/100 requiring genuine physical-register reuse under the documented
liveness discipline, up to 13 of 14 pool registers simultaneously live)
were each an *emergent* composition of rules the generator had never seen
combined in that specific way, and every single one matched its host oracle
exactly.

**Three real generator/harness bugs were found and fixed during a
disclosed pre-freeze pilot phase** (not hidden -- PRE_REGISTRATION.md
section 5, PROGRESS.md Milestone 2): a scope violation (treating a
load-directly-to-store path as if it were the validated load-to-ALU
bridge), a register-allocator headroom bug, and a base_slot-derivation
methodology bug for the CF carrier. **One further finding is disclosed but
NOT a bug**: `falu2` register-form's `opflags` field had NO observable
effect on `kernels/carrier_dag.metal` across all 4 raw values in two
operand-production shapes, contradicting EXP-0090's own finding_1
(established on a *different* carrier) -- additional evidence for this
project's already-documented carrier-dependent-splice phenomenon, applied
to a field where it had not previously been observed.

**The register-boundary sweep the coordinator specifically requested is
decisive**: EXP-0101's load-to-ALU bridge rule (`extmode = 2*R`) is
confirmed correct for **R = 0..63 (dense 15-point sweep, all pass)**, and
is now shown to **silently alias to `r(R mod 64)` for R in [64,112]** (not
a "silent zero" -- confirmed by 4 poison-register controls that make the
aliased read visibly return the poison value) and to **FAULT the command
buffer for R in {126,127}** -- two distinct, independently classified
failure modes at the boundary and near the top of the 7-bit encoding.

---

## 1. OBSERVED vs INTERPRETED

### 1.1 OBSERVED (directly, from `raw/m4-20260828-run01/01_results.jsonl`,
byte-identical to run02)

| family | cases | `expect_match=True` pass rate | `expect_match=False` as-predicted rate | status breakdown |
|---|---|---|---|---|
| MAIN_DAG | 100 | **100/100 (100%)** | n/a | 100 OK |
| REGBOUNDARY | 32 | 15/15 (100%) | 17/17 (100%) | 30 OK, 2 CMDBUF_ERROR |
| IADD_ANCHOR | 12 | 12/12 (100%) | n/a | 12 OK |
| CF | 12 | 12/12 (100%) | n/a | 12 OK |
| ADVERSARIAL | 5 | 1/1 (100%) | 4/4 (100%) | 5 OK |
| **Total** | **161** | **140/140 (100%)** | **21/21 (100%)** | **159 OK, 2 CMDBUF_ERROR** |

Every case ran in its own fresh subprocess (one splice-and-dispatch per
process, `harness/case_exec.py`), under a 45s hard timeout. No timeouts, no
harness exceptions, no OS-level faults occurred in either run. No
`STOP.json` was written in either run.

### 1.2 MAIN_DAG structural coverage (from each case's own `notes` field,
independently re-derivable via `generator.generate_dag`)

- DAG size: 2 to 35 nodes (`SIZE_CYCLE`, cycled across 100 seeded draws).
- **44/100 cases have `n_nodes > 14`**, i.e. strictly MORE dataflow values
  than the 14-register pool -- these REQUIRE genuine physical-register
  reuse (a register written, read to exhaustion, and later
  re-written by a completely different, later value) to be constructible
  at all under the 4-bit `dst`-nibble structural cap. Peak simultaneous
  live-register count (`max_live_registers`, independently re-derived by a
  SECOND, allocator-independent diagnostic function, `verify.py
  --selftest`) reaches as high as **13 of the 14-register pool**, across
  61 of the 100 cases reaching `max_live >= 5`.
- Every node type (`const`, `load`, `add_imm`, `mul_imm`, `add_reg`,
  `mul_reg`) appears; every `load` node is bridged into ALU consumption via
  EXP-0101's `extmode=2*R` rule with the verbatim `dst_lo=1,dst_ext9=1`
  token; every multi-consumer node's liveness bit0 is 0 on every A-read but
  the temporally last, which alone is 1 (EXP-0086/EXP-0090's rule); every
  `add_reg`/`mul_reg` node uses `opflags=3` (EXP-0090's "both real" rule);
  immediates are drawn from a boundary-weighted pool (0, ±1, ±0.5, ±30 [the
  documented minifloat max/min], ±100, 0.125, 3.5) 30-35% of the time and
  uniform-random otherwise; `idx_off` is drawn from a boundary pool (0, 1,
  2, 2046, 2047, 512, 1024) 25% of the time and uniform-random over
  0..2047 otherwise.
- 0/100 cases needed the NaN/Inf-avoidance seed-bump fallback (`seed_bumps
  = 0` in every case's own notes -- independently checkable).

### 1.3 REGBOUNDARY sweep (the coordinator-requested field-boundary
construction; `families.py::build_regboundary_program`, `casematrix.py
::build_regboundary_cases`)

`R` (`device_load`'s extmode-target register, the register a subsequent
`falu2i` consumes via EXP-0101's bridge rule) swept 0, 1, 2, 3, 7, 15, 16,
20, 31, 32, 47, 48, 61, 62, 63, 64, 65, 66, 67, 68, 79, 80, 95, 96, 111,
112, 126, 127 -- min, dense-around-the-suspected-64-bit-boundary, and max
of the 7-bit encodable range:

| R range | observed | classification |
|---|---|---|
| 0..63 (15 points) | loaded value delivered exactly | **CONFIRMED correct** -- extends EXP-0101's own spot-check ({0,3,7,16,20}, 5 points) to a dense 15-point sweep across the FULL sub-64 range |
| 64..112 (11 points, non-poisoned) | `0.0` | consistent with either "silent zero" or "aliasing to an unwritten register" |
| 64, 65, 67, 79 (4 points, POISONED: `r(R mod 64)` pre-written to `30.0` before the load) | `30.0` (the poison value, NOT `0.0`, NOT the loaded value) | **DECISIVE: this is register-field ALIASING, not a zero-read.** The consuming instruction's 7-bit `srcA_reg` field is genuinely only 6 bits load-bearing in this context: `R` and `R mod 64` address the identical physical register. |
| 126, 127 (2 points) | `CMDBUF_ERROR` (command-buffer fault, no output) | **A SECOND, DIFFERENT failure mode** -- not aliasing, not silent-zero: an outright fault, specifically at the top 2 values of the 7-bit range |

Positive control baked into the same sweep design: R=7/16/20 (already
individually HW-VALIDATED by EXP-0101) reproduce correctly here too,
confirming the sweep methodology itself is sound, not merely
"everything passes."

### 1.4 IADD_ANCHOR sweep (`K` = logical addend, `families.py
::build_iadd_program`)

`K` swept 0, 1, 2, 63, 64, 65, 100, 127, 128, 129, 200, 255 -- covering the
field's own effective-range boundary. The anchor's `srcB_imm` byte is
computed as `(K<<1)&0xFF`; the EFFECTIVE decoded addend is `((K<<1)&0xFF)
>> 1`, which **wraps at K=128** (`(128<<1)&0xFF = 0`, i.e. K=128 behaves
identically to K=0, and K=129 to K=1, etc. -- an exact mod-128 encoding
boundary, never previously tested; EXP-0090 tested only K in {0,100,127}).
All 12/12 points, including this wraparound, matched the derived-formula
oracle exactly.

### 1.5 CF sweep (`cf.py`, EXP-0090's P3 skeleton reused verbatim)

12 `(a_val, n_val, cond_override)` points, including a 0-trip-count loop,
a 60-iteration loop, both if/else arms, a negative starting accumulator,
and the `cond` field's inverted-guard behavior (`cond=7` skips the loop
entirely regardless of `n_val`, matching EXP-0090's own documented
correction). All 12/12 matched. This is a PARAMETERIZATION of one
validated skeleton (data-driven trip count/branch selection plus one
structural enum field), not new control-flow synthesis -- see SS4.

### 1.6 ADVERSARIAL (deliberate rule violations, `expect_match=False`)

| case | violation | predicted failure | observed | verdict |
|---|---|---|---|---|
| `adv_missing_mods_0xC0` | falu2i consumes a load-sourced operand with `mods=0` instead of the required `0xC0` | silent-zero of the load operand | `5.0` (= `0+5.0`, i.e. the load DID read as 0) | **CONFIRMED as predicted** |
| `adv_wrong_dst_token` | `device_load`'s `dst_lo/dst_ext9` forced to `(0,0)` instead of the verbatim `(1,1)` token | corruption | `5.0` (same silent-zero signature) | **CONFIRMED as predicted** |
| `adv_liveness_flip` | first (non-last) read of a twice-read register wrongly marked `last_use=1` | second (real last) read silently sees 0 | `2.0` (= `0+2.0`) | **CONFIRMED as predicted** |
| `positive_control_deliberate_mismatch` | a genuinely CORRECT construction, compared against a deliberately unreachable oracle (`correct+12345.0`) | mismatch (proves match-detection is not a rubber stamp) | correct value returned, compared against the wrong oracle | **CONFIRMED as predicted** |
| `adv_opflags1_bothreal_carrier_dependent` | `opflags` forced to `1` instead of `3` for a both-real `falu2` | *(originally)* silent-zero of srcB, per EXP-0090 finding_1 | **the CORRECT sum** (relabelled `expect_match=True` after the pilot phase; see SS2) | **disclosed carrier-dependent discrepancy, not a confirmed adversarial violation** |

---

## 2. The carrier-dependent `opflags` discrepancy (disclosed, not resolved)

A decisive, independently re-run sweep (`opflags` in all 4 raw values
{0,1,2,3}) was performed in TWO shapes on `kernels/carrier_dag.metal`:

1. Both `falu2` operands produced via the EXP-0101 load-bridge
   (`device_load` -> `falu2i`).
2. An EXACT re-creation of EXP-0090's own `redecisive.py::
   finding_1_falu2_srcB_needs_opflags3` shape (both operands produced via
   two adjacent `falu2i` instructions reading an unwritten-register seed
   plus an immediate, register indices 0/2/3 matching EXP-0090's own
   choice).

**All 8 runs (4 opflags values x 2 shapes) returned the CORRECT sum.**
`opflags` had NO observable effect on THIS carrier -- not even
reproducing EXP-0090's own `opflags=2` (bit1 set, bit0 clear) failure,
despite shape (2) being a byte-for-byte re-creation of the ORIGINAL
falsifying construction, on a DIFFERENT carrier file
(`kernels/carrier_p1.metal` there vs. `kernels/carrier_dag.metal` here).

**This is not a re-characterization of `opflags`'s semantics** (out of this
experiment's scope to root-cause) -- it is a disclosed, reproducible
DISCREPANCY between two experiments' observations of the identical field on
different carriers, consistent with and extending this project's own
already-documented "carrier-dependent splice behavior" caveat (EXP-0099
PROGRESS.md Milestone 3, there about `device_load` splice reliability, here
about a different field entirely). **This finding does not weaken any
MAIN_DAG result**: the generator's own policy is to always set
`opflags=3` for a both-real `falu2`, which is safe under either carrier's
observed behavior (EXP-0090's finding_1's "correct" value IS opflags=3;
this experiment's own finding shows opflags=3 also always correct). An
implementer relying on EXP-0090's own `opflags=2`-fails claim as a general
hardware fact (rather than scoped to that specific carrier) would be
over-generalizing -- flagged here explicitly so it is not silently
inherited as universal.

---

## 3. Generator design (what makes this a GENERATOR, not a replay)

`generator.py` is a 3-pass pipeline, fully documented in its own module
docstring:

1. **Structure** (`generate_dag`): a seeded RNG builds a DAG of typed nodes
   (`const`/`load`/`add_imm`/`mul_imm`/`add_reg`/`mul_reg`), each
   operand reference chosen from a live-node pool, respecting a
   consumption discipline that stays strictly inside the union of every
   prior experiment's independently validated rule set (documented in
   `generator.py`'s own "CONSUMPTION DISCIPLINE" section) -- e.g. a
   register is EITHER read only via chained `falu2i`/`falu2`-srcA "A-reads"
   (liveness-bit-tracked) OR consumed exactly once via `falu2`-srcB OR
   stored exactly once, NEVER a mix, because no prior experiment
   established the mixed case is safe. Live-node count is providably
   bounded at `POOL_SIZE-2=12` during structure generation (a forced
   single-operand closing move whenever the cap is hit), leaving headroom
   for the finalization pass.
2. **Register allocation** (`allocate_registers`): a linear-scan allocator
   over the 14-register pool with REUSE -- a register is freed the
   instruction after its producer's last consumption event, and the next
   node to need a register gets the smallest currently-free one. This is
   the part of the generator that had NO precedent in this project: every
   prior hand-built program (EXP-0090 P1/P2/P3) used a fresh, never-reused
   register per value.
3. **Emission + host oracle** (`emit_program`): every node becomes one
   `isa_helpers.py` builder call (itself one `tools/agx-isa`
   `isadb.assemble()` call) -- NEVER a copied byte string -- while
   independently computing the exact IEEE-754 float32 result on the host,
   using the SAME minifloat/address-formula codecs the hardware is
   documented to use (`isadb.imm_encode`/`imm_decode`, EXP-0082's address
   formulas).

Every field value the generator emits traces to a specific, cited,
HW-VALIDATED rule (module docstrings list them); the only VERBATIM
constants are `isa_helpers.DST_TOKEN_KNOWNGOOD=(1,1)` (EXP-0101's own
required copy-verbatim field) and the `iadd2_anchor`/CF-skeleton byte
patterns (EXP-0090's own established, explicitly-not-independently-derived
anchors) -- both labelled at every point of use, per this project's
"copying single documented constants is fine and must be labelled" rule.

---

## 4. The generation envelope -- what CAN and CANNOT be generated

**CAN be generated today, by this generator, independently, HW-VALIDATED
(140/140 `expect_match=True` cases, two byte-identical runs):**

- Arbitrary-shaped dataflow DAGs of `const`/`load`/`add_imm`/`mul_imm`/
  `add_reg`/`mul_reg` nodes, 2 to 35 nodes deep/wide, with:
  - independently chosen immediates across the full representable range
    including boundary values (min/max minifloat, 0, negative);
  - independently chosen memory offsets (`idx_off`) across the full 0..2047
    field, including the boundary values (0, 1, 2046, 2047);
  - independently chosen register assignments, INCLUDING genuine
    **register reuse** (a physical register written, fully consumed, and
    later independently rewritten by an unrelated value later in the same
    program) -- 44/100 MAIN_DAG cases required this, up to 13/14 pool
    registers simultaneously live, all correct.
  - `device_load` -> `falu2`/`falu2i` bridging for ANY register in 0..63
    (dense-swept, not spot-checked).
- The EXP-0090 `device_load`->`iadd2`->`device_store` verbatim anchor, with
  independently varied addend K across its FULL effective 0..127 range
  including the K=128 wraparound boundary.
- The EXP-0090 loop+if/else->select control-flow skeleton, parameterized
  by trip count, branch-selecting data, and the `icmp_pred` `cond` field.

**CANNOT yet be generated / explicitly OUT of this generator's envelope
(named, not silently worked around):**

- A `device_load`'s value stored DIRECTLY (no ALU consumer) -- this
  generator deliberately routes every such case through a trivial `+0.0`
  ALU finalizer instead of attempting EXP-0090's structurally distinct
  `addr_mode=0x56` load->store direct-forward mechanism, which is
  register-file-bypassing and cannot be composed into a general
  register-addressed DAG model without its own dedicated synthesis rules
  (an open item, not attempted here).
- `device_load`->ALU bridging for consumer register `R >= 64`: R in
  [64,112] silently ALIASES to `r(R mod 64)` (decisively confirmed via
  poison controls, SS1.3); R in {126,127} FAULTS the command buffer. A
  driver backend MUST restrict the extmode-bridge target register to 0..63
  -- this experiment tightens EXP-0101's own stated "R may be any value
  0-127" claim, which is now shown FALSE above 63.
- `iadd2` register-mode (both operands GPR, independently chosen
  registers/dst) -- still `UNKNOWN` (EXP-0090's own open item; this
  experiment reuses the ONE verbatim anchor, dst fixed, srcA fixed, only
  the immediate independently varied -- not a generation capability).
- General control-flow DAG synthesis (arbitrary nesting/shape composed
  from `icmp_pred`/`if_push`/`jump_cond`/`pop_reconverge`/`isel10`
  primitives) -- this experiment parameterizes ONE fixed skeleton
  (loop + if/else->select), not a composable CF generator; EXP-0104's own
  finding that reducible if/else has TWO qualitatively different lowerings
  (pure predication vs. real branch machinery, selected by
  return/break/continue presence) means a true CF generator needs that
  distinction built in, which this experiment does not attempt.
- `reg_move` as a general dataflow primitive -- correctly EXCLUDED from
  this generator entirely (EXP-0101's Blocker 2 remains unresolved; using
  it would not be "generating a legal program").
- Any node consumed by BOTH an ALU op (with the ALU read as its last A-read)
  AND a later `device_store` of the SAME register -- an untested
  interaction between the liveness-bit writeback-suppression mechanism
  (docs/isa/register-move-and-liveness.md SS2.3b) and a passive store read;
  this generator's "a stored node has no other consumer" discipline
  sidesteps it entirely rather than assuming it is safe.

---

## 5. Failure taxonomy (per CODEX: a failure class is worth more than a
high pass rate)

Because the final gated corpus achieved 0 unexpected deviations, this
section documents the taxonomy discovered and RESOLVED during the
disclosed pre-freeze pilot phase (PRE_REGISTRATION.md SS5) -- these are the
real, substantive findings, not swept under a clean final number:

1. **Unmodelled field-rule scope violation** (generator bug): applying a
   consumer-validated bridge rule (EXP-0101's `extmode`) to a DIFFERENT,
   unvalidated consumer (a bare `device_store`). Symptom: 3 independent
   stored values in one program all read back the SAME stale first value.
   Root cause identified by direct DAG-structure inspection
   (`generator.generate_dag` printout) plus a minimal 2-node hardware
   repro. Fixed by narrowing the generator's own envelope (SS4), not by
   inventing an untested second bridge mechanism.
2. **Register-allocator liveness-accounting bug** (generator bug, provably
   fixed): insufficient headroom between the structure pass's live-count
   cap and the register allocator's hard pool size, surfaced only at
   `n_nodes >= ~15` (past the point the finalization pass needs to
   bootstrap a free register). Fixed with a formal (not merely empirical)
   proof of the corrected invariant, independently re-verified by
   `verify.py --selftest`'s own second, allocator-independent live-count
   diagnostic.
3. **base_slot-derivation methodology bug** (harness bug, real HW fault
   observed): deriving a carrier's buffer-to-base_slot mapping from a
   STRUCTURALLY DIFFERENT stand-in probe kernel instead of the actual
   carrier. Symptom: a real, reproducible (4/5 repeats) wrong value
   consistent with reading a garbage huge loop-trip-count, plus 1/5
   CMDBUF_ERROR. This is the EXACT trap EXP-0090 itself documented
   ("the mapping must be independently re-derived per carrier") --
   re-encountered here because the ORIGINAL verification method (a
   separate probe) was insufficiently faithful to the trap's own stated
   cause. `baseline.py` now asserts base_slot ORDER (not just the set) to
   make a recurrence structurally impossible to miss silently.
4. **register-boundary aliasing + fault** (a genuine hardware finding, not
   a bug -- SS1.3): R>=64's failure mode is NOT uniform (silent alias for
   [64,112], hard fault for {126,127}) -- a driver must treat this as TWO
   named, distinct constraints, not one.
5. **carrier-dependent `opflags`** (a genuine, disclosed, UNRESOLVED
   discrepancy -- SS2): flags a specific prior claim (EXP-0090 finding_1)
   as carrier-scoped rather than universal.

---

## 6. Gate results

- `verify.py --selftest`: **PASS**, 986 checks (13 base checks + 5 corpus
  structural checks + 3 checks per case x 161 cases [group validity,
  carrier validity, finite-oracle check, round-trip] + 1 register-allocator
  invariant re-check across a 30x7=210-point independent sweep).
- `verify.py --seqtest`: **PASS** at all three tree states (`PRE_GPU`
  before either run, `RUN01_PRESENT`, `RUN02_PRESENT`).
- `make_manifest.py --check` / `--write`: **PASS** (16 authored files).
- `verify.py --preflight`: **PASS**.
- `verify.py --between-runs`: **PASS** -- gated ONLY on
  `authored_{code,kernel,doc}_sha256` and the case count, never live git
  `HEAD` (per SUBAGENT_BRIEF.md's standing instruction).
- `verify.py --captured`: **PASS** -- `01_results.jsonl` byte-identical
  across both runs (sha256 `568afb98c13f7c896163d0853b12356a1d7686f8eeaec4
  45fbf97f3344a1bc96`); `01_timing.jsonl` correctly not required to match.
- No `STOP.json` in either run. No timeouts, no host wedge, `macvdmtool`
  never invoked, A18 Pro never touched.
- `baseline.py`: **PASS** before each run -- both carriers' compiled
  lengths and (ORDER-checked, not just set-checked) base_slot mappings
  re-derived fresh, matching the frozen constants.

---

## 7. DRV-ISA-01 statement

**A GENERATOR (not a hand-tuned program set) can synthesize, from
documented per-family rules alone, arbitrary dataflow programs over the
`const`/`device_load`/`falu2`/`falu2i`/`device_store` family combination --
including genuine physical-register reuse under the documented liveness
discipline, immediates and memory offsets at their encoding boundaries, and
the `device_load`->ALU bridge for any target register 0..63 -- with a
100% match rate against an independently computed host oracle over 140
generated + swept `expect_match=True` programs (two independent,
byte-identical hardware runs).**

This is a MEANINGFULLY STRONGER claim than EXP-0090 (4 hand-built programs,
3 promoted) or EXP-0101 (individually hand-constructed splice cases): the
44/100 MAIN_DAG cases requiring register reuse, and the dense 0..63
register-bridge sweep, are territory NO prior experiment in this
repository exercised, and the generator got all of it right without any
per-program tuning -- exactly the acceptance bar CODEX.md sets ("prove the
*encoder* can synthesize arbitrary legal combinations, not just tokenize").

**The envelope is not yet "arbitrary supported Apple9 shaders"** (the full
DRV-ISA-01 acceptance bar) -- SS4's CANNOT list is the precise, honest
boundary: `iadd2` register-mode, general control-flow synthesis (vs. one
parameterized skeleton), `reg_move`, load-direct-to-store, and the
register-bridge's confirmed >=64 boundary are all NAMED, SCOPED gaps for a
successor experiment, not silently assumed solved. Within the
float-ALU + memory + one-CF-skeleton + one-integer-anchor envelope
demonstrated here, DRV-ISA-01 can be marked **substantially advanced**
(from "we can hand-build specific programs" to "we can generate a broad,
randomly-sampled CLASS of programs correctly"), not yet **closed**.

---

## 8. Limitations / honest gaps

- **Single-thread dispatch only** (`grid=1,tg=1`), matching every prior
  hand-built-program experiment in this repository -- no divergence, no
  cross-lane interaction, no SIMD-width effects tested by this generator.
- **Float32 add/mul only** for the DAG family -- no `fsub`/division/
  transcendental/vector-width nodes; adding them is a natural next
  extension of the SAME generator architecture (a new node type + emission
  rule), not a redesign.
- **The `opflags` carrier-dependence (SS2) is not root-caused** -- flagged
  as an open item for a successor experiment with the resources to isolate
  WHY two carriers differ (compiled instruction count? register-file
  occupancy at splice time? something else?).
- **CF is a parameterized skeleton, not a generator** for control flow --
  see SS4's explicit scoping.
- **The register-boundary sweep (SS1.3) covers extmode-target aliasing
  only for the LOAD-bridge context** -- EXP-0099's own literal-index
  aliasing finding was for a DIFFERENT addressing context (a directly
  GPR-resident value's own register-select field); this experiment
  independently re-confirms the SAME 64-boundary pattern generalizes to
  the bridge context, but the underlying hardware mechanism (why exactly
  64, why 126/127 specifically fault) remains uncharacterized.

---

## 9. Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: this experiment's own authored generator/harness code
  (generator.py, families.py, cf.py, casematrix.py, isa_helpers.py --
  every instruction built via tools/agx-isa's own READ-ONLY
  isadb.assemble()), our own carrier MSL (kernels/carrier_dag.metal,
  kernels/carrier_cf.metal), our own splice+run harness
  (harness/case_exec.py over tools/agxtest/agxtest.py, tools/shdump for
  carrier compilation).
Apple binary introspection: NONE.
Reproduction: README.md's command sequence.
Evidence: raw/m4-20260828-run01/, raw/m4-20260828-run02/ (byte-identical
  01_results.jsonl, sha256 above), manifest.json, analysis/summary.json.
```
