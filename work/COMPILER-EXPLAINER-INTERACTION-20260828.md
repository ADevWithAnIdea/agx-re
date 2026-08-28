# How the compiler engineer's `apple9_isa_explainer.md` interacts with our findings

Date: 2026-08-28. Author: RE orchestrator. Status: **analysis + one confirmed decoding bug in our
own database.** No hardware run yet — every claim below is either a byte-level derivation from the
explainer's own examples decoded with our tooling, or a citation of already-promoted evidence.

## 1. Bottom line

His model is **compatible with all our hardware evidence, more precise than ours, and it corrects
our mechanism description.** It also explains two of our open blockers and exposes a real bug in
`tools/agx-isa/db.json`.

| Our position before | His model | Verdict |
|---|---|---|
| `0x54/0x56` etc. is a "source cache / last-use hint, NOT an op change" | Per-source **retention** state: does each *input* survive this instruction | **He is right.** We already retracted "inert" (EXP-0086/0089); he supplies the correct structure |
| Mechanism = "persistent producer-side writeback suppression" (EXP-0089) | Mechanism = **premature release of an input operand**; the instruction's own result is fine, the *later consumer of that input* breaks | **His is the better fit to our own data** — see §2 |
| `srcA_reg` / `srcB_reg` are 7-bit register fields | Their top bits (15, 31) are **retention flags** | **Confirmed bug in our DB** — see §3 |
| `opflags` is an opaque `mod` | bits 19/20 = the complementary release flags, bit 21 = destination publication | Matches; explains EXP-0090's empirical `opflags=3` rule |
| `mod_hi` is an opaque `mod` | bits 45–47 = **consumer route** = "the kind of producer the operands arrive from" | **Candidate explanation for our load→ALU blocker** — see §4 |

## 2. His model explains our own data better than our model did

EXP-0086's decisive case was `v = a[0] = 7.5`; `x1 = v + 10`; `x2 = v + 20`, and flipping a bit on
the **earlier** instruction gave `x1 = 17.5` (correct) and `x2 = 20` (wrong).

- Our "writeback suppression" reading never explained why `x1` was **correct**.
- Under his model it is immediate: the `x1` instruction **released its input `v`**, so `x2`'s read
  of `v` returned zero and computed `0 + 20 = 20`. The observed value is exactly 20.

It also explains our **null** result. EXP-0086's `CAND_A` was "a register-select-field top bit that
tracks first/second-read order" — that is **his bit 15** — and we found it null in every
configuration. He states retention is the *correlated transition* `(bit15, bit19) = (1,0)`, "not
simply setting bit 15". **We flipped one half of a complementary pair**, which is why nothing
happened. Our `CAND_B` (opflags bit 0 = his bit 19) *did* corrupt, because flipping the complement
alone does change the encoded state. One model, both our results.

## 3. CONFIRMED BUG: our register fields swallow his retention bits

Decoding *his own* example bytes with **our** `db.json` field layout (`falu2`, 6-byte compact float):

| His bytes | Meaning (his) | Our decode |
|---|---|---|
| `39 89 25 85 00 00` | `x * 2.0`, retain both sources | `srcA_reg=68`, `srcB_reg=66`, `opflags=4` |
| `39 09 3d 05 00 00` | same instruction, release both | `srcA_reg=4`, `srcB_reg=2`, `opflags=7` |

Same instruction and operands; only lifetime state differs. **Our disassembler reports different
register numbers** — and both deltas are exactly **64**, i.e. bit 15 and bit 31, the top bits of our
7-bit `srcA_reg` (9..15) and `srcB_reg` (25..31).

**Conclusion: for this family the register operand is 6 bits plus a retention flag, not a 7-bit
register index.** Consequences to work through:

1. Any claim of ours involving falu2/falu2i source registers **≥ 64** is suspect — some "high
   registers" are low registers with retention set.
2. It is a likely root cause of EXP-0087's move rule turning out to be uniform-register-sourced
   only, and of EXP-0090's failure to construct a working GPR-sourced move: we were emitting the
   wrong register/retention split.
3. `opflags` values reconcile: correct = `4` (`b19=0,b20=0,b21=1`), incorrect = `7`
   (`b19=1,b20=1,b21=1`). So **bit19 = release src0, bit20 = release src1, bit21 = destination
   publication** — and EXP-0090's empirical "needs `opflags=3`, `opflags=1` silently zeroes srcB"
   is the shadow of this contract: `opflags=1` leaves src1 in an inconsistent
   (neither-retained-nor-released) state, which reads as zero.

The DB fix must be made **and round-trip re-validated across the corpus**, because it changes how
every falu2/falu2i operand decodes.

## 4. He may have unblocked our two open synthesis blockers

`docs/isa/register-move-and-liveness.md` §2.6 records two named blockers from EXP-0090:

1. **General load-to-ALU bridging** — `device_load`'s result could not be fed into `falu2`/`falu2i`
   by independent construction (5+ falsified attempts).
2. **GPR-sourced moves** — `reg_move` could not read a GPR written by `falu2`/`falu2i`.

His **consumer-route** field (bits 45–47 in the compact float form; 61–63 for FMA src2) is defined
as identifying "the kind of producer from which the operands arrive." If an operand arriving from a
**memory load** requires a different route value than one arriving from an **ALU**, that is exactly
the variable we never set. He is explicit that his own float shader cannot test this ("entirely
ALU-produced… forcing route 0–7 did not change the output") and prescribes the discriminating
shape: **a memory load feeding a float ALU instruction** — which is precisely our blocker #1.

This is the highest-value follow-up available and is dispatched as its own experiment.

## 5. What still needs hardware verification (not assumed)

- His exact bit tables for the **10-byte logic** form and the **8-byte FMA** form: we have not
  decoded those against our own layout yet; only the 6-byte float form is cross-checked above.
- Whether bit 15 / bit 31 are retention flags **in every family** or only these. Our EXP-0089 found
  the *literal* bit 17 corrupting in `unpack_convert` and `cvt_i2f` — **bit 17 is not in his tables
  at all**, so either families place these fields differently, or bit 17 is a third mechanism.
  Do not assume one generalises to the other.
- The register-width consequence: if `srcA_reg` is 6 bits, how are registers 64–95 addressed in
  this family? Our machine model has 96 GPRs (re-confirmed by EXP-0092's 96-GPR boundary), so there
  must be a high-register path we have mis-attributed.
- His polarity claims under our own splice harness, with the later-read discipline EXP-0086
  established.

## 6. Credit where due

Both of his reports have now been confirmed against hardware or against our own byte-level data,
and both found real errors in our documentation:

1. "There's a lifetime mechanism and your docs deny it" → EXP-0086/0089 refuted our "inert hint"
   claim; the literal bit 17 is load-bearing.
2. "I can't get a basic register-to-register move to work" → EXP-0087 found most `byte+2` values
   are silent zeroing no-ops, and EXP-0090 found our published rule was uniform-source-only.

And now a third, from this document: our register fields absorb his retention bits. The pattern is
consistent — **decode coverage looked complete while synthesis kept failing**, because a wrong
operand-field value on this hardware usually produces a **silent zero, not a fault**.
