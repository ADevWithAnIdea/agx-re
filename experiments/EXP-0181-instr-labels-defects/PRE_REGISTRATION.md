# EXP-0181 — PRE-REGISTRATION

**Type: DESK EXPERIMENT. No device, no SSH, no GPU, no `macvdmtool`.** Three device
experiments were live on the neo throughout and were not touched. Every input is evidence
already committed to this repository.

```text
Clean-room provenance: OWN-SHADER + HW-PROBE (re-analysis of committed evidence) + PUBLIC
Inputs: tools/agx-isa/{db.json,validation.json,isadb.py}; experiments/EXP-*/raw/**/*.jsonl
        (the recorded behaviour of OUR OWN compiled shaders, spliced by our own tools);
        experiments/EXP-M4-13-full-corpus/hex/** (our own compiled shader bytes);
        the cited experiments' RESULTS.md.
Apple binary introspection: NONE.
```

**Frozen inputs at pre-registration**

| | |
|---|---|
| repo revision | `158042dd` (dirty — sibling experiments in flight; per SUBAGENT_BRIEF the gate is the authored blob hashes, not `HEAD`) |
| `tools/agx-isa/db.json` | sha256 `a77f8cfa163fcf720c0c1093e4ddc5815ceb43c218bb64a87c86d3dcf975dc22` |
| corpus baseline | 833/1080 clean, 388,604 strict leftover, 25,419 tokens, round trip 302 OK / 0 FAIL / ALL PASS |
| headline at freeze | 52 of 166 emitter-relevant emittable, 617 emitter-grade fields |
| match-overlap at freeze | 34 rows, 0 zero-free-bit, 0 vacuous emitter-grade |

> **Amendment A1, recorded when it was noticed, not after the fact.** The orchestrator
> committed `955eb6c7 exp(0179)` mid-experiment, which edited `validation.json` and made
> `call` emittable. The live headline is therefore **53 of 166 and 621 emitter-grade
> fields**, not 52/617. Every number in `RESULTS.md` is stated against the live
> `validation.json`, and §5 shows the isolation measurement proving EXP-0181's own
> `db.json` edit moved neither.

---

## Task 1 — what the 30 weak `_instruction` labels SHOULD be

**Question.** `validate_labels.py`'s emittability rule reads only FIELD labels and never
`_instruction` (DEF-0173-1). Thirty of the emittable instructions carry an `_instruction`
label weaker than emitter grade. The orchestrator deliberately did not gate on them because
they are demonstrably STALE — `mov_imm` is one of only two instructions proven end-to-end
(EXP-0173 §2) and still reads `corpus-correlation`. What should each be, from evidence?

**Hypothesis H1.** The 30 are not a homogeneous block. A majority were dispatched on
hardware with their documented semantics confirmed against a host-computed oracle, and a
minority are descriptors whose semantics remain unconfirmed or have been REFUTED — so a
refreshed gate would cost far fewer than 30.

**Falsifier F1.** If the raw record shows that most of the 30 were never dispatched — only
tokenized and corpus-fitted — then the current labels are right, the gap is real, and the
recommendation must be to leave them alone.

**Confounders named in advance.**
- *Harness attribution is not descriptor attribution.* A raw record tagged `"instr": "X"` is
  the sweeping harness's own label. It must be checked against `isadb.decode_one`, because
  many of these descriptors are dst-generalised siblings of a different HW-validated form.
- *`ok` does not always mean "matched a host oracle".* Several harnesses score movement
  against a BASELINE HASH. That proves the bytes are live, not that the semantics hold.
- *Field strength is not instruction strength.* This is the specific error the task exists
  to avoid.

### The decision rule — FROZEN BEFORE ANY PER-INSTRUCTION RULING

| rule | recommend | requires |
|---|---|---|
| **R1** | `hardware-run` | (a) the descriptor's encoding was DISPATCHED on hardware, on a stated target; **and** (b) its own documented OPERATION was scored against a HOST-COMPUTED oracle (not a baseline hash) and the unmutated instruction reproduced it, in ≥2 gated runs; **and** (c) the dispatched bytes are claimed by THIS descriptor, not a sibling; **and** (d) at least one op-selecting or operand field was MOVED and the behaviour changed as predicted. |
| **R2** | `isolated-byte-diff` | dispatched, and it ran with the predicted effect at one or more points — but (b), (c) or (d) fails: no semantic oracle, or one carrier only, or the descriptor's distinguishing claim was never separated by value. |
| **R3** | keep `corpus-correlation` | nothing that executed establishes the descriptor's identity or semantics — including the case where an experiment **refuted** the documented role. |
| **R4** | keep `tokenization-only` | framing-only, semantics explicitly uncharacterised, or recorded elsewhere as an unresolved continuation-word candidate. |
| **R5** | *(overrides all)* | **A descriptor earns NOTHING at instruction level from its fields being `hardware-run`.** Live fields prove the BYTES were exercised. Promotion requires evidence about the instruction's identity and semantics. |

**Pre-registered expectation:** ≥ 20 of the 30 meet R1 or R2; ≥ 3 stay weak. Recorded
before the rulings so the outcome can embarrass the prediction.

---

## Task 2 — the four descriptor defects EXP-0168 handed over

**Question.** `iter_at.grp`, `pixel_order.scope`, `reg_move_cb.form` and
`shift_amt_move.kind` each declare a field over bits their own descriptor's `match` pins.
EXP-0175 folded the 25 zero-free-bit cases and deliberately left the 34 partially pinned
ones. Can each of these four be narrowed to its genuinely free bits?

**Hypothesis H2.** Each is a real defect and each is narrowable, with the pinned remainder
preserved in `match_notes`.

**Falsifier F2 (and it is expected to fire at least once).** A defect that does not survive
independent re-derivation, or a field whose free bits are not contiguous, must be REPORTED
and NOT applied. EXP-0165 re-derived nine defects and found one half wrong; EXP-0175
refused a propagation that would have created a new defect. Following either of them
blindly is the failure mode.

**Method.** Recompute the free/pinned split from `db.json` alone; go back to every
committed raw record naming the field and score the DISPATCHED values against the
descriptor's own legal set; check what the own-MSL corpus actually emits. Only then compare
with EXP-0168's table.

**Gates (a regression is a stop).**
1. corpus **833/1080 clean, 388,604 leftover, 25,419 tokens** — unchanged;
2. `roundtrip_test.py` ALL PASS — necessary, **not** an emitter gate (EXP-0170, EXP-0173);
3. `match_overlap_report.py` — overlap count must FALL and zero-free-bit must stay 0;
4. `validate_labels.py` exit 0 apart from rows this experiment orphans, which are listed
   rather than fixed in place;
5. every A/B measurement runs `roundtrip_test.py` in a **subprocess** (DEF-0175-2).

**Not edited:** `tools/agx-isa/validation.json`, `docs/`, `PROVENANCE.md`,
`docs/P0-P1-CLOSURE.md`, any other experiment's directory. Nothing committed.
