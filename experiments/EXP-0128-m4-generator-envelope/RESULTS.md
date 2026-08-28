# RESULTS -- EXP-0128 M4 generator envelope: closing EXP-0112's CANNOT-GENERATE list

**STATUS: CAPTURED / GATE-CLOSED for items (a) and (c); SYNTHESIZED for
(b) and (e); PARTIAL/UNKNOWN for (d).** Both contracted runs
(`m4-20260828-run01`, `m4-20260828-run02`) complete, 39/39 cases each,
`01_results.jsonl` **byte-identical** across both runs (sha256
`9be3990a762d1d5dedbb0aea3bdd6191c2dfd5670aeaeb1708a050be66918b98`).
34/39 matched, 5/39 mismatched -- **0 unexpected mismatches** (every
mismatch is a pre-registered `expect_match=False` case behaving exactly
as predicted) and **1 disclosed surprise** (a predicted corruption that
did not occur -- see item (c) SS3.4). `verify.py --selftest` (273
checks), `--seqtest`, `--preflight`, `--between-runs`, `--captured`, and
`make_manifest.py --check` all PASS. Target: **local Apple M4/G16G
only.** No A18 Pro replication (hands-off). No M5 evidence used.

---

## 0. Per-item verdicts (headline)

| item | verdict | evidence |
|---|---|---|
| **(c) iadd2 register-mode** | **CLOSED, bounded**: `d[dst] = r0 (+/-) r_N` for N=0..15 (the full `mov_imm`-seedable range), `dst` freely choosable including registers far past 63 -- HW-VALIDATED, gated, 22 cases. Chaining 2+ instances is a disclosed, bounded NEGATIVE. N>15 and any OTHER fixed-first-operand family are OUT OF SCOPE (`UNKNOWN`, not attempted). | `HW-VALIDATED` |
| **(a) load-direct-to-store** | **CLOSED**: EXP-0090's `addr_mode=0x56` mechanism GENERALIZES to independently-addressed, chainable load/store pairs when the byte offset is carried by the index register's dynamic content (`idx_off` held at 0 on the STORE side specifically) -- HW-VALIDATED, gated, 17 cases. | `HW-VALIDATED` |
| **(b) R>=64** | **SYNTHESIZED, not a new experiment**: a hard restriction for the PACKED source-operand register field family (falu2/falu2i's srcA_reg/srcB_reg, and this experiment's own newly-decoded iadd2 srcB field, tested N<=15), NOT a uniform hardware wall -- iadd2's `dst` (write side) independently confirmed reaching far past 63 in this experiment's own gated corpus (dst=90 passes; dst=110 boundary-faults). | `HW-VALIDATED` (cited) + `HW-VALIDATED` (this experiment, dst side) |
| **(d) control flow displacements** | **PARTIAL / UNKNOWN, safety-stopped**: the displacement ARITHMETIC (`target=jump_addr+offset`, EXP-0115's own formula) is independently verified correct (N=0 case exactly reproduces the known-good anchor's own -30/+64 offsets, a deterministic, no-GPU check). Live hardware validation of N>=1 was CONFOUNDED by an unrelated base_slot/buffer-mapping bug in this experiment's own padded carrier and was NOT cleanly re-attempted, per CLAUDE.md's explicit control-flow-hang safety directive, after 2 real (cleanly-recovered) hangs. Reported `UNKNOWN`, not falsified. | `STRUCTURAL` (arithmetic) + `UNKNOWN` (execution) |
| **(e) reg_move** | **Bounded NEGATIVE, synthesized**: three independent experiments (EXP-0101, EXP-0090, EXP-0113) have each tried and failed to find a genuine GPR-to-GPR move; EXP-0113 additionally closed the one remaining named candidate (`reg_move_c9`, byte0=0x2b) with a decisive negative. No new hardware experimentation added here. | cited (`HW-VALIDATED` negative, prior work) |

---

## 1. Item (c) -- iadd2 register-mode: CLOSED, bounded

### 1.1 The decoding problem and why differential compilation alone failed

EXP-0105 judged this "too entangled to hand-assemble safely"; db.json's
own `iadd2` entry hedges: "srcB REGISTER NUMBER is scattered (srcB_reg_hi
b1[1:8] + srcB_imm/b5 + srcB_ext b6[1:8]) ... compiler reg-alloc prevents
clean single-bit isolation." **OBSERVED, this experiment's own pilot
phase** (`work/pilot/`, disclosed PROGRESS.md Milestone 1): compiling
small int-add MSL with varying register pressure and disassembling the
result (`tools/agx-isa`) reproduces this exact entanglement -- compiler-
natural chains mix at least THREE distinct register-mode tail byte
patterns (`srcA=0xA8/opc_tail=0x17/opc_tail2=0x05`, `0xA8/0x15/0x01`,
`0xE8/0x16/0x05`) depending on chain position, plus a structurally
different multiply-add shape (`srcA=0x8C`) that also matches `iadd2`'s
match bits. Differential compilation alone could not cleanly separate
"which byte encodes the register" from "which byte encodes chain
position."

### 1.2 The decisive method: independent HW construction bypassing device_load

**INTERPRETED, then confirmed HW-VALIDATED:** rather than keep chasing
compiler-natural chains, this experiment seeded GPRs directly via
`mov_imm` (bypassing `device_load`'s own extmode/dst_lo entanglement
entirely) and spliced a MINIMAL, single-instruction register-mode `iadd2`
(the ONE clean tail shape, `srcA=0xA8/opc_tail=0x17/opc_tail2=0x05`,
`opmode=2`) directly. Three independently-designed constructions (pilot
phase, `work/pilot/testB.hex`/`testA.hex`, PROGRESS.md M1) decisively
refuted the two live alternative hypotheses:

| construction | dst register | seeded values | observed | refutes |
|---|---|---|---|---|
| `test1` | same as one operand's own register | r0=10, r2=20 | 30 (=r0+r2) | -- (baseline) |
| `testA` | UNRELATED to either candidate operand (r4), r0 left UNWRITTEN | r4=10, r6=20, r2=99 (decoy) | 99 (=~0(r0) + r2) | "srcA = dst" (would give 10+99=109) |
| `testB` | SAME as one operand's own register (r2) | r0=11, r2=13, r4=17, r6=19 | 24 (=r0+r2, NOT self-add 13+13=26, NOT r2+r4=30) | "srcA = dst" AND "srcA = hardwired 0" (would give 13+13=26 either way) |

**INTERPRETED:** `srcA` is a FIXED, format-only byte (`0xA8`) whose
register-selection role is a CONSTANT read of **r0**, entirely
independent of `dst`. `srcB`'s scattered field, for THIS tail shape,
encodes the second operand as `srcB_imm = 4*N` (`srcB_reg_hi=0`,
`srcB_ext=0`) -- swept N=0..15 (the full range `mov_imm`'s 4-bit `dst`
field can directly seed), **16/16 exact matches** during pilot, then
re-confirmed in the GATED corpus below (16 of the 22 IADD_REG cases are
this exact N=0..15 sweep, `dst=40+N`, all `status=OK`/`match=True`, both
runs byte-identical).

### 1.3 GATED corpus results (HW-VALIDATED, 2 runs byte-identical)

| subgroup | cases | result |
|---|---|---|
| N=0..15 sweep (`dst=40+N`) | 16 | 16/16 MATCH |
| `dst` boundary: dst=90 | 1 | MATCH (reinforces item b, SS4) |
| `dst` boundary: dst=110 (EXPLORATORY) | 1 | `CMDBUF_ERROR`, as the case's own cautious (not confident) `expect_match=False` prediction allowed |
| subtract (`addsub=0`) | 2 | 2/2 MATCH (see SS1.4 for the polarity finding) |
| adversarial: wrong `srcB_reg_hi` | 1 | MATCHED despite `expect_match=False` -- disclosed surprise, SS1.5 |
| positive control (deliberate mismatch) | 1 | MISMATCHED as designed -- proves match-detection is not a rubber stamp |

### 1.4 A second decisive finding: subtract polarity is `rN - r0`, not `r0 - rN`

**OBSERVED** (2 independent, pre-registered points, both gated runs):
`addsub=0` on this SAME tail shape computes `d[dst] = r_N - r0` (SECOND
operand minus FIRST), not the naive "srcA-srcB"=`r0-rN` reading db.json's
own semantics note (established for the ANCHOR's immediate-mode shape)
would suggest by analogy. `N=3` (`r0=27, r3=63`) gives `36` (=63-27, not
-36); `N=10` (`r0=34, r10=70`) gives `36` (=70-34). **INTERPRETED:** a
driver emitting subtraction via THIS specific register-mode tail shape
must swap operand order (or negate the result) relative to a naive
`srcA - srcB` reading -- a precise, HW-VALIDATED correction, not merely a
sign-convention guess.

### 1.5 A disclosed, pre-registered surprise: `srcB_reg_hi` does not corrupt

**OBSERVED** (both gated runs, byte-identical): `srcB_reg_hi` forced to
`8` (instead of the `0` every positive case above uses), with `N=2`
otherwise unchanged, gives the CORRECT result (`r0+r2`), not the
predicted corruption. This case's `expect_match=False` prediction was
made BEFORE this was known and left unchanged at freeze (per this
project's own precedent, e.g. EXP-0112's "carrier-dependent opflags"
disclosure) -- `verify.py --captured` explicitly reports it as a
"disclosed surprise," not a gate failure. **INTERPRETED:** consistent
with this experiment's own natural-compiler differential-compilation
recon (SS1.1/PROGRESS.md M1), where `srcB_reg_hi` varied across `{0, 8,
16, 32, 64}` in genuinely-correct compiled instances -- `srcB_reg_hi`
appears INERT for the tested value (`8`) and register range, i.e. NOT a
register-select bit for this field, at least at this one tested value.
This REFUTES (does not merely leave open) the specific hypothesis this
adversarial case was built to test. What `srcB_reg_hi` DOES encode (if
anything, for N>15 where `srcB_imm` alone can no longer reach) is
`UNKNOWN` -- out of scope (SS1.6).

### 1.6 The bounded negative: chaining fails

**OBSERVED, pilot phase (disclosed, not gated -- reproducing it under the
formal gate was judged unnecessary once the mechanism was understood, to
avoid spending further hang-risk budget on an already-decisive negative):**
two or more register-mode `iadd2` instructions in sequence (even writing
to DIFFERENT `dst` registers, even with an inserted `scoreboard_fence`
between them) reproducibly ZERO the result -- confirmed at 2, 3, and 4
chained instances (PROGRESS.md M1). Isolated single instances are solid
(SS1.3); sequences are not. **INTERPRETED:** some additional, unidentified
per-instance state (a scoreboard slot, a chain-position field analogous to
the THREE compiler-natural tail variants observed in SS1.1) is required
for correct chaining that this experiment's naive "just repeat the
instruction" construction does not supply. **The safe driver rule:** emit
AT MOST ONE register-mode `iadd2` of this exact shape per... [interleaving
period] -- i.e., do NOT assume back-to-back emission is safe; a register
allocator wanting more than one such add must currently route the
intermediate value through a DIFFERENT instruction family (e.g. this
project's own validated `falu2`/`falu2i` float path, if the value can
tolerate it) or await a follow-up experiment that decodes the true
chaining requirement.

### 1.7 Generation envelope for item (c)

**CAN be generated today, HW-VALIDATED:**
- `d[dst] = r0 + r_N` for N=0..15, ANY `dst` register up to (and
  including, gated) 90; addsub=1.
- `d[dst] = r_N - r0` for the same N range, via `addsub=0` (note the
  operand-order correction, SS1.4).
- `dst` is a fully independent, freely-choosable 7-bit field (SS4).

**CANNOT yet be generated / OUT OF SCOPE, named:**
- N>15 (no HW-VALIDATED way in this experiment to seed r16+ with a known
  value for ground truth -- `mov_imm`'s `dst` field is hard 4-bit,
  db.json-confirmed; `device_load`-seeding reopens the entanglement SS1.1
  documents).
- A first operand OTHER than r0 (no other `srcA` byte value was tested;
  `0xA8`'s role as "read r0" was decisively established, but whether a
  DIFFERENT `srcA` byte selects a different FIXED register, or unlocks a
  genuinely parameterized first operand, is `UNKNOWN`).
- Two truly INDEPENDENT register operands (both freely chosen, neither
  fixed at r0) -- not established by this experiment.
- Chaining 2+ instances of this family (SS1.6, bounded negative).
- `srcB_reg_hi`'s real role, if any (SS1.5, refuted as a corruption
  source at value 8; not further characterized).

---

## 2. Item (a) -- load-direct-to-store: CLOSED

### 2.1 The base mechanism (cited, re-confirmed)

EXP-0090's `diagnostics/redecisive.py::finding_3_device_load_to_store_
direct_forward_works` establishes: a `device_load` (`addr_mode=0x44`)
immediately followed by a `device_store` with **`addr_mode=0x56`** (not
the usual `0x54` ALU-forwarded form), `extmode=0` fixed, forwards the
loaded value directly, bypassing the GPR file. EXP-0112's generator
deliberately excluded this from its DAG model because it "cannot be mixed
into a general register-addressed DAG" (bypasses registers entirely) --
i.e. it was known to work for exactly ONE fixed, adjacent, `idx_off=0`
pair, never generalized.

### 2.2 This experiment's generalization (HW-VALIDATED, pilot + gated)

**OBSERVED** (pilot phase, PROGRESS.md Milestone 2, then re-confirmed
under the formal gate, SS2.3 below): with `idx_off=0` fixed on BOTH the
load and the store, and the byte address instead conveyed by the DYNAMIC
CONTENT of an index register (`mov_imm`-seeded):
- **Independent addressing**: load and store may use DIFFERENT index
  registers/values -- `load_idx=2, store_idx=5` correctly forwards
  `mem[2]` to output word 5 (not word 2).
- **Chaining**: multiple INDEPENDENT load-store pairs work correctly in
  ONE program -- unlike item (c)'s own chaining hazard.
- **The STORE side's `idx_off` must stay 0** -- forcing it to 1 gives a
  silent WRONG value (not the forwarded word), a real field-boundary
  rule, not a harness artifact.
- **The LOAD side's `idx_off`, by contrast, is NOT special-cased by the
  0x56 mechanism** -- it follows the ordinary, already-HW-VALIDATED
  EXP-0082 load address formula (`idx*scale + idx_off*scale`), simply
  SHIFTING which word gets forwarded (confirmed: `load_idx=2, idx_off=1`
  forwards `mem[3]`, not a zero or a fault) -- a more precise refinement
  of this experiment's own pilot-phase finding than "idx_off must be 0"
  suggested in isolation; only the STORE side's `idx_off` is the
  mechanism-specific constraint.

### 2.3 GATED corpus results (HW-VALIDATED, 2 runs byte-identical)

| subgroup | cases | result |
|---|---|---|
| same-index round trips (idx 0..7) | 8 | 8/8 MATCH |
| cross-index pairs (4 combinations) | 4 | 4/4 MATCH |
| chained 2-pair programs (2 independent designs) | 2 | 2/2 MATCH |
| adversarial: store-side `idx_off=1` | 1 | MISMATCHED as predicted (silent wrong value) |
| adversarial: load-side `idx_off=1` | 1 | MISMATCHED as predicted, for the REFINED reason in SS2.2 (reads a shifted word, not a corrupted one) |
| positive control (deliberate mismatch) | 1 | MISMATCHED as designed |

### 2.4 Generation envelope for item (a)

**CAN be generated today, HW-VALIDATED:** an arbitrary-offset, chainable
load-direct-to-store forward for ANY pair of index-register-encoded word
offsets (own construction validated 0..7; the underlying index register
is a full GPR and this experiment's own scope did not probe beyond 7,
see Limitations), with `idx_off=0` fixed on the store side (the load side
may use ANY `idx_off`, following the standard load address formula).

**CANNOT yet be generated / OUT OF SCOPE:** this mechanism entirely
BYPASSES the GPR file -- it forwards "whatever the immediately preceding
load produced," not an arbitrary, previously-computed register's value.
It is therefore a genuinely DIFFERENT primitive from a general
`register -> store` path, not a superset of it; a DAG-style generator
wanting to store an ALU-computed value still needs the ordinary
`addr_mode=0x54` path (already validated, EXP-0090/EXP-0112). Index
values beyond 7 (up to `mov_imm`'s own 0..127 safe range) are untested,
not merely unsafe -- an extrapolation, not a validated claim.

---

## 3. Item (b) -- R>=64: SYNTHESIZED (no new experiment needed)

**CLOSED, by citation.** `tools/agx-isa/db.json`'s own `falu2`/`falu2i`
entry (updated 2026-08-28, citing EXP-0112 and EXP-0119) already states:

> "ALIASING RULE (EXP-0112, HW-VALIDATED by a dense 15-point sweep with
> poison-register controls): a target register R resolves to r(R mod 64)
> for R in [64,112], and FAULTS the command buffer at R in {126,127}...
> r64-95 have NO validated ALU-source path."

EXP-0113 independently tested and REFUTED the one candidate "wider
register field" mechanism (`iminmax`'s plain 8-bit `srcA`, fed via a
relocated `device_load`) as genuine addressing -- it is non-reproducible
across independent hardware process launches (4/10 singlehop points
disagreed between two gated runs with byte-identical spliced code), which
rules it out as a validated path to r64-95.

**This experiment's own contribution (not a new hypothesis test, a
reinforcing data point from item (c)'s own gated corpus):** `iadd2`'s
`dst` field is a DIFFERENT, WIDER encoding than `falu2`/`falu2i`'s packed
source-operand field -- a full 7-bit register selector (db.json,
EXP-0020: "reaches the whole addressable GPR file, up to 96 regs"), not
the same 6-bit-effective packed field the R>=64 restriction bounds. This
experiment's own gated `iadd_reg_dst_high90` case (SS1.3) independently
confirms `dst=90` computes correctly; the `iadd_reg_dst_probe110` case
(also gated) shows a genuine fault beyond that -- consistent with, though
not by itself proving, EXP-0020's own ~96-register ceiling for THIS
field.

**Net verdict:** "R>=64 is unsafe" is NOT a uniform hardware wall -- it
specifically bounds ALU SOURCE-operand reads for the PACKED register
field family (`falu2`/`falu2i`'s srcA_reg/srcB_reg, and, by this
experiment's own item (c) work, `iadd2`'s srcB field for N<=15 tested).
Destination/write-side register fields (`iadd2`'s `dst`, and by citation
`falu3`'s wider dst form) are a DIFFERENT field shape not subject to the
same restriction, at least up to ~90-95. **The safe driver rule,
unchanged and now reinforced from two independent field families: never
rely on a PACKED, size-sharing source-operand register field (the
`(reg<<1)|size`-shaped ones) to address a register above 63; a register
allocator feeding such an operand must keep the value in r0-r63.
Destination-only fields with a genuinely wider bit width are a separate
case and are not bound by this same rule.**

---

## 4. Item (d) -- control-flow displacement generator: PARTIAL / UNKNOWN, safety-stopped

### 4.1 What WAS established (a real, if partial, positive)

**OBSERVED, no GPU (pure arithmetic, independently reproducible from
committed source):** EXP-0090/EXP-0112's own CF skeleton, reconstructed
instruction-by-instruction via `isadb.assemble()` (not a byte copy),
disassembles to exactly the offsets EXP-0115 independently derived
(`target = jump_addr + offset`, no +4): backward `jump` at file offset
`0x5a`, `offset=-30`, target `0x3c` (the loop head, right after
`if_push`); forward `jump_cond` at `0x2a`, `offset=0x40`, target `0x6a`
(the loop-exit reconverge). A generator that inserts N extra no-op
`falu2i` instructions inside the loop body and RECOMPUTES both
displacements from MEASURED instruction lengths (never copied constants)
reproduces the anchor's EXACT known-good offsets at N=0, confirming the
arithmetic itself is correct, independent of any hardware run.

### 4.2 What was NOT established, and why (a disclosed, bounded gap)

**OBSERVED:** live hardware validation of N>=1 (the actual generation
capability the arithmetic exists to prove) was CONFOUNDED by an unrelated
bug in this experiment's own padding carrier kernel -- adding extra `a[]`
buffer reads for padding shifted the compiler's `base_slot`/argument-table
mapping, reproducing the EXACT "n read from garbage, trip count saturates
to `2^26=67108864.0`" signature EXP-0112's own `cf.py` module docstring
already documents as a known trap. **Decisive evidence this was a
carrier confound, not a displacement-arithmetic failure:** the UNMODIFIED
skeleton (N=0, offsets byte-identical to the known-good anchor) run on
the SAME confounded carrier ALSO failed with the identical wrong-value
signature. Of 4 hardware dispatches on the confounded carrier: 2 HANGed
(`kIOGPUCommandBufferCallbackErrorHang`, `agxrun`'s own 15s timeout fired
cleanly each time; the host remained fully responsive throughout,
confirmed by uninterrupted continued command execution afterward -- NOT a
host wedge, no `macvdmtool`, no manual intervention) and 2 completed with
the base_slot-confounded wrong value (including the N=0 control).

**INTERPRETED, and why this experiment STOPPED here rather than
continuing:** per CLAUDE.md's explicit directive ("control-flow generation
can hang the GPU. Hard-timeout every dispatch... if the host wedges STOP
and report BLOCKED") and this project's standing safety posture, two real
hangs plus a demonstrated carrier confound was judged sufficient reason to
STOP live-hardware iteration on this specific technique rather than
author and re-validate a THIRD carrier under continued hang risk. A
second, un-executed padding carrier (`kernels/carrier_cf_padded.metal`,
padding via extra arithmetic on `acc` alone, no new buffer reference) was
authored (disclosed) but never dispatched. **This is reported as
`UNKNOWN`, not `FALSIFIED`** -- there is no evidence the recomputed
displacements are UNSAFE, only that this experiment did not obtain a
clean signal either way, per CODEX's own stated preference for `UNKNOWN`
over unjustified certainty.

### 4.3 Generation envelope for item (d)

**CAN be generated today (unchanged from EXP-0112):** the ONE
parameterized loop+if/else->select skeleton, with trip count,
branch-selecting data, and the `icmp_pred` `cond` field independently
variable -- EXP-0112's own gated result, not re-validated or extended
here.

**CANNOT yet be generated:** a body of genuinely different LENGTH
(requiring recomputed branch displacements) -- the arithmetic to compute
the two required offsets is now independently verified correct (SS4.1),
but WHETHER a correctly-recomputed displacement executes safely on
hardware for a body the compiler never itself emitted remains `UNKNOWN`
(SS4.2), not established either way. This is consistent with, and does
not weaken, EXP-0115's own "zero forward slack" finding -- if anything it
reinforces the caution that finding already recommended: a driver must
never treat displacement arithmetic alone as sufficient proof of safety
without independent hardware confirmation, which this experiment did not
obtain.

---

## 5. Item (e) -- reg_move: bounded negative (synthesized, no new work)

Three independent experiments have each attempted to find a genuine
GPR-to-GPR move and failed, narrowing the search space each time:

- **EXP-0101** established the `reg_move_c0`/`reg_move_c1` family
  (`byte+2` low-nibble 0/1) at `src_flag=0` is producer-INDEPENDENT and
  register-PAIR-quantized -- consistent with reading a fixed, per-kernel
  preloaded/uniform-file slot, not the live GPR file.
- **EXP-0090** independently re-confirmed this (`finding_4`): `reg_move`
  does not reliably read a GPR a `falu2`/`falu2i` had just written, even
  though the source value was independently proven correct via a
  different path.
- **EXP-0113** closed EXP-0101's own last remaining named candidate --
  the "undecoded" byte0=`0x2b` instance (`reg_move_c9`) -- with a
  decisive negative: statically reproduces EXP-0087's own flagged
  instance byte-for-byte, and on hardware is ALSO producer-independent
  and register-pair-quantized, the SAME non-functional signature as its
  siblings. `isadb.py`'s disassembler calls it "undecoded" only because
  its `instr_length()` dispatcher has a narrow, unrelated length-rule gap
  (byte+2 low-nibble==9 missing a branch) -- NOT because the field
  mapping itself is wrong; db.json's own `reg_move_c9` entry is already
  correct.

**No new hardware experimentation was added by this experiment** (per the
dispatch's own instruction: "only if time permits... a bounded negative
is acceptable and already largely established"). **The safe driver rule,
unchanged: do not synthesize a GPR-to-GPR move via any currently-decoded
instruction in this ISA. Where a driver needs to relocate a live value
between registers, route it through a validated ALU identity operation
(e.g. `falu2i` with a zero immediate) instead** -- itself now part of
this experiment's own item (c)/EXP-0112's validated envelope.

---

## 6. Gate results

- `verify.py --selftest`: **PASS**, 273 checks (13 base checks + 5 corpus
  structural checks + 3 checks per case x 39 cases [group/carrier/mode
  validity, finite-oracle check for float cases, round-trip] + 2 mov_imm
  boundary-guard re-checks).
- `verify.py --seqtest`: **PASS** at all three tree states (`PRE_GPU`,
  `RUN01_PRESENT`, `RUN02_PRESENT`).
- `make_manifest.py --check`: **PASS** (14 authored files).
- `verify.py --preflight`: **PASS**.
- `verify.py --between-runs`: **PASS** -- gated ONLY on
  `authored_{code,kernel,doc}_sha256` and the case count, never live git
  `HEAD` (per SUBAGENT_BRIEF.md's standing instruction; the repository
  `HEAD` moved between pre-registration and this capture because the
  orchestrator committed sibling experiments in parallel -- expected, not
  contamination).
- `verify.py --captured`: **PASS** -- `01_results.jsonl` byte-identical
  across both runs (sha256 above); `01_timing.jsonl` correctly not
  required to match.
- No `STOP.json` in either run. No timeouts, no host wedge, `macvdmtool`
  never invoked, A18 Pro never touched. Four GPU hangs occurred during
  the DISCLOSED pre-freeze pilot phase (2 traced to item (d)'s carrier
  confound, 2 to the `mov_imm` boundary now hard-rejected by
  `isa_helpers.py`) -- zero hangs during the gated capture itself.
- `baseline.py`: **PASS** before each run -- `carrier_dag.metal`'s
  compiled length (1590B) and (order-checked) `base_slot` mapping
  (`SLOT_MEM=1` first/last-load-consistent, `SLOT_IMEM=2`, `SLOT_OUT=0`
  store) re-derived fresh, matching `families.py`'s frozen constants.

---

## 7. Updated overall generation envelope (this experiment's net addition
   to EXP-0112's own SS4)

**NEWLY CAN be generated, HW-VALIDATED, this experiment:**
- `iadd2` register-mode: `d[dst] = r0 (+/-) r_N` for N=0..15, `dst`
  freely choosable (up to ~90-95).
- `device_load` -> `device_store` direct-forward (`addr_mode=0x56`) for
  ARBITRARY, independently-chosen, CHAINABLE word offsets (via
  index-register addressing), superseding EXP-0090's own single-fixed-pair
  result.

**STILL CANNOT be generated / precisely bounded, this experiment:**
- `iadd2` register-mode for N>15, for a first operand other than r0, for
  two fully-independent operands, or CHAINED (SS1.6/1.7).
- A control-flow body of a length the compiler never itself emitted
  (displacement arithmetic verified, hardware safety `UNKNOWN`, SS4).
- `reg_move` as a GPR-to-GPR move (SS5, unchanged bounded negative).
- Everything else EXP-0112's own SS4 already named as out of scope and
  not touched here (mixed store-then-ALU-read interactions, vector-width
  ALU nodes, etc.).

**A new, previously-undocumented field boundary this experiment
found and disclosed (not one of the five named items, but load-bearing
for any future generator in this repository using `mov_imm`):**
`mov_imm`'s `imm8` field is only 7 bits load-bearing -- values 128..255
silently read back as 0 in general, and were additionally observed to
HANG the command buffer when combined with `iadd2` register-mode's own
N=0 self-read encoding. `isa_helpers.mov_imm` now hard-rejects
`imm8>=128`.

---

## 8. Limitations / honest gaps

- **Item (c)'s N range is 0..15 only** -- bounded by `mov_imm`'s own hard
  4-bit `dst` field, not by any tested failure at N=16+. A follow-up
  experiment with a different ground-truth-seeding technique (not
  `device_load`, to avoid reopening SS1.1's entanglement) is needed to
  extend this.
- **Item (c)'s chaining negative (SS1.6) is disclosed but not root-caused**
  -- the THREE compiler-natural tail-byte variants observed in SS1.1
  differential compilation (SS1.1) are a strong candidate lead (chain
  position may require a different tail byte per position) that this
  experiment did not pursue further, given the time/risk budget.
- **Item (a)'s index range is 0..7 only** -- an arbitrary choice for
  corpus size, not a discovered boundary; `mov_imm`'s own 0..127 safe
  range (this experiment's own SS Milestone 5 finding) is the honest
  outer bound of what is KNOWN safe, not independently re-tested up to
  127 for this specific mechanism.
- **Item (d) is the least resolved item in this experiment** -- see SS4.2
  for the full, disclosed reasoning for stopping rather than continuing.
  A follow-up experiment with a carrier padding technique independently
  re-verified NOT to disturb `base_slot` (this experiment's own
  `kernels/carrier_cf_padded.metal` v2, authored but never dispatched, is
  a candidate starting point) could obtain the clean signal this
  experiment did not.
- **Item (b)'s synthesis relies on EXP-0020's own "~96 register" ceiling
  claim for `iadd2`'s dst field**, which this experiment's own gated
  corpus is consistent with (dst=90 passes, dst=110 boundary-faults) but
  did not independently re-derive the exact ceiling for (untested between
  90 and 110).
- **The `iadd_reg_dst_probe110` boundary case's FIRST hardware
  observation (during pilot, before the formal gate) was itself
  `InnocentVictim`-classified** (a side effect of a temporally-nearby,
  unrelated hang from a DIFFERENT test), and only reproduced as a clean,
  isolated `CMDBUF_ERROR` after a retry once the recovery window had
  passed -- consistent with, and independently reproducing, EXP-0115's
  own documented finding that GPU error classification can misattribute a
  fault to a nearby, unrelated dispatch under back-to-back fault-provoking
  conditions. The GATED run (SS6) shows the case cleanly `CMDBUF_ERROR`ing
  on its own, not contaminated by a neighbor.

---

## 9. Clean-room provenance

```text
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: this experiment's own authored generator/harness code
  (isa_helpers.py, families.py, casematrix.py -- every instruction built
  via tools/agx-isa's own READ-ONLY isadb.assemble()), our own carrier MSL
  (kernels/carrier_dag.metal -- copied verbatim from EXP-0112's own
  OWN-SHADER compile, cited; kernels/carrier_cf_padded.metal -- our own
  authored MSL, pilot-phase only, never dispatched in its v2 form), our
  own splice+run harness (harness/case_exec.py over tools/agxtest/
  agxtest.py, tools/shdump for carrier compilation). Pilot-phase
  differential-compilation recon (work/pilot/, disclosed in PROGRESS.md,
  not part of the gated corpus) compiled our own small int-arithmetic MSL
  kernels only. Cited prior-experiment findings (EXP-0090's finding_3,
  EXP-0101's H1/H2, EXP-0113's H2, EXP-0115's branch-reach formula,
  EXP-0119, EXP-0020, db.json's own updated notes) are read-only citations
  of this project's own prior clean-room work, never independently
  re-derived here where already established.
Apple binary introspection: NONE.
Reproduction: README.md's command sequence; PROGRESS.md documents the
  disclosed pilot-phase work (`work/pilot/`) that derived the rules
  isa_helpers.py/families.py encode.
Evidence: raw/m4-20260828-run01/, raw/m4-20260828-run02/ (byte-identical
  01_results.jsonl, sha256 above), manifest.json, PROGRESS.md.
```
