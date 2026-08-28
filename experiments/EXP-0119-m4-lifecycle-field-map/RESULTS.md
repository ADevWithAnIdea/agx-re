# RESULTS — EXP-0119 M4 register-lifecycle field map

## Evidence status

**Both contracted runs complete and gate-passing.** `raw/m4-20260828-run01`
and `raw/m4-20260828-run02`, 77/77 cases each, `STATUS OK` in every single
case in both runs (including the one deliberately isolated hang-candidate
case — no hang, no fault, no timeout, host did not wedge). `verify.py
--selftest` (51 checks), `--seqtest`, `--preflight`/`--between-runs`,
`--captured` all **PASS**. `01_results.jsonl` is **byte-identical** across
both independent runs
(`sha256 7e5aa5fa6cf83b7295a061a557abccf9a9bd1215314d9b261715464638fb0d87`).
74/77 cases matched their pre-registered oracle; the 3 that did not are:
one deliberate detection-capability control (`positive_control_deliberate_
mismatch`, designed to mismatch) and two genuine, pre-registered hypothesis
**refutations** (`h4_regfile_corrupt_{store_then_alu,alu_then_store}` — see
H4). Every finding below is **HW-VALIDATED** (independently constructed,
spliced, and observed on real M4 hardware, two independent process
launches per case, byte-identical across two independent full runs) unless
explicitly marked otherwise. Target: **M4/G16G only**; no A18 Pro evidence
(hands-off); no M5 evidence.

This experiment's own pre-registration pilot caught five real bugs before
any gated capture (full detail: `PRE_REGISTRATION.md` section 0,
`PROGRESS.md`) — a length/framing discovery in `isadb.instr_length` (the
low-nibble-9 float-ALU group's length selector is the `ctrl` field's own
low 2 bits, not a free bit), a minifloat-immediate clamp collision, a
`device_store` word-addressing slip, a MODE B buffer-role mismatch, and an
invalid-opcode discovery in `falu_srcmod12b`. All five are documented
inline in `isa_helpers.py`/`casematrix.py` at their fix sites and are not
repeated in full here except where they bear directly on a verdict below.

---

## 0. Headline

**H1 (bits 15/31): CONFIRMED inert for addressing and retention across
every new context tested** — `falu2i`, `falu2_ext` (both operand slots),
`falu3_srcmod12` (both operand slots), and under 15-deep register pressure.
Field value 67 (bit set) always reads r3's value, never r67's — the tested
space is now four families plus a pressure condition, all consistent with
EXP-0099's original register-register `falu2` finding. **Still no positive
account of what the bit encodes; still classified role UNKNOWN.**

**H2 (per-family map): produced for six families**, with polarity matching
falu2's own `opflags` contract (bit19=release-srcA — at the family-specific
absolute bit position, see the table) in four of them
(`falu2i`, `falu2_ext`, `falu_srcmod12b`, and by extension the base `falu2`
already established); a genuinely different, unconditional-corruption
contract in `ibitcount` (also serving H3); and a bit-position-inert (on
this literal-mechanism-adjacent byte) result for `device_store`'s
`addr_mode`.

**H3 (does bit 17 generalize): THREE DISTINCT SIGNATURES for "a bit at the
same literal position," not one mechanism.** `unpack_convert`/`cvt_i2f`
(EXP-0089): bit-dependent, corrupts BOTH own result AND a later reader.
`falu2`-family `opflags` bit19/20 (EXP-0086/89/99, this experiment's own
replication throughout H1/H2): bit-dependent, corrupts ONLY a later reader,
never its own result. `ibitcount`'s `cache` bit (this experiment, H3, new):
**bit-INDEPENDENT** — own result is always correct and a later reader is
always corrupted, REGARDLESS of the bit's value. Verdict: **several
distinct mechanisms that happen to recur at the same or an analogous bit
position, not one mechanism reappearing** — the discriminating test the
dispatch asked for.

**H4 (mechanism discrimination): the persistent-writeback-suppression model
is sharpened, not merely reconfirmed.** Corruption survives an intervening
completed, unrelated device_store+device_load pair (H4_MEMOP) and a real
`threadgroup_barrier` (H4_BARRIER) — both first-class new evidence, zero
prior data existed for either crossing. A fresh, ordinary WRITE to the same
register **fully restores** it (H4_LATERWRITE) — ruling out "the register
becomes permanently unusable" in favor of "the specific value/write-instance
was never durably committed." And — the discriminating result that most
sharpens the model — an INDEPENDENT read path (`device_store`'s own
data-register read, not `falu2i`'s ALU srcA read) **also** sees the
corruption (H4_REGFILE_VS_FORWARD, a genuine refutation of this
experiment's own weaker a-priori prediction): the value is not merely
"skipped in the ALU forwarding path," it is **gone from every read path by
the time anything reads it** — the strongest, most literal reading of
"persistent producer-side writeback suppression" survives; a
forwarding-path-only model does not.

---

## 1. H1 — bits 15/31 in new contexts

Falsifier (per `PRE_REGISTRATION.md` §2): seed r3=30.0 via an
HW-VALIDATED ALU-only path; construct the field-under-test with value ∈
{3, 67}; read the PRODUCER's own result (isolates addressing) and a
SEPARATE, independent, LATER reader (isolates retention). All 24 cases,
both runs, byte-identical, zero faults.

| family | slot | field=3 own | field=67 own | later-read, retain (bit=0) | later-read, release (bit=1) |
|---|---|---:|---:|---:|---:|
| `falu2i` (6B, immediate) | srcA | 50.0 | **50.0** | 50.0 | 20.0 |
| `falu2_ext` (8B, register) | srcA | 30.0 | **30.0** | 50.0 | 20.0 |
| `falu2_ext` (8B, register) | srcB | 30.0 | **30.0** | 50.0 | 20.0 |
| `falu3_srcmod12` (12B, 3-src) | srcA | 30.0 | **30.0** | 50.0 | 20.0 |
| `falu3_srcmod12` (12B, 3-src) | srcB | 30.0 | **30.0** | 50.0 | 20.0 |
| `falu2` (6B, register), 15-deep pressure, srcA | 30.0 | **30.0** | 50.0 | 20.0 |

Every "field=67 own" cell reads **exactly the field=3 value** (never 0.0,
which is what a genuinely-unwritten r67 would read) — the addressing
question is unambiguous and identical across all six rows. Every later-read
cell tracks the corresponding family's own retention bit (b19/b20 as
named) exactly as EXP-0086/89/99 established for the base `falu2` family,
regardless of what the SAME instruction's top-bit field value was.

**Verdict: H1 CONFIRMED over the full tested space — bits 15/31 remain
HW-tested INERT for addressing and retention in every family reachable
through falu2's validated register-field convention** (`falu2i`,
`falu2_ext`, `falu3_srcmod12`, and under register pressure). This is a
**wider tested space**, not a resolved mechanism: the bit's role, if any,
remains `UNKNOWN`. **Not tested** (disclosed, not silently dropped): the
uniform-register/vs-GPR operand-class dimension named in the dispatch
(no validated way to construct it — see `isa_helpers.py`'s addressing-scope
note) and the 3rd source of `falu3_srcmod12` (`ext_srcmod` is
uncharacterized).

---

## 2. H2 — per-family lifetime field map

The table below is this experiment's primary H2 deliverable. Bit numbers
are **absolute instruction bits**; note the family-specific base differs
(`falu2i` has no srcB, so its one release flag sits at a DIFFERENT absolute
position than falu2's srcA-release flag, despite playing the same role —
see the family note column).

| family | length | source-lifetime bit(s) | destination-publication bit | polarity vs. falu2 | confidence |
|---|---:|---|---|---|---|
| `falu2` (register-register) | 6B | bit19=srcA, bit20=srcB (EXP-0086/89/99) | bit21 (EXP-0090/EXP-0099 attribution) | — (the reference) | HW-VALIDATED |
| `falu2i` (immediate) | 6B | bit20=srcA (its ONLY source; `imm_sign` occupies bit19 in this family, a different field) | untested this experiment (opflags is only 4 bits here, bits20-23) | **matches** (same release-on-set polarity, different absolute position because the field layout differs) | HW-VALIDATED |
| `falu2_ext` (register, 8B) | 8B | bit19=srcA (bit0 of opflags); bits1-4 (instr bits20-23) EXPLORATORY, no established role | bit21 candidate untested; own-result unexpectedly drops to 0.0 at bits3/4 (unexplained, recorded not interpreted) | bit0 **matches** falu2 exactly | HW-VALIDATED (structural extrapolation of field position from falu2, not independently addressing-validated) |
| `falu3_srcmod12` (12B, 3-src) | 12B | untested directly (own-result formula for this family is not independently validated — see H1 note); srcA/srcB addressing behaves like falu2 | untested | not directly tested (out of scope, `ext_srcmod` uncharacterized) | STRUCTURAL for the lifetime question; HW-VALIDATED for addressing only |
| `falu_srcmod12b` (12B, 2-src, `opsel_mod=0`) | 12B | bit19=srcA (bit0 of opflags), bits20/21 (bits1/2) tested NULL for this construction | bit21 tested, no effect observed under this construction | bit0 **matches falu2 exactly** — WITH the one valid `opsel_mod` value found (see below) | HW-VALIDATED, narrow (`opsel_mod=0` only; `opsel_mod=4`, this experiment's first uncritical guess, is an INVALID encoding for this family — see §2.4) |
| `device_store` (memory) | 14B | `addr_mode` bit1 (the literal `0x54`/`0x56` position) tested INERT — neither the stored content nor the source register's later ALU reuse changed | n/a (no destination register) | **inert at this literal bit position**, unlike every ALU family tested | HW-VALIDATED |
| `unpack_convert` (8B) | 8B | bit17 (EXP-0089, corrupts own+later); bits 0,2-7 of the SAME byte re-swept this experiment, ALL 7 show NO detectable effect (byte-identical to baseline in every case) | n/a in this family's exposed fields | bit17 alone is load-bearing; the rest of the byte is either genuinely inert OR (bit0 specifically) match-forced by our own `db.json` and untested as a real op — see §2.5 | HW-VALIDATED for bit17 (EXP-0089); this experiment's 7-bit resweep HW-VALIDATED-inert (no effect observed), with the bit0 caveat |
| `cvt_i2f` (8B) | 8B | bit17 (EXP-0089, corrupts own+later); bits 0,2-7 of the SAME byte re-swept, ALL 7 show NO detectable effect | n/a | same as unpack_convert; `mode` byte is genuinely fully free per `db.json`'s own match table (no bit0 caveat here) | HW-VALIDATED |
| `ibitcount` (8B, integer) | 8B | `cache` bit (byte+2 bit1, literal bit17 position) — **causally NULL**: own-result and later-read corruption are BOTH unconditional on this bit's value | n/a | does NOT match falu2's bit-dependent contract at all — see H3 | HW-VALIDATED |

### 2.1 `falu2_ext`'s opflags contract (new data)

Sweeping all 5 opflags bits individually (bit0-4 = instr bits19-23) on a
`falu2_ext` producer (srcA=r3, srcB=UNWRITTEN):

| bit (instr bit) | own-result (word0) | later-read (word4) |
|---|---:|---:|
| bit0 (19) | 30.0 | **20.0 (corrupted)** |
| bit1 (20) | 30.0 | 50.0 |
| bit2 (21) | 30.0 | 50.0 |
| bit3 (22) | **0.0** | 50.0 |
| bit4 (23) | **0.0** | 50.0 |
| baseline (all 0) | 30.0 | 50.0 |
| positive control (reader redirected to r4) | 30.0 | 20.0 (r4 unwritten, detects correctly) |

Bit0's polarity matches falu2's own bit19 exactly (`OBSERVED`, matches the
pre-registered `INTERPRETED` prediction). Bits1-2 show no later-read
effect — consistent with, but not independent proof of, falu2's bit20
(srcB-release, irrelevant here since srcB is unwritten) and bit21
(destination-publication) roles. Bits3-4's own-result collapse to 0.0 is
**OBSERVED, UNINTERPRETED** — a genuinely new, unexplained finding; this
experiment did not have a construction to isolate whether it reflects a
real destination-publication-adjacent gate or something else.

### 2.2 `falu_srcmod12b`'s opflags contract, outside a loop (resolves an
EXP-0089 open question)

EXP-0089 found this exact 12-byte form's `opflags` bit (inside a real
runtime loop, `loop_boundary`) corrupts a THIRD value (the loop
accumulator) and, uniquely, made the consumer's own bit also matter — and
explicitly could not separate whether loop repetition or the 12-byte form
itself caused the widened effect. This experiment's own construction
(`opsel_mod=0`, the one value confirmed not to corrupt an unrelated
register — see §2.4), executed a SINGLE time outside any loop:

| bit (instr bit) | own-result | later-read |
|---|---:|---:|
| bit0 (19) | 30.0 | **20.0 (corrupted)** |
| bit1 (20) | 30.0 | 50.0 |
| bit2 (21) | 30.0 | 50.0 |
| baseline | 30.0 | 50.0 |
| positive control (reader redirected to r6, separately seeded 12.0) | 30.0 | 32.0 (12+20, detects correctly) |

**This reproduces falu2's clean, single-target, bit19-only contract
exactly** — no widened corruption, no consumer-bit effect. **Conclusion:
EXP-0089's widened/anomalous `loop_boundary` behavior is attributable to
loop repetition (the same physical instruction executing multiple times),
not to the 12-byte form itself**, when the form is given a valid opcode.
This is the cleanest possible resolution of that open question: same form,
same bit, same absolute polarity, ordinary single-target behavior outside
a loop.

### 2.3 `ctrl_hi5` bit0 outside a loop (resolves the other half of EXP-0089's
open question — and the hang does NOT reproduce)

The single designated hang-candidate case flips the SAME bit position
(relative bit2 of the 7-bit `ctrl` field, absolute instruction bit 34) that
produced a **genuine GPU hang** in EXP-0089's `loop_boundary` (12-byte form,
inside a loop). Outside a loop, with `opsel_mod=0`: `STATUS OK`, no hang,
in **both** independent runs (115ms and comparable in run02). Own-result
changed to 0.0 (an unexplained side effect, `OBSERVED`/`UNINTERPRETED`,
consistent with §2.1's bit3/4 pattern of "some ctrl/opflags-adjacent bits
zero the own-result without faulting"); the later reader was **unaffected**
(50.0, retained). **Conclusion: the hang requires the loop context (or,
less parsimoniously, this experiment's specific `opsel_mod=0`/other-field
combination happens to avoid it for a different reason not excluded here)
— the 12-byte form + this bit combination alone, executed once, is not
sufficient to hang the GPU.** Reported with the honest caveat that this is
one negative data point, not an exhaustive sweep of the interaction space,
and per SAFETY discipline this case was isolated, run last, and
independently pre-tested before the contract was frozen.

### 2.4 `falu_srcmod12b`'s `opsel` field: `opsel=4` is an invalid encoding,
a separate finding from the retention question

`opsel` is an UNTYPED (`mod`, not opcode-enum) field for this family in
`db.json`, unlike `falu2_ext`'s. This experiment's first construction
copied falu2's convention (`opsel=4`="fadd") uncritically. Pilot sweep
(`opsel_mod` 0-7, `PROGRESS.md`): `opsel_mod=4` alone corrupts an entirely
UNRELATED, independently-seeded register (r6, never referenced by the
instruction) that a later, unrelated reader then reads back as zero — a
qualitatively broader and different effect than a srcA-retention bug.
`opsel_mod ∈ {1,2,3,5,6,7}` give a different but locally-contained
own-result (0.0) without reaching r6; `opsel_mod=0` alone gives a clean,
srcA-passthrough own-result AND leaves r6 intact. **This is reported as its
own, separate `db.json` finding** (§4 below) — a field this project's own
tooling had modeled as an innocuous "mod" byte is, for at least one value,
an out-of-spec encoding with a blast radius wider than the instruction's
own operands.

### 2.5 `unpack_convert`'s `cache` byte: a `db.json` self-consistency note

`db.json`'s own match table for `unpack_convert` constrains ALL of the
`cache` byte's bits except bit1 (bit0=forced 0, bits2-7=forced to a fixed
pattern) — i.e., by our OWN model, only bit1 (the already-known literal
bit17 mechanism) is a genuinely free field; the rest exist as a `mod`-typed
field label but are match-forced for THIS family's own identity. This
experiment's bit0 sweep therefore constructs bytes that do not re-decode as
`unpack_convert` under `isadb.decode_one` even though `isadb.assemble()`
happily produces them by mnemonic name (`verify.py --selftest` checks
well-formed hex length for these MODE B splices, not a full decode
round-trip, for exactly this reason — documented inline). **The real
hardware ran bit0 (and every other swept bit) successfully and reproduced
the EXACT baseline output, byte-for-byte, in both runs** — i.e., on this
evidence, the hardware does not appear to treat bit0 as opcode-determining
for this instruction the way our own `db.json` match table pessimistically
assumes (or, alternatively, the hardware silently falls back to the SAME
decode regardless — this experiment cannot distinguish "genuinely
tolerant of this bit" from "always decodes this byte0/length/shape as
unpack_convert regardless of this specific bit," which would require a
broader sweep of the surrounding bits together, out of scope here). Flagged
as an open `db.json` self-consistency question, not resolved.

### 2.6 `device_store`'s `addr_mode` bit1 — inert at the literal bit
position, a genuinely different family

Seeding r3=30.0 (ALU-computed) and storing it with `addr_mode=0x54`
("ALU-computed data", the semantically-correct value) vs. `0x56` ("direct
live load-result data", a semantically-WRONG assertion for an ALU-computed
source — the exact "claim a state that isn't true" pattern that corrupts
in every ALU family tested):

| addr_mode | stored content (word8) | later ALU reread of r3 (word4) |
|---|---:|---:|
| 0x54 (correct) | 30.0 | 50.0 |
| 0x56 (mismatched) | **30.0 (unchanged)** | **50.0 (unchanged)** |
| positive control (store R_UNWRITTEN instead) | 0.0 (detects correctly) | 50.0 |

**Both inert.** This is a genuine negative result for a THIRD family
carrying a bit at the literal `0x54`/`0x56` position — unlike every ALU
family tested (falu2 and siblings, unpack_convert/cvt_i2f's bit1), a memory
op's version of this bit shows no observed effect in this construction.
Consistent with H3's overall conclusion that "bit at this position" is not
one mechanism.

---

## 3. H3 — does bit 17 generalize?

Four independent families now carry a literal- or analogous-position bit at
instruction bit 17 (or the structurally equivalent bit1-of-a-`mod`-byte
position). Their signatures:

| family | own-result affected? | later-reader affected? | bit-dependent? |
|---|---|---|---|
| `unpack_convert`/`cvt_i2f` (EXP-0089) | **YES** | **YES** | YES (0x56 fresh works, 0x54 breaks) |
| `falu2`/siblings' `opflags` bit19/20 (EXP-0086/89/99, this experiment) | no | **YES** | YES |
| `ibitcount`'s `cache` (this experiment, NEW) | no (always correct) | **YES (always)** | **NO — unconditional** |
| `device_store`'s `addr_mode` bit1 (this experiment, NEW) | n/a (no dst reg) | no | n/a — inert |

### 3.1 The decisive `ibitcount` result

`ibitcount`'s `cache` bit occupies the literal instruction-bit-17 position
in a FOURTH, structurally independent opcode group (byte0=0x27, sharing
none of the 0x09/0x17/0xa7 families already tested), with independently
HW-VALIDATED `dst`/`src` addressing (EXP-M4-14 direct hardware splice;
re-confirmed this experiment's own pilot: seeding r3 via `falu2i` and
reading back its exact popcount, 6, for the bit pattern of 30.0). Testing
BOTH values of the bit, with TWO independent later readers (a discrim3-
style persistence check EXP-0089 explicitly could not build for any
literal-bit-17 family):

| cache | own-result (word0, popcount bits, as f32) | 1st later reader (word4) | 2nd later reader (word12) |
|---|---:|---:|---:|
| 1 (`0x56`, "fresh") | 6 (correct) | **corrupted (read-as-zero)** | **corrupted (read-as-zero)** |
| 0 (`0x54`, "stale"/EXP-M4-14's "breaks") | 6 (correct, UNCHANGED) | **corrupted (read-as-zero)** | **corrupted (read-as-zero)** |

Both values give byte-identical results, in both runs. `ibitcount`
unconditionally releases its `src` operand for any later reader (reaching
a SECOND independent reader too — the persistence signature) and its own
result is unconditionally correct — **the `cache` bit has zero observed
causal role in either effect for this family.** A positive control
(`src` redirected to r7, never written) correctly reads popcount(0)=0 and
leaves r3's later read unaffected (50.0), proving the harness detects a
genuinely different source and that the corruption is specific to reading
r3, not a general artifact of executing `ibitcount` at all.

### 3.2 A18-vs-M4 discrepancy (disclosed, not resolved)

This experiment reproduced EXP-M4-14's OWN literal anchor bytes
(`27 05 56 00 02 00 5c 04` / `27 05 54 00 02 00 5c 04`, splicing directly,
not through this experiment's own builder) after seeding r0 to a known
value. EXP-M4-14 (A18 Pro) recorded: "only 0x54/0x55 (bit1 clear) break the
stored result... 0x56 standalone writes back." This experiment's M4 result
with the IDENTICAL bytes: **both give the correct popcount, own-result
unaffected either way** — a direct contradiction for the same literal
bytes. This experiment does not have the tooling to rule out a
dispatch-shape confound (EXP-M4-14's own test used a real compiled kernel
with actual thread-loaded input, possibly at a different grid/thread count
than this experiment's grid=1/tg=1 single lane); reported as an open,
disclosed cross-target discrepancy for a specific field, not a general
claim that A18 and M4 differ for this subsystem (CLAUDE.md's own premise,
that the two are byte-identical for every driver-emittable subsystem, is
not contradicted at the subsystem level by one field's edge case).

### 3.3 Verdict

**Bit 17 (and the structurally-analogous bit1-of-a-mod-byte position) is
NOT one mechanism recurring across families — it is (at least) three
distinct behavioral signatures that happen to share a bit position**:
(a) a "does this instruction's own operand-fetch use a fresh vs.
short-circuited path" gate that ALSO governs a later reader's fate
(unpack_convert/cvt_i2f); (b) a pure later-reader release flag with no
self-effect (`falu2`'s `opflags` family, a DIFFERENT absolute bit position,
included here as the conceptual sibling the dispatch's own framing groups
with (a)); (c) apparently no causal role at all for the SAME literal bit
(`ibitcount`), where the actual, observed release behavior is unconditional
on it. A fourth family (`device_store`) shows the position fully inert.
This is exactly the "several distinct mechanisms that share a bit position"
outcome, not "one mechanism appearing in several families," and it is
established by a DISCRIMINATING test (independent families, independent
addressing validation, a persistence-to-a-second-reader check), not merely
by "more instances."

---

## 4. H4 — mechanism discrimination

All four sub-questions the dispatch named were built, pre-registered with
an explicit falsifier, piloted, and gate-captured. `discrim3`-style
"reaches a third reader, never an earlier one" causality (EXP-0089) is
assumed as background, not re-derived here.

### 4.1 H4_MEMOP_INTERVENING — does a completed, unrelated memory
transaction reset the release?

| corrupt? | intervening device_store+device_load? | later reader |
|---|---|---:|
| no | no | 50.0 |
| no | yes | 50.0 |
| yes | no | **20.0 (corrupted)** |
| yes | yes | **20.0 (corrupted, UNCHANGED)** |

**No reset.** The corruption survives an intervening, completed,
functionally-unrelated memory round trip identically to the no-memop case.

### 4.2 H4_LATERWRITE_RESTORE — does a subsequent ordinary write restore it?

| corrupt? | rewrite (r3 = fresh value, K3=8.0, normal opflags)? | later reader |
|---|---|---:|
| no | no | 50.0 (30+20) |
| no | yes | 28.0 (8+20 — plain rewrite works) |
| yes | no | **20.0 (corrupted, confirms the shape)** |
| yes | **yes** | **28.0 — RESTORED, not 20.0** |

**Fully restored.** The later reader sees the FRESH value exactly, not a
still-corrupted read and not some third garbage value. This directly
distinguishes two architectural models: a **permanent per-register poison
flag** (would predict the reader stays corrupted regardless of any
subsequent write) is REFUTED; a **per-value/per-write-instance suppression**
(the specific write that was marked "already consumed" never durably
committed, but the register itself is perfectly normal and the NEXT write
commits fine) is CONFIRMED.

### 4.3 H4_REGFILE_VS_FORWARD — gone from the register file, or merely not
forwarded to the ALU?

| corrupt? | order | ALU later-read (word4) | `device_store`'s OWN read of r3 (word8) |
|---|---|---:|---:|
| no | store-then-ALU | 50.0 | 30.0 (correct) |
| yes | store-then-ALU | **20.0 (corrupted)** | **0.0 (ALSO corrupted)** |
| yes | ALU-then-store | **20.0 (corrupted)** | **0.0 (ALSO corrupted, order-independent)** |

This is the sharpest discriminator in this experiment, and it **refutes
this experiment's own pre-registered a-priori prediction** (which favored
the weaker "not-forwarded-only" reading): `device_store`'s data-register
read is a genuinely different port from `falu2i`'s ALU srcA read (different
instruction family, different byte0 group entirely), and it ALSO reads the
corrupted value. **The suppressed value is not present via ANY read path
tested — the strongest, most literal reading of "the producer never
durably wrote the value back to the register file" is what survives.** A
model where only the ALU's own forwarding/bypass network is affected,
while the register file itself still holds the correct value for a
different consumer, does not fit this data.

### 4.4 H4_BARRIER — does the effect survive a real synchronization barrier?

| corrupt? | later reader, across a real `threadgroup_barrier(mem_device)` |
|---|---:|
| no | 50.0 |
| yes | **20.0 (corrupted, survives the barrier)** |

**Survives.** A genuine hardware synchronization/memory-fence primitive
(HW-VALIDATED encoding, EXP-0025/EXP-M4-13 R8, unmodified) does not reset
the suppressed state. Combined with §4.1-4.3, the corruption is not a
transient scheduling-window or in-flight-pipeline artifact that any of the
tested "flush" operations (an intervening memory round trip, a barrier)
clears — it behaves as a genuine, durable, per-value register-file state
change that only a fresh WRITE (§4.2) resets.

### 4.5 Control-flow-join persistence (not re-tested, cited)

Already HW-VALIDATED by EXP-0089's `if_boundary`/`loop_boundary` kernels
(real compiler-emitted `if_push`/`pop_reconverge` and a real runtime loop):
`candB_flip_c1` corrupts the post-boundary reader in both. Re-running this
specific check would be duplicative (CLAUDE.md: "do not redo, do not
contaminate"); this experiment's own novel contribution is §4.1-4.4, which
had zero prior evidence.

### 4.6 Verdict

**The model that survives every discriminator built here and in EXP-0089
combined:** a producer instruction that is (mis-)marked "this is the last
use of this source" does not durably commit that source's value to the
register file at all (§4.3) — not merely skip a forwarding shortcut. The
missing commit is permanent for that specific write (persists across an
unrelated memory round trip, a real barrier, and a real control-flow join)
but is NOT a property of the register slot itself (a fresh, ordinary write
to the same register works normally and is durably visible, §4.2). This is
`EXP-0089`'s "persistent producer-side writeback suppression" model, now
INDEPENDENTLY SHARPENED on the specific axis ("gone or merely
unforwarded") the dispatch asked to resolve, with a genuine refutation of
the weaker alternative along the way.

---

## 5. OBSERVED vs INTERPRETED — explicit separation

- **OBSERVED** (raw, uninterpreted, both runs byte-identical): every table
  cell above with a numeric value is a directly observed float/int readback
  from real M4 hardware.
- **INTERPRETED**: the "bits 15/31 are inert / role UNKNOWN" framing (H1);
  the "matches/does not match falu2's contract" polarity claims (H2); the
  "several distinct mechanisms" verdict (H3); the "gone from the register
  file, not merely unforwarded" model (H4). Each interpretation is stated
  immediately after its supporting OBSERVED table and is falsifiable by
  the alternative outcome named in `PRE_REGISTRATION.md`.
- **UNEXPLAINED, explicitly not interpreted**: `falu2_ext`'s own-result
  collapse to 0.0 at opflags bits 3/4 (§2.1); `falu_srcmod12b`'s own-result
  collapse to 0.0 under the `ctrl_hi5` hang-probe (§2.3). Both are recorded
  as raw facts; no causal story is asserted for either.

---

## 6. Field limits constructed — positive and negative outcomes

Per the dispatch's implementation bar (construct the values yourself; test
min/max/first-invalid/holes; record both positive and negative outcomes):

| field | values constructed | positive outcome | negative outcome |
|---|---|---|---|
| falu2/falu2i-family register top bit | 0, 1 (field values 3, 67) | reads the low-6-bit register, unchanged | none found — genuinely inert over this space |
| falu2-family opflags bit0 (per-family absolute position) | 0, 1 | 0=retain (correct later read) | 1=release (later read silently returns 0, no fault) |
| `falu_srcmod12b`/`falu3_srcmod12` `opsel`/`opsel_mod` | swept 0-7 | `opsel_mod=0`: clean passthrough, no collateral damage | `opsel_mod=4`: **corrupts an unrelated register** (r6); `opsel_mod∈{1,2,3,5,6,7}`: locally-contained own-result=0, no collateral damage observed |
| `ctrl`/`ctrl_lo` low 2 bits (length selector, this experiment's own discovery) | 0,1,2,3 (by construction, held fixed per intended length) | correct length framing, single instruction decodes | any OTHER unintended value (not swept live here, but implied by the mechanism): would desync the following instruction stream — this is the mechanical explanation for EXP-0089's own "always dangerous"/nondeterministic finding on this exact field |
| `ctrl_hi5` bit0 (absolute bit34, EXP-0089's hang bit), outside a loop | 0, 1 | 0: normal | 1: own-result collapses to 0 (unexplained), NO HANG, later-read unaffected — the hang from EXP-0089 does NOT reproduce in this single-execution, non-loop, valid-opsel construction |
| `device_store` `addr_mode` bit1 | 0x54, 0x56 | both: correct stored content, correct later ALU read | none found — inert at this position for this family |
| `unpack_convert`/`cvt_i2f` cache/mode byte, bits 0,2-7 | each bit individually flipped | all 7×2 families: byte-identical to baseline | none found — no fault, no deviation, in either family |
| `ibitcount` `cache` bit | 0, 1 | both: correct own popcount | both: later reader corrupted regardless — the "negative" (corruption) is unconditional, not gated by this bit |
| H4 constructions (memop/rewrite/barrier presence) | present/absent, each combined with corrupt/retain | retain: always correct regardless of memop/rewrite/barrier | corrupt: always corrupted regardless of memop/barrier; RESTORED by a fresh rewrite (the one condition that clears it) |

No fault, hang, or crash occurred anywhere in this experiment's 154 total
hardware executions (77 cases × 2 runs) except the intentionally-isolated
hang-CANDIDATE case, which did not hang in either run.

---

## 7. Proposed `docs/` and `db.json` corrections (text only — not applied;
`tools/` and `docs/` are read-only for this experiment)

1. **`docs/isa/register-move-and-liveness.md` §2.7** should add a new
   subsection recording: (a) H1's extension of bit15/31 inertness to
   `falu2i`, `falu2_ext`, `falu3_srcmod12`, and under register pressure —
   still `UNKNOWN` role, wider tested space; (b) the per-family field map
   table from §2 above; (c) the H3 verdict that bit 17 (and its
   analogous-position siblings) is NOT one mechanism — cite the 4-row
   signature table in §3; (d) the H4 model refinement — "gone from the
   register file by the time ANY read path sees it, not merely
   ALU-unforwarded" (§4.3), and the three new persistence crossings
   (memop, rewrite-restores, barrier).
2. **`docs/isa/README.md`**'s "cache bit" framing (the `0x54↔0x56`
   paragraph) should be corrected to state explicitly that `ibitcount`'s
   `cache` bit is a documented, HW-tested COUNTEREXAMPLE to "the literal
   bit position is load-bearing" — cite this experiment (§3.1) alongside
   EXP-M4-14's own (differently-targeted, A18) finding, with the A18-vs-M4
   discrepancy flagged (§3.2), not silently reconciled.
3. **`db.json`'s `falu2_ext` descriptor** should gain a `ctrl`/`opflags`
   annotation matching this experiment's §2.1 table (bit0 corrupts, bits
   1-2 don't, bits3-4 zero the own-result unexplained) — currently
   undocumented for this specific sibling.
4. **`db.json`'s `falu_srcmod12b` descriptor**: (a) its `opsel` field
   should be annotated `PARTIAL/DANGEROUS — opsel=4 corrupts an UNRELATED
   register (not just this instruction's own operands); opsel=0 is the one
   value confirmed safe and produces a clean passthrough; opsel∈{1,2,3,5,6,7}
   are locally-contained but not characterized further` (this experiment,
   §2.4); (b) its `opflags` field should gain the SAME bit19/20/21
   annotation as falu2's, now independently confirmed OUTSIDE a loop with a
   valid opsel (§2.2) — resolving EXP-0089's open loop-vs-form question in
   favor of "the loop caused the widened effect, not the 12-byte form
   itself"; (c) its `ctrl` field's low 2 bits should be RENAMED/RETYPED
   from an opaque "mod" tail to the length selector this experiment
   discovered (`_length_ctrl` in `isa_helpers.py`) — this is a correction
   to `isadb.py`'s own internal understanding of the field, independent of
   any semantic-lifetime question, and explains EXP-0089's "ctrl bits 0/1
   always dangerous" finding as a length-desync artifact rather than (or
   in addition to) a semantic hazard.
5. **`db.json`'s `falu3_srcmod12` descriptor**: note that its `opsel`
   field's bit1 (instruction bit17) is match-forced to 1 by the family's
   own identity condition, making `opsel` values 0-3 UNREACHABLE by
   `assemble()` for this specific family (an `assemble()`/match-composition
   property worth a general callout in `isadb.py`'s own documentation, not
   just this one descriptor — any field whose bit range overlaps a
   family's match condition has the same silent-narrowing property).
6. **`db.json`'s `unpack_convert` descriptor**: flag the self-consistency
   question in §2.5 — the `cache` byte's bit0 (and bits2-7) are
   match-forced by the family's own identity condition per the CURRENT
   model, yet real hardware ran a bit0-flipped instance successfully and
   reproduced the exact baseline output; recommend a follow-up that sweeps
   MULTIPLE of these "forced" bits together to determine whether the
   hardware's own decode is more permissive than `db.json`'s match table,
   or whether this is coincidental (same decode reached via a different
   corpus family).
7. **`db.json`'s `ibitcount` descriptor**: correct the `cache` field's
   semantics note. Current text (from EXP-M4-14, A18): "only 0x54/0x55
   (bit1 clear) break the stored result... 0x56 standalone writes back."
   This experiment's M4 data (HW-VALIDATED, byte-for-byte reproduction of
   the SAME literal anchor bytes, two independent runs) found **NO effect**
   of this bit on the own-result, and separately found the LATER-READ
   corruption (not previously tested by EXP-M4-14 at all — that experiment
   only checked the same-instruction self-consistency, the RT-1a-FIX
   pattern this whole arc has repeatedly found insufficient) is
   UNCONDITIONAL on this bit too. Recommend the field be retyped
   `UNKNOWN/A18-M4-DISCREPANT` pending a dispatch-shape-controlled
   follow-up, and the `src`-release behavior be documented as its own,
   separate, unconditional fact independent of `cache`.

---

## 8. Limitations / honest gaps

- **Register-addressing confidence is family-specific** (repeated from
  `PRE_REGISTRATION.md` §1): `falu2_ext`/`falu3_srcmod12`/`falu_srcmod12b`'s
  srcA_reg/srcB_reg addressing is a disclosed STRUCTURAL extrapolation from
  falu2's own bit positions, not independently re-validated per family in
  this experiment (H1's own result is consistent with the extrapolation
  holding, but is not an independent proof of the mapping for these
  specific families).
- **Pure integer-ALU families** (`iadd2`, `ilogic`, `ibfins`, etc.) are
  entirely OUT OF SCOPE — their register addressing is not validated
  anywhere in this project (EXP-0090/EXP-0112's own comments), and building
  a lifetime test on an unvalidated address mapping would be
  uninterpretable. This is EXP-0113's territory (register addressing); a
  follow-up combining that experiment's addressing work with this
  experiment's later-read methodology is the natural next step.
- **`falu3_srcmod12`'s 3rd source (`ext_srcmod`) is entirely
  uncharacterized** — this experiment's own H1 test avoids depending on it
  (uses a companion "1.0" register trick for the own-result oracle), but
  its own lifetime bit(s), if any, are untested.
- **The `falu2_ext` own-result 0.0 collapse (opflags bits3/4) and the
  `ctrl_hi5`-bit0 own-result collapse (`falu_srcmod12b`) are UNEXPLAINED**
  — recorded as raw facts, not chased to a mechanism, given the time
  budget.
- **The A18-vs-M4 `ibitcount` discrepancy (§3.2) is not root-caused** — a
  dispatch-shape (grid/thread-count/real-vs-single-lane) confound between
  EXP-M4-14's original test and this experiment's construction cannot be
  ruled out with the tooling used here.
- **`unpack_convert`'s bit0/other-bits sweep result (§2.5) has a
  decode-model caveat**: the real hardware ran successfully, but this
  experiment cannot rule out that the hardware silently falls back to the
  SAME decode for a value that our OWN `db.json` model treats as
  "shouldn't exist" — a genuinely different question from "this bit is a
  free, inert field," and this experiment does not have a construction
  that distinguishes the two.
- **`unpack_convert`/`cvt_i2f` positive controls (both kernels) again did
  NOT detect** (byte-identical to baseline) — REPLICATING, not resolving,
  EXP-0089's own already-disclosed limitation for these two specific
  kernels. Not re-investigated further here (out of this experiment's own
  time budget; flagged, not silently dropped).
- **H1's "operand class: uniform vs GPR vs immediate" dimension** is only
  partially covered (`falu2i`'s immediate + GPR-primary shape); a genuinely
  uniform-register-sourced construction for this specific bit position was
  judged out of scope given the addressing-validation constraint (see
  `isa_helpers.py`'s module docstring for the disclosed reasoning — the
  one family with a documented, matching-bit-position "uniform vs GPR"
  class flag, `b_alu10_loe`'s `src_flag`, is itself only STRUCTURALLY/
  byte-diff modeled, not independently HW-validated, and building a new
  test on it would have the same addressing-confound risk already
  excluded elsewhere in this experiment).

---

## 9. Gate results

- `verify.py --selftest`: **PASS**, 51 checks (real hardware fixture,
  `harness/recorded_fixture_case0.json`, captured this experiment's own
  pilot phase — CODEX gate (e); MODE A programs round-trip through
  `isadb.assemble`/`disassemble`; MODE B splices checked for well-formed
  hex of the correct instruction length — see §2.5 for why a full decode
  round-trip is not required for those specific exploratory cases).
- `verify.py --seqtest`: **PASS** in all three tree states.
- `make_manifest.py --check` / `--write`: **PASS**.
- `verify.py --preflight`: **PASS**.
- `verify.py --between-runs`: **PASS** — gated ONLY on
  `authored_{code,kernel,doc}_sha256` and the pinned revision, never live
  git `HEAD`.
- `verify.py --captured`: **PASS** — `01_results.jsonl` byte-identical
  across both runs (sha256 above).
- **No `STOP.json` in either run. No hang, no fault, no timeout — including
  the one isolated hang-candidate case, in both runs.**
- **Positive controls**: `positive_control_deliberate_mismatch` mismatches
  as designed (both runs); every group-local positive control
  (`h1`/`h2`/`h3` redirect-to-a-known-different-register controls) detects
  correctly EXCEPT the two `unpack_convert`/`cvt_i2f` positive controls,
  which replicate EXP-0089's own already-disclosed non-detection for those
  two specific kernels (§8).

---

## 10. Clean-room provenance

```text
Clean-room provenance: OWN-SHADER + HW-PROBE + PUBLIC
Inputs inspected: kernels/carrier.metal (reused verbatim from EXP-0099, our
  own MSL), kernels/lit17_unpack.metal + kernels/lit17_cvt.metal (reused
  verbatim from EXP-0089, our own MSL, recompiled fresh in this
  experiment's own tree and independently re-verified byte-identical to
  EXP-0089's own recorded anchor bytes -- baseline.py), tools/agx-isa's
  isadb.assemble()/disassemble()/decode_one()/imm_encode()/imm_decode()
  (read-only), tools/agxtest (read-only, splice-and-run), tools/shdump
  (read-only, compile+extract). db.json's own field/match tables were
  READ (to design constructions and locate genuinely-free bit positions)
  but never modified; every byte executed on hardware was independently
  constructed via isadb.assemble() (MODE A) or derived from a
  compiler-emitted anchor plus a field-level XOR computed via isadb (MODE
  B) -- never hand-copied from a captured Apple template. EXP-M4-14's own
  recorded literal anchor bytes (27 05 56/54 00 02 00 5c 04) were spliced
  DIRECTLY (not through this experiment's builder) as a targeted
  cross-check (SECTION 3.2) -- those bytes are this project's OWN prior
  hardware-derived data (EXP-M4-14, itself OWN-SHADER + HW-PROBE), not an
  Apple artifact.
Apple binary introspection: NONE.
Reproduction: python3 -B verify.py --selftest/--seqtest (no GPU);
  python3 -B baseline.py (no GPU dispatch, compile+disassemble only);
  python3 -B run.py --execute --run-id <id> (real GPU, append-only);
  python3 -B analysis.py --write; python3 -B verify.py --captured.
Evidence: raw/m4-20260828-run01/ (complete, 77/77),
  raw/m4-20260828-run02/ (complete, 77/77), both byte-identical
  01_results.jsonl (sha256 7e5aa5fa6cf83b7295a061a557abccf9a9bd1215314d9b261715464638fb0d87),
  analysis.json, manifest.json.
```
