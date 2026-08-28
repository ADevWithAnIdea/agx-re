# RESULTS -- EXP-0126 M4 register-lifecycle boundary probe

## Evidence status

**Both contracted runs complete and gate-passing.** `raw/m4-20260828-run01`
and `raw/m4-20260828-run02`, 58/58 cases each, `STATUS OK` in every single
case in both runs (zero faults, zero hangs, zero timeouts, zero
command-buffer errors, host never wedged). `verify.py --selftest` (192
checks), `--seqtest`, `--preflight`/`--between-runs`, `--captured` all
**PASS**. `01_results.jsonl` is **byte-identical** across both independent
runs (`sha256 9bcdb378fe47a019abd1a3f228ca94c034788ffedc06baa2c836933bd48e1b1e`).
56/58 cases matched their pre-registered oracle in both runs; the 2 that
did not (`h3_modeb_grid1_stale`, `h3_modeb_grid4_stale`) are **designed to
mismatch** -- they carry the PRE-BREAKAGE oracle so the mismatch itself is
the recorded evidence of the breakage (see H3). Every finding below is
**HW-VALIDATED** (independently constructed, spliced, and observed on real
M4 hardware, two independent full runs, byte-identical) unless explicitly
marked otherwise. Target: **M4/G16G only**; no A18 Pro evidence (hands-off
per user directive); no M5 evidence.

This experiment's own pre-registration pilot found and fixed four real
bugs before any gated capture (full detail: `PRE_REGISTRATION.md` section
0, `PROGRESS.md`): a fragment-stage MODE-B splice target that could not be
confirmed live on the rendered-pixel path (H1's fragment axis is
consequently NOT REACHED, disclosed below rather than faked); one wrong
opflags nibble in the first hand-transcription of EXP-0112/EXP-0090's own
CF skeleton, caught by a byte-exact diff before any hardware run;
`falu2i`'s `mods=0xC0` requirement for load-sourced operands (EXP-0101's
own already-published finding, omitted by a first pilot attempt); and
`agxtest.py --splice`'s offset being relative to the symbol region, not
the archive's absolute file offset (an early H3 pilot spliced past the end
of a 44-byte kernel and produced a misleading all-zero readback at every
grid size).

---

## 0. Headline

**H1 (bits 15/31): CONFIRMED inert for addressing and retention across
every REACHED new axis** -- a real loop+if/else control-flow boundary, a
`device_load`-sourced operand, and ~40-register pressure with the highest
live index at r55 (near EXP-0112's own 64-register-alias boundary). A
FOURTH axis (half/b16 width) also shows no effect from the field or the
retention bit, but the surrounding construction itself carries a
disclosed, unexplained anomaly (see H1.3). The field's role remains
`UNKNOWN`; the space over which it is HW-tested reserved/inert is now
wider than any prior experiment established, and is stated exhaustively
below. Fragment stage and the uniform-register operand class are **NOT
REACHED** (disclosed, not silently dropped).

**H2 (is bit 17 one mechanism or several): a genuinely new, sharper
answer than "several distinct mechanisms."** `ibitcount`'s later-read
corruption is **not** hardwired/uncontrollable -- it has a real,
bidirectional, non-confounded release-control bit, just relocated to
`srcdesc` bit4 (byte6 bit4), NOT `cache`/bit17. `cache` stays
independently inert even once the real control bit is at its
non-releasing setting. This reframes EXP-0119's "ibitcount's cache bit is
causally inert" finding (still correct as stated) into "ibitcount's
control surface for this concept lives at a different literal position
than every other family tested" -- evidence for **one underlying
release-concept, differently routed per instruction family**, not several
unrelated phenomena that merely share a bit position. The newly-found
control bit reproduces falu2's own downstream signatures exactly
(per-write-instance-suppression restore via H2_LATERWRITE,
distance-invariance via H2_DISTANCE).

**H3 (A18-vs-M4 ibitcount discrepancy): RESOLVED as (iii), a context
difference -- specifically OPERAND PROVENANCE, not dispatch shape.**
EXP-M4-14's own literal A18 anchor bytes break the stored popcount at
BOTH grid=1 and grid=4 on a fresh M4 compile (ruling out dispatch shape as
the explanation). A MODE A hand-built construction with a
`device_load`-sourced register breaks at cache=stale AT GRID=1 already
(matching EXP-0119's own single-lane dispatch shape exactly), while the
SAME construction with an ALU-immediate-seeded register (EXP-0119's own
construction, independently re-run in this tree) never breaks, at either
grid size. Both EXP-M4-14's A18 record and EXP-0119's M4 record are
correct for their own construction's context; there is no evidence of a
genuine G17P-vs-G16G microarchitectural difference or an error in either
record.

---

## 1. H1 -- bits 15/31 in further new contexts

### 1.1 H1_CF -- real loop+if/else control-flow boundary

Reused EXP-0112/EXP-0090's own byte-for-byte HW-validated skeleton
(`kernels/carrier_cf.metal`; `baseline.py` re-confirms
`build_cf_topbit_program(0x41)` reproduces a fresh compile of that kernel
exactly, every capture). Varied ONLY the "arm_true" `falu2i`'s `srcA_reg`
field (0x41 = top-bit SET, low6=1/acc, the skeleton's own natural value,
vs 0x01 = top-bit CLEARED, same low6).

| case | parameters | selects | field | observed | oracle | match |
|---|---|---|---|---:|---:|---|
| `h1_cf_true_base` | a=90,n=10 (acc=105) | TRUE arm (own-result of the varied instr) | 0x41 | 210.0 | 210.0 | yes |
| `h1_cf_true_bit15clr` | a=90,n=10 | TRUE arm | 0x01 | 210.0 | 210.0 | yes |
| `h1_cf_false_base` | a=10,n=5 (acc=17.5) | FALSE arm (a SEPARATE, later, independent reader of the SAME register r1/acc) | 0x41 | 14.5 | 14.5 | yes |
| `h1_cf_false_bit15clr` | a=10,n=5 | FALSE arm | 0x01 | 14.5 | 14.5 | yes |
| `h1_cf_positive_control` | a=90,n=10 | TRUE arm | 0x46 (low6 changed 1->6, reads the loop-counter register, not acc) | 0.0 | 0.0 | yes |

**Addressing** (TRUE-arm pair): clearing the top bit never changes the
varied instruction's OWN result. **Retention** (FALSE-arm pair): clearing
the top bit on the EARLIER instruction never changes a SEPARATE, later,
independent reader of the same register, evaluated across a real
loop-then-if/else reconvergence boundary. The positive control (low6
changed, not the top bit) reads 0.0, proving the harness detects a real
addressing change at this exact field position. **Verdict: bits 15/31
remain HW-tested inert for addressing and retention across a genuine
compiler-shaped control-flow boundary**, not just EXP-0086/89's
compiler-emitted `if_boundary`/`loop_boundary` kernels (which tested
`opflags`, a different field) and not just EXP-0119's straight-line
constructions.

### 1.2 H1_LOAD -- device_load-sourced operand (EXP-0101 bridge formula)

r7 seeded via `device_load_fixed(extmode=2*7, dst_lo/dst_ext9=(1,1))`
(EXP-0101's own HW-VALIDATED formula) with LOADVAL=42.0, consumed by
`falu2i` (`mods=0xC0`, required for load-sourced operands per EXP-0101).

| field | opflags bit0 | own (word0) | later (word4) | oracle | match |
|---|---:|---:|---:|---:|---|
| 7 | 0 | 62.0 | 62.0 | 62.0/62.0 | yes |
| 7 | 1 | 62.0 | 20.0 | 62.0/20.0 | yes |
| 71 (7+64, top set) | 0 | 62.0 | 62.0 | 62.0/62.0 | yes |
| 71 | 1 | 62.0 | 20.0 | 62.0/20.0 | yes |

Field=71's own-result is IDENTICAL to field=7's (both read LOADVAL=42.0,
own=42+20=62) -- addressing inert. Retention depends ONLY on the opflags
bit, identically for both field values. **Verdict: bits 15/31 remain
HW-tested inert when the operand's PROVENANCE is a `device_load`, not an
ALU write** -- closing the one operand-class axis EXP-0119 flagged as
reachable-in-principle but untested.

### 1.3 H1_HALFWIDTH -- b16 (srcA_size=0) instead of b32

| field | opflags bit0 | own | later | oracle |
|---|---:|---:|---:|---|
| 3 | 0 | 20.0 | 20.0 | EXPLORATORY |
| 3 | 1 | 20.0 | 20.0 | EXPLORATORY |
| 67 | 0 | 20.0 | 20.0 | EXPLORATORY |
| 67 | 1 | 20.0 | 20.0 | EXPLORATORY |

All four (field, opflags-bit) combinations are byte-identical to each
other: word0=word4=20.0 in every case (i.e. `v` reads as 0, giving
0+K2=20). **This answers the narrow H1 question** -- neither the field nor
the retention bit changes ANYTHING at b16, so bits 15/31 remain
consistent with inert here too -- **but the surrounding construction
carries its own, separately disclosed anomaly**: a diagnostic that seeds
r3 at b16 and reads it back IMMEDIATELY (zero intervening instructions)
correctly returns 30.0, yet this SAME two-instruction shape (seed, then a
SECOND b16 instruction reading it back) reads 0 regardless of field or
opflags bit. This is recorded as OBSERVED, UNINTERPRETED -- a genuinely
new, unexplained b16-specific failure mode this experiment did not have
budget to chase (see Limitations), reported honestly rather than folded
into an unqualified "bits 15/31 are inert at b16" headline.

### 1.4 H1_PRESSURE -- ~40 live registers, highest index r55

40 independent `device_load_fixed` instructions into r16..r55 (each from a
distinct memory word), THEN the standard H1 probe on r3 (untouched by the
pressure loads), inside `carrier_dag.metal`'s 1536-byte MODE A budget
(compiles to 1590 bytes, confirmed fresh by `baseline.py` every capture).

| field | opflags bit0 | own | later | oracle | match |
|---|---:|---:|---:|---:|---|
| 3 | 0 | 50.0 | 50.0 | 50.0/50.0 | yes |
| 3 | 1 | 50.0 | 20.0 | 50.0/20.0 | yes |
| 67 | 0 | 50.0 | 50.0 | 50.0/50.0 | yes |
| 67 | 1 | 50.0 | 20.0 | 50.0/20.0 | yes |

Identical to the zero-pressure baseline pattern in every cell. **Verdict:
bits 15/31 remain HW-tested inert under genuine register-file pressure
pushing the highest live logical register index to r55**, near (but not
across) EXP-0112's own confirmed 64-register-alias boundary for a
DIFFERENT field (device_load's ALU-consumer register addressing).

### 1.5 H1 exhaustive tested space (stated per the dispatch's own bar)

Bits 15/31 (the `falu2`-family `srcA_reg_top`/`srcB_reg_top` fields) are
now HW-tested inert for BOTH addressing and retention across:

- families: `falu2`, `falu2i`, `falu2_ext` (both operand slots),
  `falu3_srcmod12` (both operand slots) [EXP-0099/EXP-0119];
- a real loop+if/else control-flow boundary [this experiment, 1.1];
- a `device_load`-sourced operand [this experiment, 1.2];
- register pressure from 15-deep [EXP-0119] up to ~40 live registers with
  the highest live index at r55 [this experiment, 1.4];
- b16/half width, WITH a disclosed construction anomaly not otherwise
  explained [this experiment, 1.3].

**NOT reached, disclosed:** the fragment stage (attempted, see Limitations);
the uniform-register operand class (no validated hand-construction exists
anywhere in this project, per EXP-0119's own disclosure, unchanged here).
Role remains `UNKNOWN` -- this is a wider bounded-reserved-space statement,
not a resolved mechanism.

---

## 2. H2 -- is the literal-bit-17-position mechanism one thing or several?

### 2.1 H2_BYTESWEEP -- exhaustive sweep of ibitcount's genuinely free bits

`ibitcount`'s db.json match table match-forces most of byte0-2; the only
"mod"-typed fields NOT match-forced and not already fully characterized
are `op_enable` (bits other than the established compute-enable bit1),
`srcdesc` (bits other than the established GPR-read-enable bit6), and
`tail` (fully uncharacterized). Every individually free bit in these three
fields was XORed against the anchor (0x02/0x5c/0x04 respectively) and
checked against BOTH own-result (popcount=6, `H.bits_f32(6)`) and
later-read (the established 20.0-corrupted / 50.0-retained pair):

| field | bit | own-result | later-read | signature |
|---|---:|---:|---:|---|
| `op_enable` | 0,2,3,4,5,6,7 (7/7) | 6 (correct) | 20.0 (corrupted) | matches the EXP-0119 baseline exactly -- no effect |
| `srcdesc` | 1,2,5,7 (4/7) | 6 (correct) | 20.0 (corrupted) | matches baseline -- no effect |
| `srcdesc` | 0 | **0 (WRONG)** | **50.0 (retained)** | confounded: degraded GPR read |
| `srcdesc` | **4** | 6 (correct) | **50.0 (retained)** | **clean, non-confounded release-control bit** |
| `srcdesc` | 3 | **0 (WRONG)** | **50.0 (retained)** | confounded: degraded GPR read |
| `tail` | 0,1,3,4,5,6,7 (7/8) | 6 (correct) | 20.0 (corrupted) | matches baseline -- no effect |
| `tail` | 2 | **1 (WRONG, not 0 -- a THIRD distinct wrong value)** | **50.0 (retained)** | confounded: degraded read, different failure mode from srcdesc bits0/3 |

19 of 22 swept bits reproduce the established "always corrupts" signature
exactly (a negative result over an exhaustively stated space). **Three
bits break the later-read's unconditional-corruption pattern** -- but only
ONE of them (`srcdesc` bit4) does so WITHOUT also breaking the own-result:
it is a clean, single-variable release-control toggle. The other two
(`srcdesc` bit0/bit3) and `tail` bit2 also flip retention, but ALWAYS in
lockstep with a broken own-result (and two different wrong own-result
values at that: 0 and 1) -- consistent with these bits being part of (or
interacting with) the format/GPR-read-validity gate rather than being an
independent release control: when the instruction does not treat its
source as a normal GPR read at all, there is plausibly "nothing to
release," which would look exactly like "retained" without needing a real
release mechanism to explain it. This experiment reports the distinction
(clean vs confounded) rather than treating all four bits as equivalent
evidence.

### 2.2 H2_INTERACTION -- does `cache` regain a role once `srcdesc` bit4 is
cleared?

| `srcdesc` | `cache` | own-result | later-read |
|---|---:|---:|---:|
| 0x4c (bit4 cleared, the "retains" setting) | 1 | 6 (correct) | 50.0 (retained) |
| 0x4c | 0 | 6 (correct) | 50.0 (retained) |

**No.** With the real release-control bit at its non-releasing setting,
`cache`/bit17 is identically inert for BOTH of its own values --
independently confirming EXP-0119's own "cache is causally inert" finding
holds regardless of the newly-found `srcdesc` bit4's state, i.e. `cache`
and `srcdesc`-bit4 are two INDEPENDENT gates, not two views of the same
control.

### 2.3 H2_LATERWRITE -- does a fresh rewrite restore access?

| rewrite before the later reader? | later-read |
|---|---:|
| no | 20.0 (corrupted, confirms the shape) |
| yes (r3 = K3 = 8.0, normal opflags) | **28.0 = 8+20, RESTORED** |

**Fully restored**, exactly matching falu2's own EXP-0119 H4.2 signature
(a per-write-instance suppression, not a permanent per-register poison).
`ibitcount`'s (now understood to be real, `srcdesc`-bit4-controlled)
release mechanism behaves like every other family's under this
discriminator.

### 2.4 H2_DISTANCE -- does the corruption depend on how far away the later
reader is?

| distance (intervening throwaway instrs) | later-read |
|---|---:|
| 0 (adjacent) | 20.0 (corrupted) |
| 1 (near) | 20.0 (corrupted) |
| 4 (far) | 20.0 (corrupted) |

**Distance-invariant**, matching falu2's own CandB finding (EXP-0089): not
a scheduling-window/pipeline-hazard artifact that a few intervening
instructions clear.

### 2.5 Verdict

**H2 is answered by a genuinely discriminating construction, not more
instances of the same test.** The decisive move was sweeping ibitcount's
OTHER free bits rather than re-testing `cache` in new contexts: this found
a real, working, bidirectional, non-confounded release-control bit
(`srcdesc` bit4) that reproduces the SAME downstream signatures
(restore-on-rewrite, distance-invariance) already established for falu2's
`opflags` bit and consistent with the "persistent producer-side writeback
suppression" model from EXP-0089/EXP-0119. The right reading is: **there is
one underlying release-concept, but each instruction family's ENCODING
routes the corresponding control bit to a different literal position** --
`falu2`/siblings at `opflags` bit19/20 (an absolute position that itself
differs per family, per EXP-0119's own H2 table), `unpack_convert`/
`cvt_i2f` at the literal bit-17 position (with a genuinely different,
self-corrupting downstream signature, still unresolved as same-or-different
underlying mechanism -- see Limitations), and `ibitcount` at `srcdesc`
bit4, nowhere near bit17. This is NOT "several unrelated mechanisms that
happen to share a bit position" in the strong sense the dispatch's
alternative framed -- for ibitcount specifically, the position-sharing
with `cache`/bit17 was always coincidental (bit17 plays no role here at
all, confirmed independently in 2.2), while the RELEASE CONCEPT ITSELF
generalizes. `device_store`'s `addr_mode` bit1 (EXP-0119) remains the one
family where NO control bit for this concept was found anywhere tested
(it has no destination register to protect, consistent with having no
release concept to expose at all).

---

## 3. H3 -- A18-vs-M4 ibitcount discrepancy

### 3.1 H3_MODEB -- EXP-M4-14's own literal bytes, dispatch shape varied

`kernels/iunary_popcount.metal` (verbatim from EXP-M4-14's own corpus),
freshly compiled on M4, spliced at the EXACT anchor EXP-M4-14 used
(`27 05 56/54 00 02 00 5c 04`, relative offset 0x12 -- confirmed byte-for-
byte identical to EXP-M4-14's own recorded bytes by `baseline.py` every
capture), at grid=1 and grid=4, with EXP-M4-14's own 4 input values
(`[15,16,65535,0x40000001]`, expected popcounts `[4,1,16,2]`):

| grid | cache | observed | oracle | match |
|---:|---|---|---|---|
| 1 | fresh (0x56) | popcount(15)=4 (lane0 only; grid=1 dispatches only lane0) | 4 | yes |
| 1 | stale (0x54) | **0** (lane0, WRONG) | 4 | **no (designed to mismatch)** |
| 4 | fresh (0x56) | [4,1,16,2] (all 4 lanes correct) | [4,1,16,2] | yes |
| 4 | stale (0x54) | **[0,0,0,0]** (all 4 lanes WRONG) | [4,1,16,2] | **no (designed to mismatch)** |

**The "stale breaks it" signature reproduces at BOTH grid=1 and grid=4.**
Dispatch shape does NOT gate the effect -- ruling out the confound
EXP-0119 itself named as the one it "does not have the tooling to rule
out."

### 3.2 H3_MODEA -- operand provenance x dispatch shape, MODE A hand-built

| source | grid | cache | own-result | oracle | match |
|---|---:|---:|---:|---:|---|
| ALU-seeded (EXP-0119's own construction) | 1 | 1 | 6 (correct) | 6 | yes |
| ALU-seeded | 1 | 0 | 6 (correct) | 6 | yes |
| ALU-seeded | 4 | 1 | 6 (correct) | 6 | yes |
| ALU-seeded | 4 | 0 | 6 (correct) | 6 | yes |
| device_load-sourced (EXP-0101 formula) | 1 | 1 | 2 (correct, popcount(0x40000001)) | 2 | yes |
| device_load-sourced | 1 | 0 | **0 (WRONG)** | 0 (predicted) | yes |
| device_load-sourced | 4 | 1 | 2 (correct) | 2 | yes |
| device_load-sourced | 4 | 0 | **0 (WRONG)** | 0 (predicted) | yes |

**Operand provenance alone reproduces the effect, independent of dispatch
shape.** ALU-seeded NEVER breaks, at either grid size (matching EXP-0119
exactly, independently re-confirmed in this tree). Device_load-sourced
BREAKS at cache=stale already AT GRID=1 -- i.e. WITHOUT any multi-lane
dispatch at all, the exact axis EXP-0119 held fixed at single-lane. Grid=4
changes nothing for either operand-provenance branch (own-result checked
via a deliberate same-address race across identically-valued lanes -- see
Limitations for why this is safe here and what it does NOT test).

### 3.3 Verdict

**Candidate (iii) -- a context difference, specifically OPERAND
PROVENANCE -- resolves the discrepancy, entirely on M4, without needing
A18 access.** EXP-M4-14's A18 record used a real `device_load`-sourced
kernel; EXP-0119's M4 reproduction used an ALU-immediate-seeded hand-built
program. Both records are correct for their own construction. There is
**no evidence supporting candidate (i)** (a genuine G17P-vs-G16G
microarchitectural difference) -- the SAME M4 hardware shows BOTH
behaviors depending purely on how the source register was produced, which
is a strictly M4-internal, non-cross-target finding. There is **no
evidence supporting candidate (ii)** (an error in the A18 record) -- the
A18 record's own construction (device_load-sourced, real dispatch)
reproduces cleanly on M4 under the matching construction. **If an A18 run
were ever authorized:** the informative test would be EXP-0119's OWN
ALU-seeded MODE A construction (not yet tried on A18) -- this experiment's
prediction, extrapolated from the M4-only evidence above, is that it would
NOT break on A18 either, which would be the single cleanest remaining
falsifier of candidate (i). This experiment does not have A18 access and
does not claim to have tested this; it is named so a future A18-authorized
run knows exactly what to run.

---

## 4. OBSERVED vs INTERPRETED

- **OBSERVED** (raw, uninterpreted, both runs byte-identical): every
  numeric table cell above.
- **INTERPRETED**: "bits 15/31 inert / role UNKNOWN" (H1); "one
  release-concept, differently routed per family" / the clean-vs-confounded
  distinction among the three retention-flipping bits (H2); "operand
  provenance, not dispatch shape, explains the discrepancy" and the
  candidate-(i)/(ii)/(iii) resolution (H3).
- **UNEXPLAINED, explicitly not interpreted**: H1_HALFWIDTH's
  seed-survives-alone-but-not-through-a-second-b16-instruction anomaly
  (1.3); the mechanistic reason `srcdesc` bits0/3 and `tail` bit2 degrade
  the GPR read specifically (rather than merely documenting that they do,
  2.1); whether `unpack_convert`/`cvt_i2f`'s OWN-corrupting signature
  (EXP-0089/EXP-0119) is the SAME release-concept as `ibitcount`'s (now
  understood, `srcdesc`-bit4-controlled) one or a genuinely different
  datapath property -- this experiment did not build a construction that
  distinguishes the two (see Limitations).

---

## 5. Proposed `docs/`/`db.json` corrections (text only -- not applied;
`tools/`/`docs/` are read-only for this experiment)

1. **`docs/isa/register-move-and-liveness.md`** should add a subsection
   recording: (a) H1's extension of bit15/31 inertness to a real
   control-flow boundary, a `device_load`-sourced operand, and ~40-register
   pressure (highest live index r55) -- still `UNKNOWN` role, wider tested
   space, exact list in section 1.5 above; (b) H1_HALFWIDTH's disclosed
   anomaly as an open item, not folded into the inertness claim; (c) H2's
   revised model -- `ibitcount`'s release control is real, HW-VALIDATED,
   and lives at `srcdesc` bit4, not `cache`/bit17; `cache` is confirmed
   independently inert of it; (d) H3's resolution -- the A18-vs-M4
   ibitcount discrepancy is closed as a construction/operand-provenance
   difference, not a genuine target difference, with both prior records
   correct for their own context.
2. **`db.json`'s `ibitcount` descriptor** should gain: (a) `srcdesc`
   (byte6) bit4 annotated as a release-control bit, `HW-VALIDATED` this
   experiment, with the SAME polarity convention as falu2's opflags (a
   value of 1, the anchor's own natural setting, releases; 0 retains);
   (b) `srcdesc` bits 0 and 3, and `tail` bit2, annotated as
   "degrades/changes the computed result -- CONFOUNDED with a retention
   change, likely a GPR-read-validity interaction, not verified as an
   independent release control"; (c) the `cache` (byte2 bit17) field's
   existing "writeback-enable" note should be corrected to state
   explicitly that later-read corruption is unconditional on THIS bit
   specifically (already partially stated per EXP-0119) AND that it stays
   independently inert even when the real control (`srcdesc` bit4) is at
   its retaining setting (this experiment's own H2_INTERACTION, new).
3. **`docs/isa/README.md`**'s A18-vs-M4 discrepancy note (added after
   EXP-0119) should be updated from "disclosed, not resolved" to
   "RESOLVED: operand provenance (device_load-sourced vs ALU-seeded), not
   dispatch shape or a target difference -- cite this experiment's
   H3_MODEB/H3_MODEA."

---

## 6. Limitations / honest gaps

- **H1's fragment-stage axis was ATTEMPTED and is NOT REACHED.** Two
  independent positive controls (a saturated-output pilot, then a properly
  scaled one) both failed to detect a deliberate register-field change at
  the one live-looking compiler-emitted instruction this experiment could
  locate in the fragment stage's `_agc.main.constant_program` region.
  Fragment-stage code structure (a split `_agc.main.constant_program`/
  `_agc.main` layout, unlike compute's single region, and a
  `frag_color_pack` fused epilogue that fully absorbed a simpler test
  kernel's arithmetic) differs qualitatively enough from compute that a
  reliable MODE B splice target could not be established within this
  experiment's time budget. `kernels/fs_adjacent.metal` and
  `harness/fsrun.m` are retained for provenance/audit; no case in the
  frozen matrix uses them.
- **H1's uniform-register operand class remains untested project-wide**
  (repeated from EXP-0119: no validated hand-construction exists for it
  anywhere in this project).
- **H1_HALFWIDTH's anomaly is unexplained** (section 1.3) -- recorded as a
  raw fact, not chased to a mechanism, given the time budget.
- **`srcdesc` bits0/3 and `tail` bit2's own-result-breaking behavior is not
  root-caused** -- this experiment distinguishes "confounded" from
  "clean" (section 2.1) but does not determine WHY those specific bits
  degrade the read (e.g. whether they overlap the same "must be 0x40 for
  GPR read" gate `srcdesc` bit6 already established, or a separate
  mechanism).
- **Whether `unpack_convert`/`cvt_i2f`'s own-corrupting signature is the
  SAME underlying release-concept as `ibitcount`'s (now understood) one,
  or a genuinely different datapath property, is UNRESOLVED.** This
  experiment's H2 discriminator was built specifically for ibitcount
  (which had a clean, uncorrupted own-result to work from); unpack_convert/
  cvt_i2f's own-result IS affected by the SAME bit that affects later-reads
  (EXP-0089's finding), so the same "sweep other bits looking for a clean
  dissociation" method was not re-run there in this experiment (out of
  scope/budget -- a natural next step, not attempted here).
- **H3_MODEA's grid=4 cases do not construct per-lane divergent
  addressing** (section 3.2) -- every lane races to write the SAME fixed
  output word. This is disclosed as answering "does own-result depend on
  provenance x dispatch shape" and NOT "is per-lane output correctly
  separated at grid=4" (H3_MODEB, with real per-thread addressing, covers
  the latter and independently confirms the same qualitative result).
- **No A18 replication.** Every H3 finding is M4-only; the specific
  follow-up an A18-authorized run should perform is named in 3.3.

---

## 7. Gate results

- `verify.py --selftest`: **PASS**, 192 checks (real hardware fixture,
  `harness/recorded_fixture_case0.json`, captured this experiment's own
  pilot phase, case index 0 -- CODEX gate (e); every MODE A case's whole
  program round-trips through `isadb.assemble()`/`disassemble()`; every
  MODE B splice checked for correct instruction-length hex).
- `verify.py --seqtest`: **PASS** in all three tree states
  (PRE_GPU/RUN01_PRESENT/RUN02_PRESENT).
- `make_manifest.py --check` / `--write`: **PASS**.
- `verify.py --preflight`: **PASS**.
- `verify.py --between-runs`: **PASS** -- gated ONLY on
  `authored_{code,kernel,doc}_sha256` and the pinned revision, never live
  git `HEAD`.
- `baseline.py`: **PASS**, every capture -- `CARRIER_LEN`/`DAG_CARRIER_LEN`/
  `CF_CARRIER_LEN` re-derived fresh from a real compile; the reused
  `carrier_cf.metal` skeleton and the `iunary_popcount.metal` k_popcount
  anchor confirmed byte-identical to their source experiments' own
  recorded values.
- `verify.py --captured`: **PASS** -- `01_results.jsonl` byte-identical
  across both runs (sha256 above). No nondeterministic field leaked into
  the gated key set (`grid`/`tg` were added to `GATED_KEYS` deliberately,
  as they are deterministic per-case constants, not per-run artifacts).
- **No `STOP.json` in either run. No hang, no fault, no timeout,
  anywhere** in 116 total hardware executions (58 cases x 2 runs) plus the
  informal pilot/smoke phase (also zero faults/hangs there).
- **Positive controls**: `h1_cf_positive_control` detects correctly (0.0,
  distinct from the true-arm oracle 210.0); H1_LOAD/H1_PRESSURE's own
  retention-bit contrast (50/20, 62/20) serves as an in-test positive
  control proving the harness could have detected corruption; H3_MODEB's
  two designed-to-mismatch cases are themselves the positive evidence of
  the breakage they predict.

---

## 8. Clean-room provenance

```text
Clean-room provenance: OWN-SHADER + HW-PROBE + PUBLIC
Inputs inspected: kernels/carrier.metal (EXP-0119, our own MSL),
  kernels/carrier_dag.metal + kernels/carrier_cf.metal (EXP-0112, our own
  MSL, re-confirmed byte-identical by this experiment's own baseline.py),
  kernels/iunary_popcount.metal (EXP-M4-14's own corpus/halfint/iunary.metal,
  our own MSL, re-confirmed byte-identical by baseline.py),
  kernels/fs_adjacent.metal (authored here, our own MSL, NOT exercised by
  the frozen matrix -- see Limitations), tools/agx-isa's
  isadb.assemble()/disassemble()/decode_one()/imm_encode()/imm_decode()
  (read-only), tools/agxtest (read-only, splice-and-run), tools/shdump
  (read-only, compile+extract). db.json's own field/match tables were READ
  (to locate ibitcount's genuinely-free bits) but never modified. Every
  byte executed on hardware was independently constructed via
  isadb.assemble() (MODE A) or is EXP-M4-14's own recorded literal anchor
  bytes, spliced at a symbol-relative offset (MODE B, H3_MODEB only) --
  this project's own prior hardware-derived data, not an Apple artifact,
  and never hand-copied from a captured Apple template.
Apple binary introspection: NONE.
Reproduction: python3 -B verify.py --selftest/--seqtest (no GPU);
  python3 -B baseline.py (no GPU dispatch, compile+disassemble only);
  python3 -B run.py --execute --run-id <id> (real GPU, append-only);
  python3 -B analysis.py --write; python3 -B verify.py --captured.
Evidence: raw/m4-20260828-run01/ (complete, 58/58),
  raw/m4-20260828-run02/ (complete, 58/58), both byte-identical
  01_results.jsonl (sha256 9bcdb378fe47a019abd1a3f228ca94c034788ffedc06baa2c836933bd48e1b1e),
  analysis.json, manifest.json.
```
