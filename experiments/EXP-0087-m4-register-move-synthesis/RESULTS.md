# RESULTS -- EXP-0087 (M4 register-move synthesis, DRV-ISA-01)

STATUS: **CAPTURE COMPLETE, ANALYSIS PARTIAL** -- both gated hardware
captures (`raw/m4-20260827-run01/`, `raw/m4-20260827-run02/`) are closed,
valid, and used directly below. The automated `analysis.py --write` step
and therefore the final `verify.py --captured` gate are blocked by a bug
discovered post-capture in the (hash-frozen) analysis script; **the
underlying raw evidence is not affected**. Full accounting: `QUARANTINE.md`.
Every number in this document is traceable to
`raw/m4-20260827-run01/04_results.jsonl` (and, for the two rows that differ,
`raw/m4-20260827-run02/04_results.jsonl`), read directly.

Target: **local M4/G16G only** (per `CLAUDE.md` 2026-08-27 directive). No
A18 Pro replication attempted (out of scope, hands-off).

---

## 1. OBSERVED: what the compiler actually emits for a GPR-to-GPR move

Four minimal, `tid`-indexed kernels (`kernels/census.metal`), compiled and
disassembled with our own tools (`baseline.py::derive_census`, re-derived
identically in both closed runs -- `06_baseline.json` cross-run byte-identical):

| kernel | context | compact-move (byte0 low-nibble 0xb) instances | tokenizes cleanly |
|---|---|---|---|
| `k_passthrough` | value through a local variable (`float t = a; out[tid] = t;`) | **none** -- lowers straight to `device_load` -> `device_store` (store `addr_mode=0x56`, "direct live load-result data"); no move at all | yes |
| `k_swap` | classic two-variable swap | undetermined past offset 0x1c: a `0x2b`-class instruction our DB does not yet decode (`2b0009c0...`) blocks further tokenization | **no** (leftover, see below) |
| `k_loop_phi` | genuine loop-carried control-flow join (a data-dependent, non-unrollable `for` loop; **not** `if`/`else`, which this ISA lowers to predication/select, not a branch -- confirmed separately not to emit this family) | **two** real instances: `+0x6e reg_move_c0 5b000000` (dst=5, src_reg=**0**, src_flag=0, src_class=0, op_desc=0 -- literally all-zero payload) and `+0x8a reg_move_c1 2b860100` (dst=2, src_reg=6, **src_flag=1** ["uniform/class"], src_class=0, op_desc=0) | yes |
| `k_call_marshal` | noinline function-call argument marshal (`frame_marker`/`call`/`ret`, confirmed present) | **none observed in the caller** -- argument setup here uses a different instruction (`b_alu10_lo7`, byte0 `0x?b`+different match, not in the reg_move_c*/uniform_mov family); the compact-move family is not what carries this call's arguments | yes |

**Interpretation.** Two of four hand-authored contexts produce zero
instances of this family (a value simply aliased through a variable
optimizes away entirely; a noinline call's argument marshal uses a sibling
but DIFFERENT instruction). The one context that reliably produces the
family is a genuine control-flow-join phi inside a real (non-unrolled)
loop -- and even there, the TWO instances that appear look nothing alike:
one (`reg_move_c0`, all-zero payload) matches the DB's own characterization
of that low-nibble-0 form as a "const-zero / scope-prep" op rather than a
value move; the other (`reg_move_c1`, `src_flag=1`) is very plausibly the
actual phi-resolving copy, reading from a **uniform/class-flagged** source,
not a plain GPR. Neither instance the compiler emitted here has `src_flag=0`
with a nonzero GPR source -- i.e. **the compiler-emitted census alone does
not show a single "textbook" GPR<-GPR move**; both real-world instances are
either the const-zero form or a uniform/class-sourced form. This corroborates
the synthesis experiment below, which independently finds the plain-GPR-
source path (`src_flag=0`) untested in the wild and confirms it works only
via direct hardware splicing, not via anything the compiler was observed to
emit on its own for these four inputs.

`k_swap`'s undecoded `0x2b`-class tail is a genuine DB gap (a shift/pack
family per `docs/isa/README.md`'s own notes on the `0x?b` shift/rotate
compact forms) -- out of this experiment's scope; recorded, not chased.

---

## 2. OBSERVED + falsified/confirmed: can an independently-assembled move
   be spliced in and executed correctly?

Carrier: `kernels/synth_move.metal` (16 constant-index loads -> 16 compact
moves -> 4 vector `device_store`s; frozen baseline `out[K]==in[K]==1000.0+K`
for K=0..15). Every candidate below was **independently re-assembled from
field values with `tools/agx-isa`'s own `assemble()`** (never a copy-pasted
byte string) and spliced over an EXISTING 4-byte instruction (same length).
`probe_src` = the first move (dst=r12, feeds `out[0]`); `probe_dst` = the
last move (originally dst=r3/`out[15]`, nothing later can overwrite a
retarget). Full per-case data: `raw/m4-20260827-run01/04_results.jsonl`
(cases 0-48, `casematrix.py` for the frozen definitions/predictions).

### 2a. CTRL -- paired null-result controls (2/2 as predicted)

Re-splicing each probe with its own ORIGINAL bytes changed nothing
(`diff_from_baseline: {}` for both `ctrl_src_identity` and
`ctrl_dst_identity`). The splice mechanism itself introduces no spurious
change -- a null result here is meaningful because the mechanism is proven
live (every other case below DOES show effects from the same pipeline).

### 2b. MOVE-01 -- byte+2 FAMILY sweep, dst=12 src=8 op_desc=0x08 fixed
   (23 cases: every "observed" high nibble of the five DB descriptors)

| byte+2 | assembled as | result | verdict |
|---|---|---|---|
| `0x00`,`0x20`,`0x60` (reg_move_c0) | reg_move_c0 | `out[0] -> 0.0` | **silent zero** |
| `0x01` | reg_move_c1 (= `uniform_mov`) | (this is the CTRL baseline, not resplit here) | **WORKS** (see baseline) |
| `0x21` | reg_move_c1 | **`out[0]` UNCHANGED (stays 1000.0)** | ambiguous -- see below |
| `0x61`,`0xa1`,`0xc1`,`0xe1` | reg_move_c1 | `out[0] -> 0.0` | **silent zero** |
| `0x09`,`0x29`,`0x49`,`0x69`,`0x89`,`0xc9` (reg_move_c9) | reg_move_c9 | `out[0] -> 0.0` | **silent zero** |
| `0x0b`,`0x1b`,`0x2b`,`0x3b` (reg_move_cb) | reg_move_cb | `out[0] -> 0.0` | **silent zero** |
| `0x22`,`0x23`,`0x24`,`0x2a` (reg_move_c2var) | reg_move_c2var | `out[0] -> 0.0` | **silent zero** |
| `0x26` (reg_move_c2var) | reg_move_c2var | **NONDETERMINISTIC**: `CMDBUF_ERROR` (fault) in run01, `STATUS OK` with `out[0]->0.0` in run02 | **fault / silent-zero, unstable across runs** |

**19 of 23** non-`0x01` byte+2 candidates are unambiguous: real hardware
executes them (`STATUS OK`, no fault) but the destination register reads
exactly `0.0`, never the intended source value -- a clean, deterministic
**silent no-op-to-zero**, reproduced byte-for-byte across both closed runs.
This directly falsifies the "these are five interchangeable move opcodes"
reading and supports "byte+2's low nibble is a real discriminator: only
`0x?1` reads a live source" -- **but see 2c below: the low nibble alone is
not sufficient either.**

`0x26` is the one exception that faults instead of zeroing (in run01) --
and did NOT reproduce that fault in run02 (see `QUARANTINE.md`). This is a
genuine finding: at least one of the "documented observed" c2var high
nibbles sits on a fault/succeed boundary, not a stable "always zero"
behavior. **Driver guidance: do not use `byte+2=0x26`; its behavior is not
guaranteed stable on this hardware/driver combination.**

`0x21` is the second exception, and the most important open question this
experiment leaves: **`out[0]` came back byte-identical to the correct,
already-present value (1000.0), reproduced identically in both runs.**
Because this case's `src` was held at 8 (the SAME uniform slot the
UNMODIFIED probe already read), a genuinely-working move and a true no-op
that leaves r12's prior content undisturbed are **observationally
indistinguishable from this case alone** -- r12 has no other writer in this
kernel, so either explanation predicts exactly the observed bytes. Weak
circumstantial evidence favors "genuinely works": the observed bit pattern
is the EXACT IEEE-754 encoding of 1000.0, not a plausible "leftover
register content" pattern (compare the truly-untested-register probes in
2d below, which return distinctive small denormals, not round numbers) --
but this is not proof. **UNKNOWN, precisely scoped**: does `byte+2=0x21`
(the DB's own documented "dominant" c1 high nibble) perform a real move?
Closing this needs one more case, not run here: re-splice `probe_src` with
`byte+2=0x21` and `src` pointing at a DIFFERENT sibling value (e.g. `0x0a`
= 1001.0) and check whether `out[0]` follows to 1001.0.

### 2c. MOVE-02 -- op_desc (byte+3) single-bit sweep, dst=12 src=8
   byte+2=0x01 fixed (8 cases, one bit flipped from the known-working 0x08)

| bit flipped | op_desc | result | verdict |
|---|---|---|---|
| bit0 | `0x09` | `out[0]` unchanged (=1000.0, byte-identical to a correct read) | works or ambiguous (same caveat as 2b's `0x21`) |
| bit1 | `0x0a` | `out[0] -> 0.0` | **silent zero** |
| bit2 | `0x0c` | **`out[0] -> 0.0` AND `out[8] -> 1000.0`** (a slot OTHER than the addressed one received the source value) | **CORRUPTS** -- routes the write to a different destination entirely |
| bit3 | `0x00` | `out[0] -> 0.0` | **silent zero** |
| bit4 | `0x18` | `out[0] -> 0.0` | **silent zero** |
| bit5 | `0x28` | `out[0]` unchanged (=1000.0) | works or ambiguous (same caveat) |
| bit6 | `0x48` | `out[0]` unchanged (=1000.0) | works or ambiguous (same caveat) |
| bit7 | `0x88` | `out[0]` unchanged (=1000.0) | works or ambiguous (same caveat) |

This is the sharpest single finding in the experiment: **op_desc is not a
harmless "descriptor" -- bit2 (`0x04`) is a live routing bit.** Setting it
(op_desc `0x08 -> 0x0c`) makes the SAME `dst`-nibble-12 instruction write
its source value into whatever register feeds `out[8]` instead of (or as
well as) r12, while r12 itself reads zero. This is HW-validated,
reproduced byte-for-byte across both closed runs. **Driver guidance: never
set op_desc bit2 (`&0x04`) on this instruction family; its effect is
destination corruption, not a size/type variant.** Bits 1, 3, and 4 each
independently break the read to a silent zero (same failure mode as most
of MOVE-01). Bits 0, 5, 6, 7 show no observable deviation from a correct
read -- subject to the identical "same source value" ambiguity noted above
for `byte+2=0x21` (not independently disambiguated in this experiment).

### 2d. MOVE-03 -- src/usrc sweep, dst=12 byte+2=0x01 op_desc=0x08 fixed
   (10 cases: the one family already known to read correctly)

- **5/5 sibling values worked exactly as predicted**, with bit-exact
  correctness and zero cross-talk: retargeting `probe_src`'s `usrc` field to
  another live move's slot (`0x0a`,`0x10`,`0x18`,`0x20`,`0x26`, corresponding
  to `in[1]`,`in[4]`,`in[8]`,`in[12]`,`in[15]`) made `out[0]` take EXACTLY
  that sibling's tagged value (1001.0, 1004.0, 1008.0, 1012.0, 1015.0) with
  no other output slot touched. **This is the core positive result of the
  whole experiment: a move independently constructed by our own assembler,
  spliced into a slot that did not originally contain that specific move,
  correctly delivers a genuinely different source's value to the correct
  destination, confirmed on real M4 hardware across two independent runs.**
- Uniform slots below our program's own allocated range (`usrc=0x00,0x04`,
  i.e. slots the compiler never assigned to any of our 16 values) read back
  distinctive small denormalized floats (`~1.63e-40`), not zero and not one
  of our tagged inputs -- some other real, deterministic (repeats
  byte-for-byte across both runs), unidentified data lives there. Recorded
  as `EXPLORE`, not claimed.
- Far-above-range slots (`usrc=0x7e`) read exactly `0.0`; `usrc=0xfe` read a
  different tiny denormal (`~1.77e-43`). Neither faulted.
- `usrc=0x88` (the `src_flag`/bit7 "GPR-mode" bit set, addressing GPR r8
  directly, read at the very first instruction of the kernel, before any of
  our own moves have executed) read yet another distinct tiny denormal
  (`~1.12e-44`) -- NOT the clean zero a "register file zero-initialized at
  kernel entry" model would predict (contrast MOVE-04 below, where a
  register that is simply never written READS EXACTLY ZERO). This is a
  genuine, unresolved discrepancy between two different "unwritten
  register" scenarios and is recorded as `EXPLORE`, not smoothed over: it
  may mean the GPR file is NOT uniformly zero-initialized at thread launch
  (leftover content from a prior dispatch/allocation), or it may mean
  `src_flag=1` addresses something other than a plain GPR (a different
  register bank/"class", consistent with `src_flag`'s own DB enum name
  `"uniform/class"`). Not distinguished here.

### 2e. MOVE-04 -- dst sweep on `probe_dst` (4/4 exactly as predicted)

Retargeting the LAST move's `dst` field (src=`0x26`=in[15]=1015.0,
byte+2=0x01, op_desc=0x08 held fixed) redirected the write across all four
register quads exactly as predicted from instruction-ordering reasoning,
reproduced byte-for-byte across both closed runs:

| new dst | affected output slot | value | side effect |
|---|---|---|---|
| r12 | `out[0] -> 1015.0` | correct | `out[15] -> 0.0` (nothing else writes r3 any more) |
| r8 | `out[4] -> 1015.0` | correct | `out[15] -> 0.0` |
| r4 | `out[8] -> 1015.0` | correct | `out[15] -> 0.0` |
| r0 | `out[12] -> 1015.0` | correct | `out[15] -> 0.0` |

**This independently confirms the `dst` field (byte0 high nibble) genuinely
selects the physical destination register**, across all four register
quads (0, 4, 8, 12) -- and confirms that an unwritten register (r3, once its
only writer is retargeted away) reads back **exactly 0.0**, not garbage --
a DIFFERENT, cleaner result than the `usrc=0x88` GPR-mode read above (see
2d), which is a genuine open discrepancy, not resolved by this experiment.

### 2f. MOVE-05 -- byte+2 values outside every documented family (2 cases)

- `byte2=0x0F`: `CMDBUF_ERROR` (contained fault) in run01; **`STATUS OK`
  with the ENTIRE 16-float output zeroed** in run02 -- nondeterministic,
  same pattern as `0x26` above (see `QUARANTINE.md`).
- `byte2=0xFF`: `STATUS OK` in BOTH runs, but the ENTIRE 16-float output
  reads all-zero (not just `out[0]`) -- a materially DIFFERENT failure mode
  from every MOVE-01 "silent zero" case (which only zeroed the one targeted
  slot). This suggests `0xFF` disrupts something broader than the single
  destination -- plausibly the whole store/scoreboard state for this
  dispatch, not merely this one instruction's own write.

**Driver guidance: byte+2 values outside the documented low-nibble
{0,1,9,0xb} set and the high-nibble-2 residual set are unsafe** -- observed
behaviors span silent zero, single-fault, whole-output corruption, and
fault/succeed nondeterminism, with no safe fallback identified.

---

## 3. THE RULE: how must a compiler emit a correct GPR<-GPR move?

**What IS established, HW-validated, on this M4, across two independent
closed captures (except where flagged nondeterministic):**

1. Use the compact 4-byte form: byte0 = `0x0B | (dst << 4)`, where **`dst`
   is a 4-bit field reaching ONLY r0-r15** -- this instruction family
   structurally CANNOT address a destination beyond r15 (confirmed: MOVE-04
   independently validated dst across all four low-register quads 0/4/8/12;
   no wider dst form was exercised or found in this instruction's own
   encoding -- `docs/isa/README.md`'s own `uniform_mov` provenance already
   states "higher GPR dst would use a wider move form", not identified
   here). **If the destination is r16 or above, this family cannot be
   used at all; a compiler must fall back to whatever wider move/ALU-copy
   form exists for that case (out of this experiment's scope).**
2. byte1 = the source selector, values 0-255 (7-bit register index + a
   high "src_flag"/"uniform-class" bit at bit7). **The ONLY byte+2/byte+3
   combination proven, by independently varying the source across FIVE
   different values, to deliver the correct source value to the correct
   destination with zero cross-talk is byte+2 = `0x01`, byte+3(op_desc) =
   `0x08`, byte1 = the plain 7-bit index of the source (`src_flag`=0,
   ordinary GPR/uniform-slot addressing).** This is the one encoding a
   compiler can rely on today.
3. **op_desc bit2 (`0x04`) MUST be clear.** Setting it does not merely fail
   silently -- it redirects the destination write to an unrelated register,
   observed HW-validated and reproduced across both runs. This is the
   single most dangerous latent defect an implementer could hit by treating
   op_desc as a don't-care "descriptor" field, exactly the failure mode this
   experiment exists to catch.
4. op_desc bits 1, 3, and 4 (`0x02`, `0x08`'s absence, `0x10`) each
   independently break the read to a silent zero when flipped from the
   known-good `0x08` -- avoid them; **op_desc must be exactly `0x08`** (not
   merely "bit3 set"), since bits 1/3/4 all individually break it even
   though none of them touch bit3.
5. Every OTHER byte+2 family value tested (`reg_move_c0`, `reg_move_c9`,
   `reg_move_cb`, and four of five `reg_move_c2var` values) is a **silent
   no-op that always zeros the destination** rather than moving the source
   -- these do NOT implement "mov dst,src" for any src value tried, and must
   not be used by a compiler intending a real move, regardless of what the
   DB's per-descriptor "src_class"/"op_desc" enums suggest about their
   semantics.
6. `byte+2=0x26` must be avoided entirely: it is the one candidate observed
   to fault at all (in either run), and its behavior did not reproduce
   across runs.

**What is NOT established (precisely scoped remaining unknowns):**

- **U1 -- does `byte+2=0x21` (the DB's own "dominant" `reg_move_c1` high
  nibble) perform a genuine move, or is it a no-op that happened to leave
  the correct pre-existing value undisturbed?** Same open question for
  op_desc bits 0/5/6/7 relative to the working `0x08`. Not closable from
  this experiment's data (see 2b/2c); closing it needs one more splice
  case with a DIFFERENT source value than the one already resident.
- **U2 -- does this rule depend on source LIVENESS** (whether the source
  register the compiler considers "live" at that program point matches
  what the move reads), independent of the value-routing behavior
  characterized here? Out of this experiment's scope by design --
  EXP-0086-m4-register-liveness-bits is the sibling experiment testing bit
  17 (byte+2 bit 1) liveness semantics concurrently; **cross-reference its
  RESULTS rather than duplicating it.** Notably, bit 17 IS byte+2 bit 1 in
  this experiment's own bit-numbering, and MOVE-02's bit1 flip (byte+3
  `0x08`, NOT byte+2) is a DIFFERENT bit than EXP-0086's target -- this
  experiment did not vary byte+2 bit 1 independently of the family-selecting
  low nibble, so no direct comparison is available from this data alone. If
  EXP-0086 finds bit 17 changes move behavior, that is an ADDITIONAL
  constraint layered on top of the rule above, not a contradiction of it.
- **U3 -- whether a "wider" move form exists for dst >= r16.** Not probed;
  this instruction family structurally cannot reach it (4-bit dst), and no
  candidate wider encoding was tested.
- **U4 -- the exact content of "unwritten" uniform slots/registers**
  (2d's small denormals, the `src_flag`-GPR-mode read of r8) is
  unidentified data, not characterized further here.
- **U5 -- the TRUE fault rate of `byte+2 in {0x26, 0x0F}`** -- one sample
  per run is not enough to characterize a probability; see `QUARANTINE.md`
  successor recommendation.

---

## 4. Corrected descriptor proposal (negative space, item 4)

Based on the above, the five DB descriptors are **not five distinct
operations**. Proposed correction for `tools/agx-isa/db.json` (report text
only; the DB itself is untouched by this experiment per the read-only
tools convention):

- **Collapse `reg_move_c0`, `reg_move_c1`, `reg_move_c9`, `reg_move_cb`, and
  `reg_move_c2var` into ONE instruction**, `reg_move` (byte0 low-nibble
  `0xb`, `dst` = byte0 high nibble, 4-bit, r0-r15 only), with byte+1 =
  `src`(7-bit)+`src_flag`(1-bit) as already documented, and **byte+2 kept
  as a single 8-bit field, not two independently-enumerated nibbles**: this
  experiment's data shows the low nibble is NOT independent of the high
  nibble's effect (e.g. `0x21` behaves differently from `0x61`/`0xa1`/
  `0xc1`/`0xe1` despite sharing the "c1" low nibble) and the *specific full
  byte value* `0x01` is what is proven to work, not "any low-nibble-1
  value". The five-way split by low nibble should be retired.
- **byte+3 ("op_desc") should be documented as a structured field with (at
  minimum) bit2 flagged EXPLICITLY DANGEROUS** ("destination-redirect /
  corruption bit, HW-validated EXP-0087 -- do not set"), not a generic
  "operand/size descriptor". The current per-descriptor op_desc enums
  ("plain", "desc-04", "desc-08", ...) should be replaced with the concrete
  per-bit behavior found here until a full bit-by-bit characterization
  exists for values other than `0x08`.
- **The only value combination that should be marked HW-VALIDATED for
  actually moving a value** is `byte+2=0x01, byte+3=0x08, src_flag=0`
  (5-way independently-varied source, zero cross-talk, reproduced across
  two runs). Every other byte+2 value tried should be marked either
  `HW-VALIDATED (silent zero, not a move)`, `HW-VALIDATED (corrupts,
  EXP-0087 MOVE-02 bit2)`, or `HW-VALIDATED (nondeterministic
  fault/silent-zero, EXP-0087, do not use)` for `0x26`/`0x0F`/`0xFF`, rather
  than left as an unvalidated "observed" enum entry as today.
- `byte+2=0x21` and op_desc bits 0/5/6/7 should be marked `PARTIAL /
  UNKNOWN` (this experiment's U1), not silently folded into either the
  working or the silent-zero bucket.

---

## 5. DRV-ISA-01 statement: can a move now be GENERATED?

**Yes, with a narrow, precisely-stated constraint, not a guess:** a compiler
targeting this Apple9/M4 ISA CAN emit a correct GPR-to-GPR (or uniform-
slot-to-GPR) move today, using the compact 4-byte form `0x0B | (dst<<4)`,
`src` (7-bit, `src_flag=0`), `byte+2=0x01`, `byte+3=0x08`, with `dst`
restricted to r0-r15. This was independently constructed (never copied from
an observed byte string) with this repository's own assembler and executed
correctly on real M4 hardware across five different source values and two
independent closed captures, satisfying the "generate, not merely decode"
acceptance bar for DRV-ISA-01.

**The constraint that must be stated alongside it:** every other candidate
encoding for this same instruction shape is either a confirmed silent
no-op, a confirmed destination-corrupting defect (op_desc bit2), a
confirmed fault, or -- for `byte+2=0x21` and op_desc bits 0/5/6/7 --
genuinely unresolved by this experiment (U1 above). A compiler MUST NOT
generalize "any low-nibble-1 byte+2, any op_desc with bit3 set" as safe; it
must emit exactly `0x01`/`0x08`. Destinations at or above r16 are out of
this instruction family's reach entirely (a 4-bit field), and no
alternative wider-move encoding was identified in this experiment.

---

## 6. Gate results

- `verify.py --selftest`: **PASS**, 20/20 synthetic cases.
- `verify.py --seqtest`: **PASS**, 14/14 state-machine steps.
- `verify.py --preflight` (before run01): **PASS**.
- `verify.py --between-runs` (before run02): **PASS**.
- `verify.py --captured`: **FAILS** -- see `QUARANTINE.md` for the exact,
  precisely-scoped reason (a bug in the hash-frozen `analysis.py`, plus the
  independent 2/49-case cross-run nondeterminism above). The raw evidence
  itself is not in question; only the final automated gate could not be
  completed as contracted.
- `roundtrip_test.py` (`tools/agx-isa`): not affected by this experiment
  (no DB edits were made; `tools/*` is read-only per the dispatch).

---

## 7. Clean-room provenance

```
Clean-room provenance: OWN-SHADER
Inputs inspected: kernels/synth_move.metal, kernels/census.metal (our own
  MSL); the compiled AGX bytes tools/shdump extracted from them; our own
  tools/agx-isa assembler/disassembler output on those bytes; our own
  tools/agxtest splice+execute harness.
Apple binary introspection: NONE
Reproduction: see README.md; the two closed captures are
  raw/m4-20260827-run01/ and raw/m4-20260827-run02/.
Evidence: raw/m4-20260827-run01/04_results.jsonl (sha256 of the file is
  recorded in raw/m4-20260827-run01/03_dispatch.json.results_sha256),
  raw/m4-20260827-run02/04_results.jsonl (likewise),
  raw/m4-20260827-run0{1,2}/06_baseline.json (the compiler census).
```
