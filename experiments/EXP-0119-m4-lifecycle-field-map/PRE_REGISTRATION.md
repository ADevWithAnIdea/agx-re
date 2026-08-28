# PRE_REGISTRATION — EXP-0119 M4 lifecycle field map

**Pinned repository revision (per SUBAGENT_BRIEF.md — record and compare
against THIS value, never live `HEAD`):** `72c2dde8afd896e384afa20050bdd040f657ca78`
(tree dirty with unrelated sibling-experiment untracked artifacts at pin
time — expected, not a contamination signal per SUBAGENT_BRIEF.md).

Target: **local Apple M4 / G16G only.** macOS 26.6.2 (build 25G82), Metal 4,
`Mac16,10`. No A18 Pro (hands-off, standing directive). No M5 evidence used
anywhere.

**Renumbering note:** this experiment was originally dispatched as
EXP-0118; the coordinator reassigned it to EXP-0119 mid-dispatch because
another concurrent agent had already claimed EXP-0118 for an unrelated
partial-render workload. No capture had occurred under the old number; the
rename is a directory move only, contracted here under the number this
experiment actually captures under.

## 0. Origin: an extensive informal pilot phase, disclosed up front

Per the standing pattern of every predecessor in this arc (EXP-0086/89/90/99
all had an informal pilot before their frozen capture), this contract is
written **after** a long pilot phase on real M4 hardware — not before any
hardware contact. The pilot is summarized here in full because it changed
several design decisions and caught real bugs that would otherwise have
produced a wrong, gated oracle. See `PROGRESS.md` for the full chronological
log; the load-bearing findings are:

1. **A length/framing discovery, not previously documented anywhere in this
   repository.** `isadb.instr_length`'s rule for the ENTIRE low-nibble-9
   float-ALU group (2-source AND 3-source alike) is `6 + 2*(byte+4 & 0x3)`
   — i.e. the `ctrl`/`ctrl_lo` field's **own low 2 bits are the
   instruction-LENGTH selector**, not a free semantic bit. Constructing
   `falu2_ext`/`falu3_srcmod12`/`falu_srcmod12b` with `ctrl=0` (the natural
   default) silently reassembled as a plain 6-byte `falu2`/`falu2i` on
   round-trip — caught by this experiment's own `assert_round_trip` +
   single-instruction-count assertion, before any hardware run. This
   **reframes EXP-0089's own finding** that `ctrl`/`ctrl_lo` bits 0/1 are
   "always dangerous" and the sole source of every cross-run
   non-deterministic case in that experiment: flipping them does not
   corrupt a semantic field, it **reclassifies the instruction's own
   length**, desyncing every subsequent byte in the program — a clean,
   mechanical explanation for both the fault-heavy and the
   boundary-dependent-nondeterministic character of that result, not
   previously identified. `isa_helpers.py`'s new builders fix the affected
   low 2 bits to the correct value for the intended length and expose only
   the field's semantically-free upper 5 bits (`ctrl_hi5`).
2. **`falu3_srcmod12`'s `opsel` field cannot reach `opsel=4`/`5`
   ("fadd"/"fmul")** — its match condition forces instruction bit17=1,
   which overlaps `opsel`'s own bit range; `assemble()` composes match-
   constant bits and field bits with OR, never AND/clear, so the field's
   own bit17 is always forced to 1 regardless of what is requested (an
   early version of the builder requested `opsel=4` and silently got
   `opsel=6` "fma" back). Caught by the same round-trip self-check. The
   builder no longer exposes `op` for this family; this experiment never
   reads this family's own computed result (only whether a later,
   independent reader's read of srcA/srcB survives), so the specific
   reachable opsel value is immaterial to what is tested.
3. **The minifloat immediate codec (`isadb.imm_encode`/`imm_decode`,
   EXP-0006) clamps/rounds hard above 16** (odd integers 17-31 round down
   to the nearest even value; everything ≥32 clamps to 30.0). An early
   design picked `K3=99.0` as a "rewrite" value clearly distinct from the
   seed `V=30.0` — `imm_value(99.0)` silently returns exactly `30.0`, so
   the "rewrite" instruction was byte-identical in effect to a no-op
   re-seed, and a real-hardware run of that shape gave a result
   indistinguishable from "the rewrite never happened" purely by
   coincidence. Caught by directly printing `imm_value()` for every
   candidate constant before trusting an oracle built on it. The frozen
   immediate palette (`V=30, K2=20, K3=8, K4=12`) is independently
   verified to be **exact, non-clamped fixed points** (see `casematrix.py`
   module docstring).
4. **`device_store`'s `idx_off` is in units of 4 WORDS (16 bytes)**
   (HW-VALIDATED EXP-0090, re-confirmed this experiment's own pilot) — an
   early version of this experiment's own `store(word_index, reg)` helper
   passed the WORD index straight through as `idx_off`, silently writing
   out of the declared 16-word output-buffer bounds (`idx_off=4` -> word16)
   and leaving the intended slot at its zero-initialized default. Every
   affected case ran with `STATUS OK` and a plausible-looking all-zero
   result that would have read as "corrupted to zero" — indistinguishable
   from a real finding without independently re-deriving the expected
   value. Caught by comparing against this experiment's own earlier
   ad-hoc pilot runs (which used `idx_off` directly and gave different,
   internally-inconsistent numbers) and fixed with an explicit assertion
   in the helper.
5. **`lit17_unpack.metal`/`lit17_cvt.metal` (reused verbatim from EXP-0089)
   declare `buffer(0)` as INPUT and `buffer(1)` as OUTPUT — the OPPOSITE
   of `carrier.metal`'s `buffer(0)`=output/`buffer(1)`=input.** An early
   version of `case_exec.py` hardcoded carrier's buffer order for every
   kernel; every MODE B (splice-into-compiled-kernel) case ran with
   `STATUS OK` and read back all-zero output (because it was reading the
   INPUT buffer's slot, never written by the kernel). Fixed with an
   explicit per-kernel `KERNEL_IO` table in `casematrix.py`
   (`out_buf`/`in_buf`/`in_pack`/`in_vals`), and re-verified against
   EXP-0089's own recorded baseline oracle strings ("0.50000763,
   6.0000305" / "1244, 1254") byte-for-byte.
6. **`falu_srcmod12b`'s `opsel` field is UNTYPED (`mod`, not a typed
   opcode enum) — unlike `falu2_ext`'s.** An early version of this
   experiment's H2 group copied falu2/falu2_ext's convention
   (`opsel=4`="fadd") uncritically. On real hardware, `opsel=4` is **not**
   a valid encoding for this specific family: it silently corrupted an
   entirely UNRELATED, independently-seeded register (`r6`, never
   referenced by the instruction) that a later, unrelated reader then
   read back as zero — a qualitatively different and much broader effect
   than a srcA-retention bug. A full pilot sweep of `opsel_mod` 0-7 found
   `opsel_mod=0` alone gives a clean move-like own-result AND leaves an
   unrelated register intact; with `opsel_mod=0` the opflags contract is
   then **pilot-confirmed byte-for-byte identical to falu2's own** (bit0
   corrupts a later reader, bits1-2 do not). H2's `falu_srcmod12b` group
   uses `opsel_mod=0` throughout for exactly this reason — a disclosed,
   evidence-driven choice, not an assumption.
7. Every one of the 77 frozen cases below (all but the one deliberate
   hang-probe, tested separately with extra isolation) was run once,
   informally, non-gated, in `work/full_smoke_run/` (deleted before the
   gated capture; `work/` is never part of `raw/`) via `work/full_smoke.py`
   — **every one returned `STATUS OK`** (zero faults, zero timeouts) and
   every case with a real (non-`None`) oracle key **matched**, except the
   two designed-to-mismatch positive controls
   (`h4_regfile_corrupt_*` — a genuine, informative REFUTATION of the
   "not-forwarded" hypothesis, see H4 below — and
   `positive_control_deliberate_mismatch`, deliberately wrong by design).
   This is the standing NON-RECORDED smoke gate's own single-case check
   generalized to the WHOLE matrix during pre-registration, not a
   substitute for it — `run.py`'s own single-case smoke gate still runs
   immediately before `raw/` is created, on every contracted run.
8. **The one designated hang-candidate case
   (`h2_srcmod12b_noloop_ctrl_bit2_HANGPROBE`) was independently tested in
   isolation, exactly as it will run in the gated capture (same case
   index, same harness, own subprocess), before this contract was frozen.**
   Result: `STATUS OK`, 115ms, **no hang**. This is itself informative:
   EXP-0089's hang was in the SAME 12-byte form + the SAME bit position,
   but INSIDE a real runtime loop; this experiment's construction is
   OUTSIDE a loop (a single execution, `opsel_mod=0` this group's confirmed
   -benign base) and did not hang. The case remains in the frozen matrix,
   last, with full SAFETY framing (below) — a repeat during the gated
   capture is not guaranteed to be equally safe (the H1 dispatch's own
   directive: "Hard-timeout every dispatch, one case per process, treat
   hangs and faults as RESULTS") — but it is now a *characterized* risk,
   not a blind one.

## 1. Scope discipline (repeated from `isa_helpers.py`/`casematrix.py`;
stated here as a pre-registered, not post-hoc, decision)

This experiment owns register **LIFETIME**; a concurrent sibling
(EXP-0113) owns register **ADDRESSING**. Every family used for a hand-
assembled (MODE A) case has an independently HW-VALIDATED register field
for arbitrary construction: `falu2`/`falu2i`'s `srcA_reg`/`srcB_reg`
(EXP-0099), the falu2-sibling extended/12-byte forms' fields at the SAME
bit positions (a disclosed structural extrapolation, not independently
re-validated per family — flagged per-group below), `device_load`/
`device_store`'s addressing fields (EXP-0082/83/M4-13/90, `device_store`'s
`extmode=2*data_reg` formula restricted to registers <64 per EXP-0099's own
narrowing), and `ibitcount`'s `dst`/`src` (EXP-M4-14 direct hardware
splice, re-confirmed this experiment's own pilot). `iadd2`, `falu_compact4`,
`falu_acc`, `ilogic`, `ibfins`, and other integer-ALU families were
deliberately EXCLUDED — EXP-0090/EXP-0112's own builders record that
`iadd2`'s register-mode addressing is "NOT independently re-derived
anywhere in this project" (their anchors use a fixed, uninterpreted
`srcA=0x88` byte copied from a compiled instance), and `falu_compact4`/
`falu_acc`'s operand fields are flagged STRUCTURAL/byte-diff-only in
`db.json`'s own provenance notes. Building a NEW lifetime test on an
unvalidated address mapping would silently conflate "field is inert" with
"field addresses a register this experiment guessed wrong" — an ambiguity
with no way to resolve it without addressing validation this experiment
does not have. `unpack_convert`/`cvt_i2f` (MODE B) sidestep this entirely
by reusing EXP-0089's own compiler-emitted anchors and touching only their
already-free `cache`/`mode` byte, never synthesizing new addressing.

## 2. Hypotheses under test (H1-H4, per dispatch)

### H1 — what do bits 15/31 encode, over a wider tested space?

EXP-0099 (HW-VALIDATED) found `falu2`'s (register-register form only)
`srcA_reg`/`srcB_reg` top bit has **zero observed effect** on addressing or
retention — a field value of 67 (bit set, low6=3) reads r3, never r67, and
retention depends only on `opflags` bit19/20 regardless of the top bit.
That result was explicitly scoped to ONE family, ONE operand-source shape
(GPR/ALU-computed), and no register pressure. This experiment extends the
SAME falsifier design (seed a low register with a known value via an
ALU-only path; construct the field-under-test with value ∈ {3, 67}; add a
separate, later, independent reader) into:

- **H1_FALU2I** (immediate-operand family, not register-register): does
  the analogous field in `falu2i` (which has no srcB — only one source to
  test) show the same inertness?
- **H1_FALU2EXT** (8-byte sibling, `bit17=0,bit18=1`): same falsifier for
  BOTH srcA and srcB slots.
- **H1_FALU3SRCMOD12** (12-byte 3-source sibling, `bit17=1`): same
  falsifier for srcA and srcB (the 3rd source's own field is out of scope —
  `ext_srcmod` is uncharacterized, see H1_FALU3SRCMOD12's own note).
- **H1_PRESSURE**: the base (already-validated) register-register `falu2`
  form, srcA slot only, with 15 intervening independent register writes
  between producer and later reader (a register-pressure dimension EXP-0099
  did not test for this specific bit).

**Falsifier, per sub-group:** field value 67's OWN result (word0, isolated
by holding the other operand at `R_UNWRITTEN`=0.0 or, for the 3-source
family, at a pilot-confirmed multiplicative-identity companion register)
must equal `V`=30.0 if bit15/31 is inert for addressing (CONFIRMS EXP-0099);
must equal `0.0` if it is a genuine 7th address bit reaching r67 (REFUTES);
any third value is a genuine refuter for BOTH models. The later, INDEPENDENT
reader's result (word4, always field=3, always retain) must be unaffected
by the field-under-test's value — any deviation is evidence the top bit has
SOME retention-adjacent side effect EXP-0099's narrower test could not see.

### H2 — per-family lifetime field map

For each family below, the same later-read falsifier (producer with a
candidate lifetime-bit set; separate independent later reader; a positive
control redirecting the reader to a distinguishable register) answers:
which bit(s) carry source-lifetime, which carry destination publication (if
identifiable), and whether the polarity matches falu2's own (`opflags`
bit19=release srcA / bit20=release srcB / bit21=destination publication,
EXP-0086/89/99/EXP-0090's shadow-of-the-contract finding).

- **H2_FALU2EXT_OPFLAGS**: all 5 opflags bits individually, on the 8-byte
  sibling. Bit0's polarity (matches falu2's bit19) is the one falsifiable
  a-priori prediction; bits1-4 are EXPLORATORY (no prediction is asserted;
  the pilot already shows own-result drops to 0.0 at bits3/4 — an
  unexplained side effect recorded but not pre-guessed).
- **H2_SRCMOD12B_NOLOOP**: the 12-byte 2-source sibling that is EXP-0089's
  `loop_boundary` c1 family, but constructed to execute a SINGLE time,
  OUTSIDE any loop — isolating whether EXP-0089's widened corruption
  (reaching a 3rd value, the loop accumulator) and its GPU hang (`ctrl`
  bit2) were caused by loop repetition or are intrinsic to the 12-byte
  form. Pilot-confirmed (with the one valid `opsel_mod` value, see §0 item
  6): opflags bit0/1/2 reproduce falu2's OWN contract exactly when NOT
  inside a loop — a clean, decisive answer (loop repetition, not the form,
  drives EXP-0089's widened/anomalous behavior for the RETENTION contract
  specifically; the invalid-opsel corruption mode found in the pilot is a
  SEPARATE, unrelated finding about this family's opcode space, reported
  as its own result). The one exploratory hang-probe case (§0 item 8,
  SAFETY framing below) targets the SAME literal bit position EXP-0089
  hung on, still outside a loop, to close that specific open question too.
- **H2_DEVSTORE_ADDRMODE**: `device_store`'s `addr_mode` bit1 — the SAME
  literal `0x54`/`0x56` bit-position mechanism named throughout
  `docs/isa/README.md`/`register-move-and-liveness.md`, on a THIRD kind of
  instruction (a pure memory op, not an ALU op) — tested for two distinct
  effects: does it corrupt the STORED memory content (word8, checked via
  the store itself, no re-read needed) and does it have any producer-side
  effect on the SOURCE register's later ALU reuse (word4)? Falsifier: both
  inert (the pre-registered prediction) is refuted by any deviation in
  either.
- **H2_CACHEBYTE_UNPACK / H2_CACHEBYTE_CVTI2F** (MODE B): the OTHER 7 bits
  (not bit1=literal bit17, already HW-VALIDATED corrupting by EXP-0089) of
  `unpack_convert`'s `cache` byte / `cvt_i2f`'s `mode` byte — genuinely
  free `mod`-typed fields whose bit1 alone is the previously-tested
  mechanism. No a-priori prediction for the other 7 bits (truly
  exploratory, per the dispatch's own "here is the tested space" allowance)
  except the baseline, whose value is EXP-0089's own recorded,
  HW-VALIDATED compiler-natural output — re-verified byte-identical in
  this experiment's own recompile before use (§0 item 5).

### H3 — does bit 17 generalize (one mechanism, or several sharing a bit
position)?

EXP-0089 found the literal bit 17 corrupts BOTH the flipped instruction's
OWN result AND a later reader's, in `unpack_convert`/`cvt_i2f` — distinct
from `opflags` bit19 (falu2 family), which corrupts ONLY a later reader,
never its own result. EXP-0099 showed (static analysis) bit 17's byte in
both families is structurally DISJOINT from either family's own
register-descriptor field, unlike falu2's bit15/31 (which sit INSIDE the
register field itself) — ruling out "same field, repositioned" without
resolving whether it is nonetheless the SAME underlying mechanism appearing
in multiple opcodes, or several distinct mechanisms that happen to share a
bit position.

**H3_IBITCOUNT** adds a THIRD, structurally independent family:
`ibitcount` (byte0=0x27, an entirely different opcode group from
0x09/0x17/0xa7), whose `cache` field sits at the identical literal bit
position (byte+2 bit1 = instruction bit17) and is independently
HW-VALIDATED for `dst`/`src` addressing (EXP-M4-14 direct splice on the
A18; re-confirmed this experiment's own pilot by seeding a register via
`falu2i` and reading back its exact popcount). This gives a THIRD data
point for the discriminating question, PLUS the discrim3-style "does
corruption reach a further, independent 3rd reader" persistence test
EXP-0089 explicitly could not build for any literal-bit-17 family
("this experiment does not have a 3-reader literal-bit-17 kernel to test
that directly").

**Falsifier:** if `ibitcount`'s bit17 shows the SAME dual signature
(corrupts own result AND a later reader, unconditionally on nothing else)
as unpack_convert/cvt_i2f, that is evidence for ONE shared "own-fetch
freshness" mechanism recurring across families. If it shows a DIFFERENT
signature (e.g. affects only its own result, or only a later reader, or —
per this experiment's own decisive pilot finding, see below — is
unconditional on the tested bit at all) that is evidence for SEVERAL
distinct mechanisms sharing the bit position by coincidence, not one
mechanism.

**Pilot finding (decisive, changes the a-priori H3 prediction from what a
naive "generalizes" hypothesis would expect):** `ibitcount`'s `cache` bit
was pilot-tested with BOTH values (`cache=1`/`0x56` and `cache=0`/`0x54`,
including the LITERAL byte-for-byte anchor from EXP-M4-14's own splice
record, reproduced directly, not through this experiment's builder) and
gives the IDENTICAL result either way: own-result is the correct popcount
(6) in BOTH cases, and a later, independent reader is corrupted
(read-as-zero) in BOTH cases. This is a THIRD signature, distinct from
BOTH unpack_convert/cvt_i2f (bit-dependent, corrupts own+later) AND falu2
(bit-dependent, corrupts only later): **`ibitcount` unconditionally
releases its src operand for a later reader regardless of `cache`, and its
own result is unconditionally correct regardless of `cache` — the tested
bit has NO observed causal role in either effect for this family.** This
also directly CONTRADICTS EXP-M4-14's own A18 finding that `cache=0`
("0x54") breaks the own-result to 0 — reproduced on M4 with the LITERAL
A18 anchor bytes and found NOT to break (see H3_IBITCOUNT's case notes and
RESULTS.md for the full A18-vs-M4 discrepancy discussion; this experiment
does not have the tooling to rule out a dispatch-shape confound, e.g.
grid/thread-count, between the two tests, and reports this honestly as an
open discrepancy, not a settled cross-target claim).

### H4 — mechanism discrimination

EXP-0089's `discrim3` found corruption from a flipped producer reaches
EVERY later reader (persistence), never an earlier one, and never resets
after the first subsequent reader — evidence for **persistent
producer-side writeback suppression** over a **one-shot bypass-cache
glitch**. This experiment pushes on the specific, sharper sub-questions the
dispatch names, each with its own falsifier and (per the dispatch's
explicit instruction) each PILOT-CONFIRMED before freezing:

- **H4_MEMOP_INTERVENING**: is the suppression reset by an intervening,
  UNRELATED, COMPLETED `device_store`+`device_load` pair? Falsifier:
  reset (later reader recovers to the correct value) vs. no reset (stays
  corrupted). Pilot: **no reset** — corruption persists across an
  intervening completed memory transaction.
- **H4_LATERWRITE_RESTORE**: does a SUBSEQUENT, ORDINARY (retain-semantics)
  WRITE to the SAME register fully restore it? Falsifier: restored (later
  reader sees the fresh value) vs. still-corrupted (reads zero regardless
  of the rewrite) vs. some third, garbage value. Pilot: **restored** —
  the later reader sees the freshly-written value exactly, distinguishing
  "the producer's specific value never got durably written back" (this
  result) from "the register itself becomes permanently unusable" (would
  predict no-restore).
- **H4_REGFILE_VS_FORWARD**: after a corrupting read, does an INDEPENDENT
  read path (`device_store`'s own data-register read — a different read
  port than `falu2i`'s ALU srcA read) also see the corruption, or does it
  see the real value? Falsifier: store sees the REAL value while the ALU
  path is corrupted (supports "not durably written back to the register
  file, but a bypass/forward-only path still has it" — NOT quite the same
  as EXP-0089's "writeback suppression" framing) vs. store ALSO sees the
  corruption (supports "genuinely gone from the register file by the time
  ANY path reads it," the stronger and more literal reading of "writeback
  suppression"). Pilot: **the store ALSO sees the corruption** (word8 also
  reads 0.0) — this is the sharper of the two models, and REFUTES the
  weaker "only the ALU forwarding path is affected" reading that this
  experiment's own pre-registered prediction (matching a plausible, but as
  it turns out wrong, extrapolation of EXP-0089's own language) had
  favored going in. Order (store-before-ALU-read vs. ALU-read-before-store)
  does not change the result (both pilot the same).
- **H4_BARRIER**: does the effect survive a REAL `threadgroup_barrier`
  (mem_device scope)? Falsifier: survives (later reader still corrupted
  after the barrier) vs. reset by the barrier (recovers). MSL-compiler
  route abandoned after an early attempt (the compiler hoists both the
  producer's and reader's float ALU ops BEFORE the barrier, since neither
  depends on anything the barrier orders — defeating the intended
  before/after split); the final design hand-assembles the barrier
  directly into the MODE A instruction stream (full ordering control,
  independent of compiler scheduling), using `isadb`'s own HW-VALIDATED
  `threadgroup_barrier` encoding (EXP-0025/EXP-M4-13 R8) unmodified.
  grid=1/tg=1 (single lane, single threadgroup) so the barrier is
  trivially satisfied — no cross-lane wait, matching this experiment's
  safety posture. Pilot: **survives** — the later reader is corrupted
  identically whether or not the barrier is present.

"Control-flow join" persistence (the dispatch's remaining named
discriminator) is **not independently re-tested here** — it is already
established, HW-VALIDATED evidence from EXP-0089's own `if_boundary`/
`loop_boundary` kernels (real compiler-emitted `if_push`/`pop_reconverge`
and a real runtime loop; `candB_flip_c1` corrupts the post-boundary
reader in both). Re-running the identical check would be duplicative per
CLAUDE.md's "do not redo" instruction; this experiment's own novel
contribution is the three discriminators above, which had zero prior
evidence.

## 3. Independent / controlled variables

- **Independent (per group):** the specific field/bit value(s) under test
  (register-field top bit, opflags bit index, ctrl-field upper bits,
  addr_mode bit1, cache/mode byte bits, presence/absence of an intervening
  memop/rewrite/barrier).
- **Controlled/held fixed across every MODE A case:** `carrier.metal` and
  its measured `_agc.main` length (170 bytes, `--no-fast-math`, identical
  to EXP-0099's own carrier — reused verbatim, re-measured this
  experiment's own pilot), `R_IDX=15` zeroed first instruction, the
  immediate palette (`V=30.0, K2=20.0, K3=8.0, K4=12.0, ONE=1.0` — all
  independently confirmed exact/non-clamped), dispatch shape (`grid=1,
  tg=1`), `--no-fast-math`, per-case timeout (45s harness-level / 60s
  subprocess-level).
- **Controlled/held fixed across every MODE B case:** the exact
  compiler-emitted anchor bytes/offsets from EXP-0089 (`lit17_unpack.metal`/
  `lit17_cvt.metal`, reused verbatim, recompiled fresh in this
  experiment's own tree and reverified byte-identical), the fixed
  per-kernel input value (`0x70001000` / `1234`, matching EXP-0089's own).

## 4. Known confounders

- **Register-addressing validity is family-specific** (§1) — every group
  above is scoped to a family whose addressing this experiment can trust;
  a null or corrupting result for a family whose addressing is only
  structurally/analogically extended from falu2 (the falu2-sibling
  extended/12-byte forms) carries a correspondingly weaker confidence
  label in RESULTS.md than one for an independently re-validated family
  (falu2/falu2i/ibitcount/device_load/device_store) — flagged per-group,
  not asserted uniformly.
- **`opsel`/similar "mod"-typed fields are NOT reliably analogous across
  sibling families** even when they occupy the same bit range (§0 item 6,
  the `falu_srcmod12b` opsel=4 corruption) — this experiment now treats
  every borrowed field-value convention as an explicit, disclosed
  extrapolation requiring its own pilot confirmation, never assumed.
- **The immediate codec's clamp/rounding behavior** (§0 item 3) — every
  literal constant used anywhere in `casematrix.py` is drawn from the
  frozen, independently-verified-exact palette; no new literal float is
  introduced without checking `imm_value()` first.
- **`device_store`'s `idx_off` unit** (§0 item 4) is easy to mis-apply —
  mitigated by the `store()` helper's own runtime assertion (word index
  must be a multiple of 4) and by re-verifying every planned slot
  assignment against the pilot's own observed values before freezing.
- **Compiled-kernel buffer-role convention is NOT uniform across kernels**
  (§0 item 5) — mitigated by the explicit `KERNEL_IO` table, one entry per
  kernel, never inferred implicitly.
- **A18-vs-M4 cross-target discrepancy for `ibitcount`'s `cache` bit**
  (H3 above) — reported as an open, disclosed discrepancy, not resolved
  by this experiment; a dispatch-shape (grid/thread-count) confound
  between EXP-M4-14's original A18 test and this experiment's single-lane
  M4 test cannot be ruled out with the tooling available here.
- **SAFETY (the one hang-candidate case):** `h2_srcmod12b_noloop_
  ctrl_bit2_HANGPROBE` targets a bit position that produced a genuine GPU
  hang in a DIFFERENT (loop-embedded) context in EXP-0089. It is
  pre-tested in isolation (§0 item 8, no hang observed) but is not
  guaranteed safe on a repeat — it is placed LAST in the frozen case order
  (enforced by `casematrix.build_cases`'s own assertion) so that, if a hang
  occurs during the gated capture, every other case's data is already
  flushed to `raw/` and is not lost (per the standing append+fflush,
  partial-capture-retained-never-reused rules). A hang here is a
  first-class, expected-possible RESULT, not a defect in the run.

## 5. Environment / tool revisions

- macOS 26.6.2 (build 25G82), Apple M4 (G16G), `Mac16,10`, Metal 4.
- `tools/agx-isa/isadb.py`, `tools/agxtest/agxtest.py`, `tools/shdump/*`:
  read-only, used exactly as documented in their own READMEs; not modified.
- Python 3.14.6 (`/opt/homebrew/bin/python3`), invoked as `python3 -B`
  throughout (no `.pyc` cache writes into the tree).

## 6. Raw-record schema (frozen)

Gated (`01_results.jsonl`, byte-compared across runs): `i, name, group,
kernel, splices, oracle, notes, status, pipeline_source, out_hex, observed,
match`. Non-gated (`01_timing.jsonl`, NOT byte-compared): `i, duration_ms,
argv, stdout, stderr`. See `run.py`'s `GATED_KEYS`/`NONGATED_KEYS`/
`SMOKE_KEYS` for the single authoritative definition imported by both the
runner and `verify.py --selftest`.

## 7. Timeouts

Per-case hard timeout: 45s (`case_exec.py`'s own `agxtest.py --run-timeout`
budget) / 60s (the `run.py`-level subprocess wall clock around the whole
`case_exec.py` invocation, matching EXP-0099's precedent with margin for
the one 12-byte extended-form hang-probe). Environment/build commands:
5-120s. Full run: no overall cap beyond the sum of 77 cases' individual
timeouts (worst case ~77 minutes; observed pilot durations are 90-200ms
per case, so the realistic run time is a few minutes).
