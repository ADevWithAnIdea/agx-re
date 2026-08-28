# RESULTS — EXP-0099 M4 lifetime-field model

**STATUS: CAPTURED / GATE-CLOSED.** Both contracted runs
(`m4-20260828-run01`, `m4-20260828-run02`) complete, 35/35 cases each,
`01_results.jsonl` **byte-identical** across both independent runs
(sha256 `3285bbe122b0e07b80c61b41e4e73eee9a0587e454ad3eb9b44800eb89c52ce4`).
15/35 matched their oracle, 20/35 mismatched — every one of those 20
mismatches is either a deliberate positive control or a hypothesis-testing
case whose oracle recorded a specific model's *prediction*, not a claim
that the case "should" pass (see `PRE_REGISTRATION.md` §3 for the
frozen, pre-registered confirm/refute table). `verify.py --selftest`
(13 checks), `--seqtest`, `--preflight`, `--between-runs`, `--captured` all
PASS. Target: **local Apple M4 / G16G only.** No A18 Pro replication
(hands-off). No M5 evidence used anywhere.

---

## 0. Headline

**H1 REFUTED (current db.json 7-bit-index model) / H1 CONFIRMED
(explainer's "not a full 7-bit index" claim, in the specific sense that
the top bit does not extend addressing) — but H2 (his specific
complementary-pair mechanism) is REFUTED.** `falu2`'s `srcA_reg`/`srcB_reg`
top bit (instruction bit 15 / bit 31) has **zero observed effect** on
either which register is read (H1) or on retention behavior (H2), in every
one of the 8 decisive cases, fully reproduced across two independent
hardware runs. This is a **third outcome**, distinct from both competing
models as stated, and is the experiment's central, load-bearing finding.

**H4 REFUTED for the specific mechanism tested.** The claimed "consumer
route" field (`mod_hi` bits 1–3 / instruction bits 45–47) does **not**
unblock `device_load` → `falu2` consumption at any of its 8 values, with a
paired ALU-sourced control confirming the harness and route field are both
wired correctly. **The load-to-ALU bridge (EXP-0090's blocker #1) remains
open.**

**H5 REFUTED for all three candidate fixes tried.** Neither the
"destination publication" bit, nor 4 padding instructions, nor both
combined unblock `reg_move` reading an ALU-written GPR (EXP-0090's blocker
#2 remains open) — and `reg_move` **also** fails to read a
`device_load`-written GPR, closing EXP-0090's own explicitly-flagged open
question with a negative answer.

**H3 remains UNKNOWN/OPEN** — reasoned from H1's own result (see §5),
not independently probed; no currently-validated mechanism was identified
for addressing registers 64–95 through this instruction family.

**H6 answered via static analysis**: bit 17 in `unpack_convert`/`cvt_i2f`
sits in a byte structurally disjoint from either family's register
descriptor — it is **not** the same field repositioned.

A **decisive, load-bearing decoding defect was also found by static
analysis alone** (no hardware needed): the explainer's own 10-byte "retain
source 0" logic-instruction example does not decode under any
`tools/agx-isa/db.json` family at all.

---

## 1. H1 + H2 — SRCA_PAIR / SRCB_PAIR (decisive, HW-VALIDATED, 2 runs)

### 1.1 Design (see PRE_REGISTRATION.md §1 for the full falsifier table)

Seed register r3 with a known value `V_LOW = 30.0` (the fixed point of
`isadb.imm_encode/imm_decode(42.5)`) via an ALU-only, independently
HW-VALIDATED path (`falu2i`, srcA = an unwritten register — proven to read
exactly 0.0, EXP-0087 MOVE-04). **Register 67 is never written by any
case.** Construct instruction A: `falu2(dst, srcA_reg=X, srcB=UNWRITTEN,
opflags bit19=B19)` for `X ∈ {3, 67}` × `B19 ∈ {0,1}` (4 combinations; `67`
has the SAME low 6 bits as `3` and its weight-64 bit set). Immediately
after, instruction B: `falu2i(dst, srcA_reg=3, K=20.0, opflags=1)` reads
register 3 **again**, as a separate, later reader (EXP-0086's own
"adjacent" methodology). Store both A's own result (word0) and B's result
(word4). Mirrored construction for `srcB_reg`/`Y`/`bit20`.

### 1.2 Observed (both runs, byte-identical)

| case | X (or Y) | test bit | word0 (A's own read) | word4 (B's later read) |
|---|---:|---:|---:|---:|
| srca_low_b19_0 | 3 | b19=0 | **30.0** | **50.0** |
| srca_low_b19_1 | 3 | b19=1 | **30.0** | **20.0** |
| srca_high_b19_0 | 67 | b19=0 | **30.0** | **50.0** |
| srca_high_b19_1 | 67 | b19=1 | **30.0** | **20.0** |
| srcb_low_b20_0 | 3 | b20=0 | **30.0** | **50.0** |
| srcb_low_b20_1 | 3 | b20=1 | **30.0** | **20.0** |
| srcb_high_b20_0 | 67 | b20=0 | **30.0** | **50.0** |
| srcb_high_b20_1 | 67 | b20=1 | **30.0** | **20.0** |

All 8 rows are **fully deterministic**: identical across two independent
process launches, on two independent, fully re-gated hardware runs
(`STATUS=OK`, no faults).

### 1.3 Interpretation

**H1 verdict: the current `db.json` 7-bit-index model is REFUTED.** Field
value 67 (bit15=1 for `srcA_reg`, bit31=1 for `srcB_reg`) reads register
**3**'s value in every case, never register 67's (which, being genuinely
unwritten, would read 0.0 under the literal-index model — that value never
appears in any of the 8 rows). This decisively rules out "the operand byte
is `(reg<<1)|size`, register up to 127" for this bit position, exactly as
the explainer's document claims, and exactly as the background analysis
(`work/COMPILER-EXPLAINER-INTERACTION-20260828.md`) predicted from static
byte decoding alone — now confirmed causally, on hardware, by independent
construction (not merely by decoding a captured example).

**H2 verdict: the specific complementary-pair mechanism he describes is
REFUTED.** Column "word4" depends **only** on B19 (or B20) — `X=3` and
`X=67` give byte-for-byte IDENTICAL results at every B19 value. If bit15
functioned as his "retain" flag (paired with bit19: `(1,0)`=retain,
`(0,1)`=release, with `(0,0)`/`(1,1)` as distinguishable "invalid" states),
the four rows would NOT collapse into two identical pairs the way they do
— `(bit15=0,bit19=0)` and `(bit15=1,bit19=0)` would be different encoded
states under his model, yet they produce the same result (50.0) in this
data, and likewise for the two bit19=1 rows (20.0). **Bit15/bit31 has no
observed effect on retention, positive or negative, register-redirecting
or corrupting.** This reconfirms and extends EXP-0086's own original
finding (CAND_A, the identical bit, was null in every one of 7 kernels
there) — this experiment adds the crucial case EXP-0086 could not reach:
crossing the bit against the SAME instruction's own current-read behavior
AND against the retention-bit's own value, closing the "maybe it's only
active as a pair" gap directly rather than leaving it as an untested
possibility.

**What DOES hold, unchanged from EXP-0086/EXP-0089/EXP-0090:** `opflags`
bit19 (srcA) / bit20 (srcB) alone, exactly as previously documented,
governs whether the value survives to a later, separate reader — natural
polarity confirmed again (bit=0 → retained, 50.0; bit=1 → released,
reads as zero, 20.0), byte-for-byte matching EXP-0086's own polarity
finding.

### 1.4 What this means for the register file

Given bit15/bit31 is inert for BOTH addressing and retention in this
family, `falu2`'s `srcA_reg`/`srcB_reg` operand is, on the evidence
gathered here, **functionally a 6-bit register selector** (the top bit
read but not observed to do anything) for the specific construction
tested (a fresh, unwritten "high" encoding immediately following a
low-register seed). This experiment cannot rule out that bit15/bit31 has
SOME effect not exercised by this test shape (e.g. only visible under
register pressure, a specific op, or a longer dependency chain) — it can
only report that the two most natural hypotheses (7-bit literal index;
his specific complementary-pair retention flag) are both refuted by this
data, and that a third, simpler explanation (the bit is read but currently
inert, at least for `fadd`/`falu2`-family register-register combination)
fits every observation.

---

## 2. H3 — registers 64–95 (UNKNOWN/OPEN, not independently probed)

Per `PRE_REGISTRATION.md` §5's disclosed, time-boxed scoping decision: H3
was to be answered by reasoning from H1's result. **H1's actual result
does not resolve H3** — neither competing model's account of how
registers 64–95 are addressed survives (the current model's account is
refuted; the explainer's account, under which 64–95 would ALSO not be
directly addressable via this same field since it only has 6 bits, is
consistent with what was observed but gives no positive mechanism either).
**No currently-validated mechanism for reaching registers 64–95 through
`falu2`/`falu2i` was identified.** A candidate alternate path
(`falu3`'s plain 8-bit register fields, `db.json`: `srcA`/`srcB`/`srcC` at
bytes 3/4/5) was considered but not tested — that family's `op` enum and
tail-modifier fields are flagged by `db.json`'s own provenance note as
"inferred"/structural-only, and characterizing it well enough to mount a
non-confounded probe was judged, and disclosed in advance, to be its own
multi-case undertaking outside this experiment's time budget. **H3 is
UNKNOWN, not guessed.**

---

## 3. H4 — consumer route / load-to-ALU bridge (decisive negative, 2 runs)

### 3.1 Observed

| group | cases | result |
|---|---|---|
| `ROUTE_LOAD` (route 0–7) | 8 | **ALL 8 read 0.0** (oracle `-8.5`, `V_LOAD` from `mem[1]`) — MISMATCH in every case |
| `ROUTE_ALU` (route 0–7, ALU-sourced control) | 8 | **ALL 8 read 16.0 exactly** (oracle `16.0`) — MATCH in every case |
| `route_load_6_bit21` (route=6, opflags bit21=1) | 1 | reads 0.0 — MISMATCH |
| `route_alu_6_bit21` (control) | 1 | reads 16.0 — MATCH |
| `h4_store_bridge_regstore` (device_load→register-named store, extmode=2·67) | 1 | reads 0.0 (oracle `133.75`) — MISMATCH |

All rows fully deterministic across both independent hardware runs.

### 3.2 Interpretation

**The route hypothesis is REFUTED for the mechanism as tested**: not one
of the 8 candidate route values (`mod_hi` bits 1–3, instruction bits
45–47) makes `device_load`'s result readable by a subsequent `falu2`.
The `ROUTE_ALU` control is the methodologically load-bearing piece here:
identical construction, identical route sweep, ALU-sourced operand instead
of load-sourced — and it is **perfectly correct at every route value**,
proving (a) the harness, splice mechanism, and `mod_hi` field encoding are
all working exactly as intended, and (b) route genuinely has **no effect**
on an ALU-sourced operand — independently reproducing, on OUR OWN bytes,
the explainer's own stated observation about his all-ALU float-fanout
shader ("forcing its route through all values 0–7 did not change the
output"). The asymmetry (`ROUTE_LOAD` uniformly fails, `ROUTE_ALU`
uniformly succeeds, same sweep) is the clean, decisive signature of a real
load-vs-ALU distinction whose *mechanism* is not the route field.

The `bit21` ("destination publication") variant does not help either
(load case still 0.0), and the register-store path
(`h4_store_bridge_regstore`) fails too — extending EXP-0090's own
`extmode=2*data_reg` store formula (previously validated only on small
registers) to register 67 does not work, a second, ALU-independent data
point for the same underlying blocker (see also §6, the pilot-phase
finding that even a register-named STORE consuming a fresh `device_load`
result only worked for the exact register EXP-0090's own anchor used).

**Net: EXP-0090's blocker #1 (general `device_load`→ALU bridging) is
CONFIRMED to persist and is NOT explained by the route field.** The
project should continue to treat this as an open, unsolved hardware
question — this experiment narrows the search space (route is
eliminated) rather than closing it.

`db.json`'s own `scoreboard_model` note (EXP-0025, HW-VALIDATED: "G17P
emits NO per-op scoreboard wait... an async op marks its destination
register pending; a consumer reading that register stalls in HW until the
op retires... >=20 independent device loads outstanding, all consumed
correctly with no wait") argues against a missing-software-wait
explanation specifically — a padding-instruction variant was also tried
(H5's `move_padding`, and informally for the load→ALU path in the pilot
phase, PROGRESS.md Milestone 4) with no effect. **The actual mechanism
blocking `device_load`→ALU consumption remains genuinely unidentified.**

---

## 4. H5 — GPR-sourced move retry (decisive negative for 3 fixes, +1 new fact)

### 4.1 Observed

| case | producer | fix tried | observed | oracle | verdict |
|---|---|---|---:|---:|---|
| `move_baseline_fail_replicate` | falu2i, opflags=1 | (none — EXP-0090 replicate) | `0x00000100` (≈3.587e-43) | 30.0 | MISMATCH (predicted) |
| `move_bit21_set` | falu2i, opflags=3 (bit21=1) | destination-publication bit | `0x00000100` | 30.0 | MISMATCH |
| `move_padding` | falu2i, opflags=1, +4 pad instrs | pipeline timing | `0x00000100` | 30.0 | MISMATCH |
| `move_bit21_and_padding` | falu2i, opflags=3, +4 pad | both combined | `0x00000100` | 30.0 | MISMATCH |
| `move_load_sourced` | device_load (not falu2i) | different producer family | `0x00000100` | -8.5 | MISMATCH |

All 5 rows fully deterministic, byte-identical across both runs, in BOTH
`out_hex` (raw) and the decoded float.

### 4.2 Interpretation

**All three candidate fixes are REFUTED**: `reg_move` still cannot read a
GPR written by `falu2i`, whether or not the producer's `opflags` bit21 is
set, whether or not 4 padding instructions separate producer and
consumer, and whether both are combined. EXP-0090's blocker #2 remains
open, with the "destination publication" and "timing" hypotheses this
experiment could test both eliminated as explanations (H4's own consumer
family — a different one, `falu2`/`falu2i` — is unaffected by these same
variables, so this is specific to `reg_move`, or to the general
load/ALU→different-family consumption pattern shared by both blockers).

**New fact: `move_load_sourced` ALSO fails**, closing EXP-0090's own
explicitly-flagged open question ("whether `reg_move` can read a GPR
written by `device_load`... remains UNKNOWN") with a definite **NO** for
the tested construction. `reg_move`'s failure is not specific to
`falu2i`-written sources — it also cannot read a `device_load`-written
source, i.e. `reg_move`'s scope remains exactly what EXP-0087 established
(uniform-register/preloaded sources only) and does not extend to ANY
GPR written by a different instruction family tested so far.

**New, precisely-recorded fact (not previously reported): the failure
mode is NOT exactly 0.0.** Every one of the 5 `GPR_MOVE_RETRY` cases reads
back the exact 32-bit pattern `0x00000100` (a denormalized float,
≈3.587324×10⁻⁴³), identically, deterministically, across both runs and
all 5 constructions (including the `device_load`-sourced variant, which
has a structurally different producer). This is recorded as an exact
observation, not rounded to "reads zero" by assumption — EXP-0090's own
report described its P4 failure as reading "0.0 for every slot," which
this experiment's more precise, hex-level readback (`out_hex` in the raw
records) shows was evidently an approximation, an artifact of EXP-0090's
own decode not printing enough precision, or a genuine difference between
that experiment's slightly different construction and this one. Either
way: **a constant, non-zero, denormalized bit pattern appearing
identically regardless of producer family is a stronger, more specific
signature than "reads zero"**, and is a concrete lead for whoever
continues this investigation — it suggests `reg_move`'s `src_reg` field
(or some other fixed field in its 4-byte encoding) is consistently
addressing the SAME wrong location (which happens to hold this bit
pattern) rather than reading "nothing"/an uninitialized-but-random value.
This experiment did not have time to chase that lead further.

---

## 5. H6 — family generality of bit 17 (static analysis only, no new HW group)

Per the disclosed scoping decision (`PRE_REGISTRATION.md` §5): compared
`db.json`'s field layout for `unpack_convert` (`src_class` byte+1,
**`cache` byte+2 — full byte, contains the literal bit 17 at its bit1**,
`convert_desc` bytes+3..6, `size`/`reg_sel` byte+7) and `cvt_i2f`
(`mode` byte+2 — again the literal-bit-17-bearing byte, `dst` byte+3,
`src_class` byte+4, **`src` byte+5** — the actual register descriptor,
`cvtop` byte+6, `signflag` byte+7) against `falu2`'s layout, where bit15
lives INSIDE the same byte as the register index it modifies (`srcA_reg`
occupies bits 9–15, i.e. bit15 is literally the top bit of the register
field itself).

**Verdict: bit 17 is structurally NOT the same mechanism repositioned.**
In both `unpack_convert` and `cvt_i2f`, the byte containing bit 17 (byte+2)
is a SEPARATE byte from the family's own register-descriptor field
(`reg_sel` at byte+7 for `unpack_convert`; `src` at byte+5 for `cvt_i2f`)
— there is no register field anywhere in either family whose own top bit
IS bit 17, unlike `falu2`'s bit15/bit31. This rules out "H1's bit15
mechanism, just at a different byte offset" as an explanation for bit 17.
Combined with EXP-0089's own hardware finding that bit 17 (unlike bit19/20
in this experiment) corrupts the FLIPPED instruction's OWN result, not
only a later reader's, bit 17 remains best characterized as a genuinely
**third, distinct mechanism** — consistent with EXP-0089's original
conclusion, now additionally supported by a structural argument for WHY
it should be expected to differ, rather than left as an open "maybe."
**Whether bit 17 itself has its own companion/pair bit within its own
byte (byte+2) is NOT tested here** and is recommended follow-up work, not
asserted either way.

---

## 6. Table verification (his 10-byte logic table; his 8-byte FMA table)

### 6.1 10-byte logic table — DECISIVE DECODING DEFECT FOUND (static only)

Decoding the explainer's own worked example bytes (Example 1, integer
select DAG) against `tools/agx-isa/db.json`:

```text
"Correct — source 0 retained":   4b 85 16 07 02 08 00 00 00 00
"Incorrect — both released":     4b 05 1e 07 02 08 00 80 00 00
```

`isadb.disassemble()` on the "retained" bytes returns:
`{"mnemonic": "<unknown>", "error": "unknown instruction length at offset
0 (byte0=0x4b)"}` — **this encoding does not decode under ANY family in
our current instruction database.** The "released" bytes DO decode, but
as `b_alu10_loe` (`db.json`'s own provenance note: "byte-diff EXP-M4-13
R7... NOT HW-dispatch validated; op-select value meanings inferred") —
**not** `ilogic`, the family his prose implies (LUT2 bitwise logic):
`ilogic`'s own match condition requires the WHOLE of byte0 == `0x0B`
(decimal 11), not merely its low nibble, and `0x4B`'s low nibble is `0xB`
but its full byte value is `0x4B` (75), which does not match.

This is reported as a **static, decoding-dispatch-level finding**,
independent of any hardware result: our own `db.json`'s `length_rule`/
match-table dispatch **cannot even tokenize** one of his two literal
example encodings, and dispatches the other to a weakly-validated,
differently-named family. This does not, by itself, confirm or refute his
retention-bit claims for the logic form (we have no hardware test of this
specific family in this experiment — see §6.3), but it is independent
confirmation that **`db.json`'s coverage of this instruction shape has a
real, exact gap**, worth fixing regardless of the retention question.

### 6.2 8-byte FMA table — no clean db.json correspondent found

The explainer describes an "eight-byte FMA form" where source 0/1 share
`falu2`'s own bit15/19/bit31/20 fields and a third source uses bit47/39
+ a route at bits 61–63. No family in `db.json` matches this description
structurally:

- Our own 8-byte 3-source form, `falu3`, uses a COMPLETELY DIFFERENT
  layout (`dst_lo` nibble + `dst` full byte at byte+1 + `op` byte + plain
  8-bit `srcA`/`srcB`/`srcC` register bytes at byte+3/4/5) — none of
  bit15/19/31/20/39/47 correspond to a register or retention field in
  this layout at all (bit15 there is inside the `dst` byte, not a source).
- Our 12-byte `falu3_srcmod12` (3-source FMA) DOES share `falu2`'s exact
  base-48-bit layout (`srcA_reg` bits 9–15, `opflags` 19–23, `srcB_reg`
  bits 25–31, `srcB_imm` bit39, `mod_hi` bits 44–47) his description
  implies — but it is 12 bytes, not 8, with the 3rd source living in a
  separate 48-bit `ext_srcmod` tail (bits 48–95), not at bits 61–63 of an
  8-byte instruction.

**This is reported as an open discrepancy, not resolved by guessing which
family he means.** No hardware test of either `falu3` or
`falu3_srcmod12`'s 3rd-source retention fields was attempted in this
experiment (see §2/H3 for the same time-budget reasoning covering
`falu3`).

### 6.3 Own-MSL authored reproduction of the two dataflow shapes

Per the dispatch's explicit instruction not to port the explainer's GLSL
verbatim, no attempt was made to compile a literal translation of his two
reproducers. His two dataflow SHAPES (a fanned-out operand feeding a
second use; a memory load feeding a float ALU op) are directly embodied,
authored independently in our own MSL/hand-assembled-instruction terms, by
this experiment's own `SRCA_PAIR`/`SRCB_PAIR` groups (a value read twice,
by two separate instructions — the same structural shape as his integer
select DAG's `gid` fanout and his float fanout DAG's `x` fanout) and by
`ROUTE_LOAD` (a `device_load` result feeding `falu2`, exactly his
prescribed "discriminating shape" for the route question). No separate,
additional own-MSL kernel was compiled purely to mirror his source
line-for-line, since the hand-built instruction approach already gives
full, independently-verified field control without depending on what a
compiler happens to naturally emit — and, given the time already spent
isolating the pilot-phase carrier/plumbing issues (§ PROGRESS.md), a
third, purely-confirmatory compiled anchor was judged lower priority than
capturing the frozen matrix under the formal two-run gate.

---

## 7. Proposed `db.json` field-definition corrections (text only — NOT applied; `tools/` is read-only for this experiment)

1. **`falu2`'s `srcA_reg` (bits 9–15) and `srcB_reg` (bits 25–31) fields
   should be RE-TYPED from a 7-bit literal `reg` index to something
   reflecting that the top bit (bit15/bit31) has been HW-TESTED and shown
   to have NO effect on which register is addressed** (this experiment,
   §1) — NOT "6-bit register + retention flag" (that specific claim is
   ALSO refuted, §1.3) but simply: only the LOW 6 bits are load-bearing
   for addressing in the tested construction; the top bit's role (if any)
   is unresolved. Suggested annotation: `reg (6 bits load-bearing; top bit
   HW-tested INERT for register-selection AND retention in the
   register-register two-source form, EXP-0099; role, if any, UNKNOWN)`.
2. **`falu2i`'s `srcA_reg` (bits 25–31) should get the same annotation**
   by structural analogy (not independently tested by this experiment —
   only the `falu2` register-register form's bit15/31 were tested; the
   analogous position in `falu2i` was not).
3. **A new "known-narrow" annotation for `device_store`'s `extmode = 2 *
   data_reg` formula** (currently `db.json`: untyped `mod`, provenance
   citing EXP-0090 finding_5): this experiment found it fails for
   `data_reg=67` (extmode=134) — the formula should be flagged
   `PARTIAL/NARROW — HW-VALIDATED only for the small register range
   EXP-0090 actually tested; independently shown NOT to extend to at
   least one high register (r67) by EXP-0099`.
4. **The `device_load → device_store` "direct forward" `addr_mode=0x56`
   pattern** (currently described in `docs/isa/register-move-and-
   liveness.md` as "CONFIRMED") should be downgraded to **register-value-
   SPECIFIC, not general** — this experiment's pilot phase (PROGRESS.md
   Milestone 4) found it works ONLY for the exact destination register
   (`dst=5`) EXP-0090's own anchor used, and fails for `dst` ∈ {0, 2, 7,
   67} with the identical construction otherwise. This is not yet in a
   gated raw/ record (informal pilot finding) — flagged here for a
   follow-up experiment to formalize.
5. **`b_alu10_loe`'s / the `b_alu10` family's own provenance note** should
   record that at least one of the explainer's own logic-instruction byte
   patterns (his "retain source 0" XOR example, byte0=`0x4b`) is NOT
   decodable under ANY current `db.json` family — a concrete example to
   attach to future work characterizing this family's true length rule.
6. **`isadb.py`'s length-rule dispatch for byte0 patterns matching
   `0x?b` (low nibble `0xB`) with a non-`0x0B` high nibble** should be
   reviewed against the "unknown instruction length" failure in §6.1 —
   this is a decoding coverage gap independent of any retention-bit
   question.

---

## 8. Gate results

- `verify.py --selftest`: **PASS**, 13 checks (uses a REAL recorded
  hardware fixture, `harness/recorded_fixture_case0.json`, captured during
  this experiment's own pilot phase — CODEX gate (e); round-trips all 35
  cases through `isadb.disassemble`+`assemble`).
- `verify.py --seqtest`: **PASS** in all three tree states (`PRE_GPU`,
  `RUN01_PRESENT`, `RUN02_PRESENT`).
- `make_manifest.py --check` / `--write`: **PASS**.
- `verify.py --preflight`: **PASS**.
- `verify.py --between-runs`: **PASS** — gated ONLY on
  `authored_{code,kernel,doc}_sha256` and the pinned revision recorded in
  `PRE_REGISTRATION.md`/`CAPTURE_CONTRACT.json`; never live git `HEAD`
  (per SUBAGENT_BRIEF.md's standing instruction).
- `verify.py --captured`: **PASS** — `01_results.jsonl` byte-identical
  across both runs (sha256 above); `01_timing.jsonl` correctly NOT
  required to match (and in fact differs, as expected for a
  nondeterministic-duration field).
- No `STOP.json` in either run.
- **Positive control** (`positive_control_deliberate_mismatch`): reads
  30.0 against a deliberately unreachable oracle of 999.0 — MISMATCH as
  designed, proving match-detection is not a rubber stamp, in both runs.
- **Detection-capability proof for the H4/H5 negative results**: the
  `ROUTE_ALU`/`route_alu_6_bit21` controls (8+1 cases, all MATCH) prove
  the harness, splice mechanism, and field encodings used in `ROUTE_LOAD`
  are sound — the `ROUTE_LOAD` mismatches are a real hardware finding,
  not a broken test.

---

## 9. Limitations / honest gaps

- **Only the `falu2` register-register (6-byte compact) form's
  bit15/bit31 were HW-tested.** `falu2i`'s analogous position, the 10-byte
  logic form's bits, and the (undetermined) 8-byte FMA form's bits were
  NOT independently tested here — see §6 for why, and §7 items 1–2 for
  what is and is not being extrapolated.
- **H3 is genuinely unresolved** — not a negative result, an open gap
  (§2).
- **The load-to-ALU and GPR-move blockers (H4/H5) remain OPEN** — this
  experiment narrows the search space (route, destination-publication,
  timing padding, and — newly — the specific `move_load_sourced`
  producer-family question are all eliminated as explanations) but does
  not find the actual mechanism.
- **The `device_load`→`device_store` "direct forward" register-specificity
  finding (§ PROGRESS.md Milestone 4, §7 item 4) is INFORMAL/pilot-phase
  only** — observed on real hardware but not captured under this
  experiment's own formal two-run gate (it surfaced before the matrix was
  frozen, and re-testing it was judged lower priority than the frozen H1–
  H5 matrix given the time already spent). A follow-up experiment should
  formalize it.
- **The original, higher-register-pressure carrier kernel's silent
  `device_load` splice failure (PROGRESS.md Milestone 3) is not root-
  caused.** This is disclosed as an open question about splice
  reliability under kernel complexity, not resolved.
- **`move_load_sourced`'s exact `0x00000100` bit pattern is not explained**
  (§4.2) — recorded precisely as a lead for follow-up work, not chased
  further here.

---

## 10. Clean-room provenance

```text
Clean-room provenance: OWN-SHADER + HW-PROBE + PUBLIC
Inputs inspected: kernels/carrier.metal (our own MSL), tools/agx-isa's
  isadb.assemble()/disassemble()/imm_encode()/imm_decode() (read-only),
  tools/agxtest (read-only, splice-and-run), tools/shdump (read-only,
  compile+extract). apple9_isa_explainer.md is cited as the HYPOTHESIS
  ORIGIN (PUBLIC category, a third-party document) -- no GLSL source or
  byte sequence from that document was copied into any file in this
  experiment; every instruction byte executed here is our own field
  values passed through our own assembler (isa_helpers.py /
  casematrix.py). Decoding his example bytes against db.json (sections
  6.1/6.2 and PROGRESS.md Milestone 1) is DATA analysis of numbers printed
  in a public document, not code introspection of any kind.
Apple binary introspection: NONE.
Reproduction: python3 -B verify.py --selftest/--seqtest (no GPU);
  python3 -B run.py --execute --run-id <id> (real GPU, append-only);
  python3 -B analysis.py --write; python3 -B verify.py --captured.
Evidence: raw/m4-20260828-run01/, raw/m4-20260828-run02/ (byte-identical
  01_results.jsonl, sha256 above), analysis.json, manifest.json.
```
