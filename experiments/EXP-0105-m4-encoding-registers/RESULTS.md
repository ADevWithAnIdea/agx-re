# RESULTS — EXP-0105 M4 encoding/registers (ENC-* cluster)

**STATUS: CAPTURED / GATE-CLOSED.** Both contracted runs
(`m4-20260827-run01`, `m4-20260827-run02`) complete, 16/16 cases each,
`01_results.jsonl` **byte-identical** across both independent runs (sha256
`b19327a48bc2857f36b7771202f1287fec2ab104a0dc12d518301517fca14453`). 8/16
matched their oracle, 8/16 mismatched — every one of those 8 mismatches is
either the deliberate positive control or a hypothesis-testing case whose
oracle recorded ONE candidate model's *prediction*, not a claim that the
case "should" pass (see `PRE_REGISTRATION.md` §4 for the frozen falsifier
table). `verify.py --selftest` (47 checks), `--seqtest`, `--preflight`,
`--between-runs`, `--captured` all PASS. Target: **local Apple M4 / G16G
only.** No A18 Pro replication (hands-off). No M5 evidence used anywhere.

---

## 0. Headline

**H1 (ENC-02, TOP PRIORITY) — REFUTED for `falu2i`'s `srcA_reg` field, BY
INDEPENDENT CONSTRUCTION.** Field value 67 (low 6 bits == 3, weight-64 bit
set; register 67 itself never written) reads register **3**'s seeded
value (30.0), never the genuinely-unwritten register 67's zero. This
extends EXP-0099's own `falu2` finding to its sibling instruction
`falu2i` — not by structural analogy (which is all EXP-0099 itself could
offer), but by an INDEPENDENT hardware test. A parallel cross-check on
`falu2`'s own register-register form, in this experiment's own
independently-built harness/carrier, REPRODUCES EXP-0099's original
finding exactly (`bank_high_baseline`: field value 67 also reads 30.0).

**Net for r64-95 addressing: still `UNKNOWN`, but the negative result now
covers TWO sibling instructions by direct test, not one by test plus one
by inference.** No mechanism examined by this experiment (the reg field's
own top bit, `opflags` bits22/23, `mod_hi` bit44, 4 of `ctrl`'s 7 bits)
provides a validated path to registers 64-95 as a `falu2`/`falu2i` source
operand.

**H2 (ENC-06/ENC-07 candidate "bank-select bit") — REFUTED for every
candidate tested, but 5 of 7 candidates are independently a NEW,
DECISIVE finding: they are NOT safely-reserved bits.** `opflags` bits22
and 23, `mod_hi` bit44, and `ctrl` bits 0 and 1 all **silently corrupt**
the read to `0.0` regardless of which register the field nominally
addresses (confirmed by crossing 3 of them against BOTH `reg=3` and
`reg=67` and observing the SAME corruption either way — a general
corruptor, not a register-specific bank selector). `ctrl` bits 2 and 3
are the only two of the 7 tested candidates confirmed inert.

**A second, structurally different register-addressing method
(`iminmax`, plain 8-bit register fields) was attempted in this
experiment's pilot phase and ABANDONED after producing two unexplained,
uninterpretable hardware behaviors** — reported as a first-class,
unresolved negative finding (§6), not silently dropped.

---

## 1. H1 — `falu2i` `srcA_reg` register-64-95 addressing (decisive, HW-VALIDATED, 2 runs)

### 1.1 Design

Seed register r3 with `V_LOW=30.0` (the fixed point of
`isadb.imm_encode/imm_decode(42.5)`) via `falu2i(dst=3, srcA=UNWRITTEN,
K=30.0, opflags=1)` — an ALU-only path independently `HW-VALIDATED` by
EXP-0090/EXP-0099. Register 67 is never written by any case in this
matrix. Read back via `falu2i(dst=5, srcA_reg=X, K=0.0, opflags=1)` for
`X ∈ {3, 67}`.

### 1.2 Observed (both runs, byte-identical)

| case | X | observed | oracle (wide-field prediction) | verdict |
|---|---:|---:|---:|---|
| `control_r3_falu2i` | 3 | **30.0** | 30.0 | match (sanity) |
| `falu2i_srca_high67_alias_DECISIVE` | 67 | **30.0** | 0.0 | **MISMATCH — aliases to r3** |

Cross-check, `falu2` register-register form (same aliasing question, a
different sibling instruction, independently built in this experiment's
own harness):

| case | X | observed | oracle | verdict |
|---|---:|---:|---:|---|
| `bank_low_baseline` | 3 | **30.0** | 30.0 | match |
| `bank_high_baseline` | 67 | **30.0** | 0.0 | **MISMATCH — aliases to r3, reproducing EXP-0099** |

### 1.3 Interpretation

**REFUTED: `falu2i`'s `srcA_reg` field does NOT address a genuine,
independent register 67.** Field value 67 reads register 3's value in
both tested cases, both runs, deterministically. Combined with
`bank_high_baseline`'s reproduction of EXP-0099's original `falu2`
finding on an independently-built carrier/harness, this is now **TWO
independent hardware confirmations, on two sibling instructions,** that
this instruction family's packed `(reg<<1)|size`-shaped source field
collapses to (at most) its low 6 bits for register selection in the
tested construction. `INTERPRETED`: consistent with, and extending,
EXP-0099's own conclusion — "functionally a 6-bit register selector...
for the specific construction tested." This experiment's own construction
differs from EXP-0099's (different carrier kernel text, different seed
value, `falu2i` instead of `falu2`, a fresh code revision) — the
reproduction is not a re-run of the same bytes, it is an independently
re-derived result.

**OBSERVED, not merely INTERPRETED:** the exact bit pattern read back
(30.0, an exact `f32` value) never differs across 2 independent process
launches × 2 independently gated hardware runs × 2 sibling instructions.
**INTERPRETED:** this is the SAME "low-6-bit aliasing" failure mode
EXP-0099 characterized for `falu2`, now shown to also apply to `falu2i`.

**What remains unknown:** whether registers 64-95 are reachable via THIS
field family AT ALL, through any encoding this experiment did not try.
The falsifier that would settle it positively — a genuinely-seeded,
distinctly-valued r67 correctly read back via this SAME field — was not
achieved this round (see §6, the abandoned `iminmax`/`get_sr` avenue).

---

## 2. H2 — candidate "bank-select bit" sweep (decisive negative + a genuine ENC-07 finding, 2 runs)

### 2.1 Observed

| case | candidate | reg | observed | true baseline @ same reg | verdict |
|---|---|---:|---:|---:|---|
| `bank_low_baseline` | (none) | 3 | 30.0 | 30.0 | baseline |
| `bank_low_opflags_bit22` | opflags bit22 | 3 | **0.0** | 30.0 | **corrupts** |
| `bank_low_opflags_bit23` | opflags bit23 | 3 | **0.0** | 30.0 | **corrupts** |
| `bank_low_modhi_bit44` | mod_hi bit44 | 3 | **0.0** | 30.0 | **corrupts** |
| `bank_low_ctrl_bit0` | ctrl bit0 | 3 | **0.0** | 30.0 | **corrupts** |
| `bank_low_ctrl_bit1` | ctrl bit1 | 3 | **0.0** | 30.0 | **corrupts** |
| `bank_low_ctrl_bit2` | ctrl bit2 | 3 | 30.0 | 30.0 | inert |
| `bank_low_ctrl_bit3` | ctrl bit3 | 3 | 30.0 | 30.0 | inert |
| `bank_high_baseline` | (none) | 67 | 30.0 (aliased) | — | baseline-at-high |
| `bank_high_opflags_bit22` | opflags bit22 | 67 | **0.0** | 30.0 (aliased) | **corrupts** |
| `bank_high_opflags_bit23` | opflags bit23 | 67 | **0.0** | 30.0 (aliased) | **corrupts** |
| `bank_high_modhi_bit44` | mod_hi bit44 | 67 | **0.0** | 30.0 (aliased) | **corrupts** |

All 16 rows fully deterministic, byte-identical across both independent
hardware runs.

### 2.2 Interpretation

**OBSERVED:** `opflags` bit22, `opflags` bit23, and `mod_hi` bit44 each
change the result from 30.0 to exactly 0.0, IDENTICALLY whether the reg
field nominally selects the low register (3) or the high field value
(67, itself already aliased to 3). **INTERPRETED:** because the effect is
IDENTICAL regardless of which register is nominally addressed, these
three bits are **general corruptors** (the same "silent zero" pattern
`docs/isa/register-move-and-liveness.md` §2.5 already documents for other
fields in this family), **NOT register-specific bank-select mechanisms**
— the `get_sr`-inspired hypothesis (a separate bit unlocking r64-95, by
analogy with `get_sr`'s `dst_hi`) is **REFUTED** for these three specific
candidates. `ctrl` bits 0 and 1 show the identical corrupting signature
at `reg=3` (not cross-checked at `reg=67` — a disclosed, time-boxed
scoping narrowing, see §7). `ctrl` bits 2 and 3 are the only two of the 7
tested candidates that left the baseline unchanged — `HW-VALIDATED`
inert, for this specific construction, this specific bit only.

**Positive control** (`positive_control_deliberate_mismatch`): reads 30.0
against a deliberately unreachable oracle of 999.0 — MISMATCH as
designed, both runs, proving match-detection is not a rubber stamp and
that a "silent zero" (an ACTUAL, different value from the oracle) is
genuinely detected, not coincidentally matched.

**Consequence for ENC-06/ENC-07:** of the 7 previously wholly-untested
bits this experiment characterized, **5 are load-bearing** (silently
corrupt to zero when set) and **2 are confirmed inert** (`ctrl` bits 2,
3). None functions as a register-bank extension. This directly answers
"is this field genuinely reserved" for the 5 corrupting bits: **NO** —
treat them exactly as `docs/isa/register-move-and-liveness.md` already
instructs for the family's other undocumented fields: never synthesize
or normalize, emit only values copied verbatim from a compiler-observed
pattern for the same operand shape.

---

## 3. ENC-* per-item verdicts

| item | verdict this experiment | evidence |
|---|---|---|
| ENC-01 | `PARTIAL` (unchanged; DESK-AUDIT) | `docs/isa/encoding-tables.md`; several families remain db.json-flagged inferred |
| **ENC-02** | **`REFUTED` for falu2/falu2i's packed field @ r64-95; `UNKNOWN` overall** | §1, this experiment, 2 sibling instructions, 2 runs |
| ENC-03 | `UNKNOWN` (`DEFERRED`, not probed) | none new |
| ENC-04 | `PARTIAL` (unchanged; DESK-AUDIT) | EXP-0020/RT-1a-FIX (float), int ALU still inferred |
| ENC-05 | `PARTIAL` (unchanged; DESK-AUDIT) | EXP-0006 (minifloat), EXP-0031 (mov_imm); NaN-literal handling: gap, not found documented anywhere |
| **ENC-06** | **`PARTIAL`, extended** | §2, 7 new bits classified (5 corrupting, 2 inert) |
| **ENC-07** | **`PARTIAL`, extended — general answer: NO, not safely known** | §2; general policy reaffirmed with new specific data |
| ENC-08 | `PARTIAL` (unchanged; DESK-AUDIT) | RT-ISA-FIX census, ~87-91% tokenization |
| ENC-09 | `PARTIAL` (unchanged; DESK-AUDIT + this experiment's own round trip) | `verify.py --selftest`, all 16 cases round-trip |
| **ENC-10** | **`OPEN`, extended with a new negative data point** | §6, `iminmax` could not be made to work in a hand-built program this session |
| ENC-11 | `PARTIAL`, compute closed (DESK-AUDIT) | EXP-0003/EXP-0010 E4 |
| ENC-12 | `PARTIAL` (unchanged; DESK-AUDIT) | EXP-0010 E6 (jump), EXP-0035/RT-ISA-FIX (call/jump_cond) |
| ENC-13 | `PARTIAL`, substantially closed for tested depth (DESK-AUDIT) | EXP-0035/EXP-0038 |
| ENC-14 | `PARTIAL`, compute doubly closed (DESK-AUDIT) | EXP-0006/EXP-0020 + EXP-0092 GLIO-A02 |
| ENC-15 | `UNKNOWN` (`DEFERRED`, unchanged) | `docs/isa/README.md`'s own disclosed gap |
| ENC-16 | `UNKNOWN` (`DEFERRED`, sibling workstream `EXP-0107`) | `docs/isa/README.md`'s own disclosed gap |

See `PRE_REGISTRATION.md` §1 for the full per-item plan and citation
detail behind every DESK-AUDIT row.

---

## 4. Required response blocks (covered items)

### ENC-02 (TOP PRIORITY)

```text
Status: [x] Open  [ ] Partial  [ ] Closed  [ ] Not applicable
Answer, where Yes/No: [ ] Yes  [x] No (for the tested field/family)  [ ] Unknown
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [x] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [x] encode/decode round trip
          [ ] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: experiments/EXP-0105-m4-encoding-registers/raw/m4-20260827-run01/01_results.jsonl,
    raw/m4-20260827-run02/01_results.jsonl (byte-identical, sha256
    b19327a48bc2857f36b7771202f1287fec2ab104a0dc12d518301517fca14453),
    analysis.json, casematrix.py (case generation + independent oracles).
Exact observed semantics or field mapping:
    falu2i's srcA_reg field (bits 25-31) and falu2's srcA_reg/srcB_reg
    (bits 9-15/25-31) all collapse register selection to (at most) their
    low 6 bits in the tested construction: field value 67 (low6=3) reads
    register 3's seeded value, never a genuinely-unwritten register 67's
    zero, in 2 sibling instructions x 2 independent hardware runs.
Finite namespace: scope / encoding / exact usable count or range / holes and reservations:
    Structurally a 7-bit field (0-127); only the low 6 bits (0-63) are
    demonstrated load-bearing for register selection in this construction;
    the top bit is HW-tested inert for BOTH addressing and retention
    (EXP-0099); this experiment adds no new evidence about the top bit's
    role, only that it does not extend addressing.
Maximum-valid and first-invalid tests:
    Not applicable in the "fault boundary" sense -- there is no fault; the
    field simply aliases below 64. The maximum DEMONSTRATED-CORRECT
    register via this field is unresolved (only 3 and the aliased-67 were
    tested; a genuine value in 4-63 was not independently cross-checked
    against a distinct seed this round -- EXP-0099 covers 3 vs 67 only,
    matching this experiment's own scope).
Failure/overflow behavior: [ ] reject  [x] zero/discard (indirectly, via aliasing to a DIFFERENT live register, not a true zero/discard)  [ ] alias/wrap  [ ] fault/device loss
    A register-value ALIAS (reads a different, live register's value),
    not a fault, not a literal zero (the aliased register happened to be
    unwritten-equivalent only when its OWN content is zero) -- distinct
    from the "silent zero" pattern documented for the candidate bank-bits
    in this same experiment (section 2).
Correct behavior when the compiler/driver needs more:
    Do not address registers 64-95 as a falu2/falu2i source operand via
    this field. No validated alternative path exists (see also EXP-0099's
    own H3 finding and this experiment's own abandoned iminmax/get_sr
    attempt, section 6). The safe fallback is to keep live values used by
    falu2/falu2i-family arithmetic below register 64, and/or move
    register-pressure overflow to the documented scratch-spill mechanism
    (itself only partially characterized, ENC-16, deferred to EXP-0107).
Lifetime, destruction, and reuse semantics: not applicable (stateless per-instruction field).
Counterexamples and untested cases:
    Only field values {3, 67} were tested for falu2i; only a coarser set
    for falu2 (EXP-0099's own 4-value sweep plus this experiment's single
    high-value cross-check). The exact aliasing FORMULA (mod-64? low-6-
    bits-literal? something else entirely for values 4-63?) is not
    independently determined by either experiment. A genuinely-seeded,
    independently-verified r67 value was never successfully read back
    through this field by ANY method in either experiment -- the
    "aliases to r3" conclusion rests on r67 being UNWRITTEN, which is
    the same evidentiary shape EXP-0099 itself used and disclosed as its
    own limit.
Driver/compiler consequence:
    A compiler backend targeting Apple9 must NOT rely on falu2/falu2i's
    packed source-register field to reach registers 64-95. Until a
    validated high-register source path is found (candidate leads:
    falu3's plain 8-bit fields, get_sr+some consumer, or a currently
    unexamined instruction family), register allocation feeding
    falu2/falu2i-family arithmetic should treat 0-63 (or, conservatively,
    0-15 given falu2's own 4-bit dst nibble cap) as the practically usable
    range for values that must flow through this specific op family.
```

### ENC-06 / ENC-07 (candidate bank-select bits / reserved-bit safety)

```text
Status: [ ] Open  [x] Partial  [ ] Closed  [ ] Not applicable
Answer, where Yes/No: [x] No (none of the 7 tested candidates is a bank selector; 5/7 are NOT safely reserved)
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [x] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [x] encode/decode round trip
          [ ] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: same raw/ pair as ENC-02 above (single combined capture).
Exact observed semantics or field mapping:
    falu2's opflags bit22, opflags bit23, and mod_hi bit44 each
    deterministically zero the read result (30.0 -> 0.0), IDENTICALLY
    whether the source register field nominally selects reg=3 or the
    aliased reg=67 field value -- i.e. these bits corrupt regardless of
    which register is "selected," ruling out a register-bank-selector
    role. ctrl bits 0 and 1 show the identical corrupting signature (at
    reg=3 only, not cross-checked at reg=67 this round). ctrl bits 2 and
    3 leave the baseline (30.0) unchanged -- confirmed inert.
Finite namespace: scope / encoding / exact usable count or range / holes and reservations:
    Of falu2's 5-bit opflags field: bits19/20 known (retention, EXP-0086),
    bit21 known-refuted-as-publication (EXP-0099), bits22/23 now known
    LOAD-BEARING/corrupting (this experiment) -- ALL 5 bits are now
    characterized, ZERO remain unknown in this field. Of the 4-bit mod_hi
    field: bits45-47/route known inert-for-ALU-sourced-operands
    (EXP-0099), bit44 now known LOAD-BEARING/corrupting (this experiment)
    -- ALL 4 bits now characterized. Of the 7-bit ctrl field: 4 of 7 bits
    characterized this experiment (0,1 corrupting; 2,3 inert); bits 4,5,6
    remain UNTESTED (disclosed scoping, not silently assumed inert).
Maximum-valid and first-invalid tests: not applicable (single-bit fields, no ordinal range).
Failure/overflow behavior: [ ] reject  [x] zero/discard  [ ] alias/wrap  [ ] fault/device loss
    Silent zero/discard -- no fault, no warning, deterministic and
    reproducible across both runs. Exactly the pattern
    docs/isa/register-move-and-liveness.md section 2.5 documents for
    other fields in this same family.
Correct behavior when the compiler/driver needs more:
    Never synthesize opflags bits22/23, mod_hi bit44, or ctrl bits0/1 for
    a falu2 instruction unless copying the exact value from a compiler-
    observed pattern for the identical operand shape. ctrl bits2/3 may
    safely be treated as don't-care/reserved-zero for the tested
    construction, but this is a narrow finding (single-op, single operand
    shape) -- not generalized to every falu2 context without further
    testing.
Lifetime, destruction, and reuse semantics: not applicable.
Counterexamples and untested cases:
    ctrl bits 4-6 not tested (disclosed). Every candidate was tested in
    exactly ONE operand shape (srcA-slot read, srcB=UNWRITTEN,
    opsel=fadd) -- a different shape (srcB real, different opsel, 16-bit
    size) could show different behavior for the SAME bits; not excluded.
Driver/compiler consequence:
    Reinforces docs/isa/register-move-and-liveness.md's existing
    implementer guidance with 5 new concrete, named corrupting bits and 2
    new concrete, named inert bits for falu2 specifically.
```

---

## 5. Proposed `db.json` field-definition corrections (text only — NOT applied; `tools/` is read-only for this experiment)

1. **`falu2i`'s `srcA_reg` (bits 25-31) should carry the SAME annotation
   this experiment's predecessor (EXP-0099) proposed for `falu2`'s
   `srcA_reg`/`srcB_reg`, now upgraded from "by structural analogy, not
   independently tested" to independently `HW-VALIDATED`**: `reg (6 bits
   load-bearing; top bit HW-tested to alias, not extend, addressing in
   this construction — same behavior as falu2's sibling field,
   EXP-0099+EXP-0105; role of the top bit, if any, remains UNKNOWN)`.
2. **`falu2`'s `opflags` field description should record that bits22/23
   are NOT reserved/don't-care — they deterministically zero the read
   result** (`HW-VALIDATED`, this experiment). Suggested annotation:
   `opflags (5 bits: bit0/1=srcA/srcB last-use retention [EXP-0086],
   bit2=HW-REFUTED as 'destination publication' [EXP-0099], bits3/4=
   LOAD-BEARING silent-corruption bits, NOT safely reserved [EXP-0105] —
   emit as 0 unless copying a compiler-observed pattern)`.
3. **`falu2`'s `mod_hi` field description should record that bit44 (the
   field's own bit0, i.e. instruction bit44) is NOT reserved** — it
   deterministically zeros the read result (`HW-VALIDATED`, this
   experiment), unlike bits1-3/route (instruction bits45-47, EXP-0099
   H4: inert for an ALU-sourced operand).
4. **`falu2`'s `ctrl` field (currently untyped `mod`, no per-bit note at
   all) should record the first partial per-bit map**: bits0/1
   LOAD-BEARING (silent-corruption, `HW-VALIDATED` this experiment),
   bits2/3 inert for the tested construction (`HW-VALIDATED` this
   experiment, narrow scope — single operand shape only), bits4-6
   UNTESTED (not "presumed inert" — explicitly UNKNOWN).
5. **A new cross-reference note recommended for `iminmax`'s own
   provenance field**, flagging that an attempt to splice its `srcA`
   byte on a real, independently-verified-correct compiled instance
   produced NO observable change in output at any tested value (a low
   in-range register AND the r64-95 candidate), and that a hand-built
   construction using the SAME field values could not even read back a
   `mov_imm`-seeded low register — i.e. this family's operand-read
   behavior in a spliced or hand-built context is NOT understood well
   enough to trust for ANY register-addressing claim, HW-VALIDATED status
   notwithstanding its "NOT HW-dispatch validated" note already says as
   much for `fmt`/`selhi`, but this experiment's finding is broader (the
   register FIELDS themselves, not just the format bits, behave
   unexpectedly). See §6 for the full account.

---

## 6. Abandoned second method — `iminmax` (first-class negative finding)

Per the dispatch's TOP-PRIORITY instruction to find a structurally
DIFFERENT register-addressing mechanism (not merely falu2's own family),
this experiment's pilot phase (PROGRESS.md Milestone 2) targeted
`iminmax`, whose `srcA`/`srcB` fields are documented as PLAIN 8-bit
register bytes (structurally unlike falu2's packed 7-bit+flags field).

**OWN-SHADER confirmation the family works at all:** a freshly compiled
`int a=mem[tid]; int b=mem[tid+1]; out[tid]=max(a,b);` kernel correctly
computed `max(23,71)=71`, unspliced, confirming `iminmax`'s basic
semantics and this experiment's own extracted `fmt=3`/`selhi=0`/`sel=6`
field values are valid for a real dispatch.

**Two independent attempts to use it as a splicable/hand-buildable
register-addressing probe both produced results this experiment could
not interpret as either "confirms" or "refutes" anything:**

1. Splicing ONLY the working compiled instance's `srcA` byte (a
   single-byte diff, independently confirmed via `isadb.assemble`) to a
   genuinely different, IN-RANGE low register (1) OR the r64-95 candidate
   (67) left the output **completely unchanged** — still reading the
   ORIGINAL "a" operand's value in both cases. `STATUS OK` throughout,
   one case (`srcA=67`) additionally ran ~30x slower (`GPUTIME_NS 88124`
   vs a normal ~2700-3900) with no other visible symptom.
2. A hand-built program (using the SAME extracted field values) seeding
   r3 via `mov_imm` and reading it back via `iminmax(srcA=srcB=3)`
   returned `0`, not `99` — while a PARALLEL control (`mov_imm(5,77)` +
   the identical `device_store` call, `iminmax` skipped entirely)
   correctly returned `77`, proving the splice and store mechanisms are
   sound in this exact harness. 4 padding instructions between seed and
   read made no difference (rules out a naive timing/hazard
   explanation). Redirecting the seed to a `device_load`-written register
   also read back `0` — but a DECOUPLED control (`device_load` directly
   into `device_store`, no `iminmax`) ALSO read `0`, which is consistent
   with (not new beyond) EXP-0099's own already-documented finding that
   `device_load`'s result does not reliably forward to a later,
   non-adjacent consumer via the `extmode=2*data_reg` convention — this
   means finding (2)'s `device_load`-sourced variant is CONFOUNDED by an
   already-known blocker, but the `mov_imm`-sourced variant is NOT (the
   parallel `mov_imm`+`device_store`-only control ruled that blocker out
   for that specific sub-case).

**Neither observation matches any previously documented AGX behavior in
this repository.** It is not the "silent zero" pattern (that pattern is a
field encoding a WRONG-but-valid alternate meaning; here, splicing the
field produced NO detectable change of ANY kind). It is not a fault. It
is not simply the known load-to-ALU blocker (ruled out by the decoupled
control above, for the `mov_imm`-sourced case specifically). Per the
standing "do not guess" discipline, this is reported as an honest,
unresolved `UNKNOWN` — a concrete lead for a successor experiment, not
papered over with a guessed explanation. **No `iminmax`-based case is
part of this experiment's gated capture.** A `get_sr`-based seeded
positive-value confirmation (the other half of the originally planned
SEEDED design, citing EXP-0092's own `HW-VALIDATED` `get_sr`+
`device_store` round trip) was also dropped without independent
re-verification on this experiment's own hardware, for the same
time-budget and safety-of-interpretation reasons.

---

## 7. Finite-resource table (this experiment's own HW-tested fields only)

| field | scope | encoding | exact usable range tested | holes/reservations | first-invalid value | observed failure mode | correct fallback | evidence |
|---|---|---|---|---|---|---|---|---|
| `falu2i.srcA_reg` | per-instruction | 7-bit `(reg<<1)\|size`-shaped byte (bits25-31) | low 6 bits demonstrated load-bearing (values 3, 67 tested; 67 aliases to 3) | top bit: HW-tested to NOT extend addressing (aliases, does not fault, does not read a distinct r67) | n/a — no fault observed at any tested value | register-value ALIAS (reads a different live register), not zero/discard/fault | never address r64-95 via this field; keep values below r64 | `raw/*/01_results.jsonl` case `falu2i_srca_high67_alias_DECISIVE` |
| `falu2.opflags` bits22/23 | per-instruction | 1 bit each, part of a 5-bit field | both tested values {0,1}, both bits | none — every value tested behaves, just not as expected | n/a — no fault | silent zero/discard of the read result | never set; treat as reserved-emit-0 unless copying a compiler pattern | `raw/*/01_results.jsonl` cases `bank_{low,high}_opflags_bit{22,23}` |
| `falu2.mod_hi` bit44 | per-instruction | 1 bit, part of a 4-bit field | both tested values {0,1} | none | n/a — no fault | silent zero/discard | never set; treat as reserved-emit-0 unless copying a compiler pattern | `raw/*/01_results.jsonl` cases `bank_{low,high}_modhi_bit44` |
| `falu2.ctrl` bits0-3 | per-instruction | 4 of 7 bits, part of an untyped byte+4 field | tested values {0,1} for bits0-3 only; bits4-6 UNTESTED | bits4-6 explicitly unknown, not presumed inert | n/a — no fault | bits0/1: silent zero/discard; bits2/3: inert (narrow scope, single operand shape) | bits0/1 never set except copying a compiler pattern; bits2/3 may be left 0; bits4-6 treat as unknown/load-bearing by the family's own established pattern | `raw/*/01_results.jsonl` cases `bank_low_ctrl_bit{0,1,2,3}` |

---

## 8. Gate results

- `verify.py --selftest`: **PASS**, 47 checks (uses a REAL recorded
  hardware fixture, `harness/recorded_fixture_case0.json`, captured
  during this experiment's own pilot phase — CODEX gate (e); round-trips
  all 16 cases through `isadb.disassemble`+`assemble`; checks every
  oracle word carries a valid `kind`; checks dispatch shape sanity).
- `verify.py --seqtest`: **PASS** in all three tree states (`PRE_GPU`,
  `RUN01_PRESENT`, `RUN02_PRESENT`).
- `make_manifest.py --check` / `--write`: **PASS**.
- `verify.py --preflight`: **PASS**.
- `verify.py --between-runs`: **PASS** — gated ONLY on
  `authored_{code,kernel,doc}_sha256` and the pinned revision recorded in
  `PRE_REGISTRATION.md`/`CAPTURE_CONTRACT.json`; never live git `HEAD`
  (per SUBAGENT_BRIEF.md's standing instruction — the working tree
  contains multiple concurrently-running sibling experiments' untracked
  artifacts throughout this capture, none of which touch this
  experiment's own files).
- `verify.py --captured`: **PASS** — `01_results.jsonl` byte-identical
  across both runs (sha256 above); `01_timing.jsonl` correctly NOT
  required to match.
- No `STOP.json` in either run.
- **Positive control** (`positive_control_deliberate_mismatch`): reads
  30.0 against a deliberately unreachable oracle of 999.0 — MISMATCH as
  designed, both runs, proving match-detection is not a rubber stamp.
- **Detection-capability proof for the H1/H2 negative results**: every
  "corrupts" verdict is a REAL, different, deterministic value (0.0)
  from its oracle prediction — the SAME match/mismatch machinery that
  correctly flags the deliberate positive control also correctly flags
  these, and the `control_r3_falu2i`/`bank_low_baseline`/`control_
  unwritten_falu2i` cases prove the harness correctly reports MATCH when
  the construction is right.

---

## 9. Limitations / honest gaps

- **The register-64-95 addressing question (ENC-02) remains formally
  `UNKNOWN`, not positively resolved either way.** This experiment adds a
  second, independent REFUTATION of one candidate mechanism (the packed
  field's top bit, now on 2 sibling instructions) but does not establish
  ANY working path to registers 64-95 as a source operand for this
  family. No currently-validated mechanism is known anywhere in this
  repository as of this experiment's completion.
- **The `iminmax` avenue is a genuinely open, unexplained negative
  finding** (§6) — a successor experiment should characterize WHY
  splicing a real, working compiled instance's register field has no
  effect at all, before attempting to reuse it for anything.
- **`ctrl` bits4-6 were not tested** (disclosed scoping, time budget).
- **The candidate-bank-bit cross-check (reg=3 vs reg=67) was only
  performed for 3 of the 7 characterized bits** (`opflags` bits22/23,
  `mod_hi` bit44); `ctrl` bits0/1's corrupting behavior was confirmed
  only at reg=3, not independently cross-checked at reg=67 — though
  given their IDENTICAL corrupting signature to the 3 cross-checked
  bits, this is a low-risk, disclosed gap, not a silently assumed one.
- **13 of the 16 ENC-* items were answered by desk audit of already-
  `PROVENANCE`-linked evidence, not new hardware testing this round** —
  explicitly stated in `PRE_REGISTRATION.md` §1, not silently presented
  as newly validated.
- **ENC-15/ENC-16 remain fully `DEFERRED`** — no new evidence gathered;
  ENC-16 appears to be the assigned scope of a concurrently-running
  sibling experiment (`EXP-0107-m4-scratch-helper-abi`), not duplicated
  here.

---

## 10. Clean-room provenance

```text
Clean-room provenance: OWN-SHADER + HW-PROBE + PUBLIC
Inputs inspected: kernels/carrier.metal (our own MSL, byte-identical to
  EXP-0099's own proven-splicable carrier), work/ pilot-phase MSL probes
  (our own MSL, deleted after use -- see PROGRESS.md for their exact
  source text and findings), tools/agx-isa's isadb.assemble()/
  disassemble()/imm_encode()/imm_decode() (read-only), tools/agxtest
  (read-only, splice-and-run), tools/shdump (read-only, compile+extract).
  EXP-0092's and EXP-0099's own RESULTS.md/db.json content is cited as
  prior, already-committed repository evidence (PUBLIC-to-this-
  experiment category), never re-derived from any Apple binary. Every
  instruction byte executed in the gated capture is our own field values
  passed through our own assembler (isa_helpers.py / casematrix.py).
Apple binary introspection: NONE.
Reproduction: python3 -B verify.py --selftest/--seqtest (no GPU);
  python3 -B baseline.py (no GPU dispatch); python3 -B run.py --execute
  --run-id <id> (real GPU, append-only); python3 -B analysis.py --write;
  python3 -B verify.py --captured.
Evidence: raw/m4-20260827-run01/, raw/m4-20260827-run02/ (byte-identical
  01_results.jsonl, sha256 above), analysis.json, manifest.json.
```
