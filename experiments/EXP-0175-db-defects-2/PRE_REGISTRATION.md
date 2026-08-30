# EXP-0175 — pre-registration

**Frozen before any edit to `tools/agx-isa/db.json` or any analysis script was written.**

Type: **desk experiment** (no device work). Every input is already-committed evidence in this
repository. **No dispatch to the neo, the M4 GPU, or M5.** One device experiment was live on
the neo at dispatch time and must not be disturbed.

## 0. Frozen inputs

| item | value at freeze |
|---|---|
| repo `HEAD` | `ff99bb52` (worktree dirty with sibling experiments; irrelevant — this experiment gates on blob hashes) |
| `tools/agx-isa/db.json` sha256 | `322847609de79055b651b79fbd630948bb97120bcefd037a3c7ae5a301ba64a5` (172 instructions, 1062 fields) |
| `tools/agx-isa/validation.json` | 1062 fields, 541 `hardware-run` + 86 `isolated-byte-diff` = **627 emitter-grade**, 50 emittable mnemonics |
| EXP-0171 raw | `raw/g17p_20260830_run01/sweep.jsonl` (35,949 cases), `run02` (35,949), `raw/isolation/iso01.json`; matrix sha `bce0b7de…` identical in both |
| EXP-0171 pinned db | `322847609de79055…` — **identical to the live `db.json`**, so its verdicts and this repair are on the same descriptor set |
| baseline gate | corpus **833/1080 clean, 388,604 strict leftover bytes**, 25,419 tokens; `roundtrip_test.py` 302 OK / 0 FAIL / ALL PASS; `validate_labels.py` exit 0 |

`match_overlap_report.py` at freeze: **59** fields overlap their own descriptor `match`;
**25** have zero free bits; **16** of those carry an emitter-grade label.

## 1. Questions

**Q1.** Do DEF-0171-1 … DEF-0171-5 survive an *independent* re-derivation from EXP-0171's
committed `raw/`, performed without reference to its `RESULTS.md` conclusions?

**Q2.** Does `ibfe` close? EXP-0171 flagged that it closes only if `ibfe.sign_ext` and
`ibfe.b2_bit0` are promoted from **proven inertness** to emitter grade.

**Q3.** Are the 25 zero-free-bit "fields" really part of `match`, and what is the exact
before/after field census when they are folded in?

**Q4.** Which fields *name* an operand but cannot select one?

## 2. Hypotheses, expected observations, refuters

### H1 — DEF-0171-1: `ilogic` byte0 == `(dst << 4) | 0x0b`
**Expected:** in EXP-0171's `SYNTH:k_and@ilogic+32` byte-0 sweep, for every value `v` with
`v & 0x0f == 0x0b`, the AND result `93 & 107 = 73 (0x49)` appears in GPR `v >> 4` and in no
other GPR, in **both** gated runs, for all 15 observable destinations (r15 is unobservable by
construction — it is the harness's own store-index register).

* **R1a (refuter).** The result stays in the anchor's r2 regardless of `v >> 4`. Then byte0's
  high nibble is not `dst` and the defect is withdrawn.
* **R1b (refuter).** The mapping holds in one run and not the other. Then it is not
  reproducible and is withdrawn.
* **R1c (partial refuter).** The mapping holds but so do other low nibbles, i.e. `0x0b` is not
  the discriminator. `0x23` is already known to reproduce the anchor state; if `v>>4` also
  drives the destination for a *second* low nibble, the `match` proposed below is still
  over-fitted in the other direction and I must say so.

**Applied form if confirmed:** `ilogic.match` becomes `[[0,4,11],[17,7,15]]` and a `dst`
field `{start:4,width:4,type:reg}` is added. This is the *minimal* change that is directly
hardware-proven.

### H2 — the full merge (`ilogic` ≡ `b_alu10_lof` ≡ `b_alu10_loe`)
This is a **structural inference**, not the hardware-proven part of DEF-0171-1: EXP-0171 swept
only `opsel_hi == 1` (byte+2 ∈ {0x1e,0x1f}) and reported the results under both key sets.
It is therefore evaluated as a **separate candidate tree** and applied only if the corpus gate
is neutral-or-better AND the evidence supports the identification.

* **Refuter:** any corpus regression (clean files down, or strict leftover bytes up), or a
  firing delta that cannot be accounted for byte-for-byte. Then it is reported and **not**
  applied — per dispatch, that call is the orchestrator's.

### H3 — DEF-0171-2: no length rule for byte0 `0x31`; `bf_alu` / `bf_fma_dst` mis-describe G17P
**Expected:** the three anchors recorded in EXP-0171's raw (`31 00 1c …`, `31 00 1d …`,
`31 00 1e …`) return `length: None` / `<unknown>` from the live `isadb.decode_one`, and
`bf_alu`'s `match` (byte0 == 0x11, byte+1 == 0x02) and `bf_fma_dst.fmt`'s enum `{2,4}` do not
contain what G17P emits.
* **Refuter:** the anchors decode. Then the defect is withdrawn.
* **Scope limit pre-registered:** the *length rule* lives in `isadb.py`, not `db.json`, and
  `isadb.py` has a named owner. I will **measure** a candidate but not land an `isadb.py`
  change unless the corpus gate strictly improves and the change is confined to the byte0
  `0x31` family.

### H4 — DEF-0171-3: `ibfe.sign_ext` is not the sign control
**Expected:** the byte+6 bit-1 sub-value sweep is inert (0 moved of 2) on **both** the
unsigned (`k_bfe`) and signed (`k_bfe_s`) anchors, while byte+6 as a whole is demonstrably
live on the same carrier in the same run.
* **Refuter:** it moves on either anchor, or byte+6 is not live (no detection power).

### H5 — DEF-0171-4: `outmod` bit 7 is a source-read control, not an output/store flag
**Expected:** on the NAT store-consumed carriers, with byte+7 bit 7 clear, `poison_out == 0`
and both sentinels intact, `k_and/k_or/k_xor/k_andn` write **0** and `k_nand` writes
**0xFFFFFFFF**.
* **Refuter:** `k_nand` also writes 0 (then it *is* an output flag), or the output stays
  poisoned (then the store did not run and the mechanism claim is unsupported).

### H6 — DEF-0171-5: `fspecial_est.subop == 0x0f` is emitted and encodable
**Expected:** the G17P `rsqrt` anchor's byte+3 is `0x0f`; `db.json`'s enum lacks `15`; and the
descriptor's own `match` leaves exactly the two bits that make `{9,11,13,15}` the legal set,
so `15` is not merely observed but *encodable*.
* **Refuter:** the anchor byte is not `0x0f`, or the match forbids `15`.

### H7 — `ibfe` closure from proven inertness
**Standing rule (from the dispatch):** proven-inert-with-unknown-role earns
`single-template-inference`, **not** emitter grade, because emitter grade asserts an
implementer may *choose* the value.
**Pre-registered decision rule:** I recommend emitter grade for an inert field only if the
inertness is established across **≥ 2 carrier styles AND ≥ 2 independent compiler-emitted
anchors that differ in the dimension the field is named for**, *and* the field's role is
either known or bounded by a control that was itself swept. If the role is unknown and the
sweep cannot exclude that some *other* state makes it live, the recommendation is
`single-template-inference` and `ibfe` does not close.

### H8 — the fold arithmetic
**Expected:** 25 fields fold; `total_fields` 1062 → **1037**; emitter-grade 627 → **611**;
`total_instructions` unchanged at 172; corpus and round-trip unchanged **exactly** (a
zero-free-bit field contributes no encodable bit, so removing it cannot change any byte).
* **Refuter:** any corpus or round-trip delta. Then the "zero free bits" premise is wrong for
  at least one row and I stop and report which.

### H9 — the operand-name defect class
Fields whose *name* implies an operand but whose bits cannot select one. Cross-checked against
`docs/isa/README.md`: the GPR file is **96 entries**; `fspecial`'s `reg = (byte+3) >> 1` maps
0..191 onto r0..r95; **r15 is not writable through a 4-bit `dst` nibble** (EXP-0168); ALU
aliasing is mod-64 while the fragment stage's `tex_sample.coord` has period 16 (EXP-0172).
A 4-bit field cannot address 96 registers, so the question is what it really selects.
No hypothesis is asserted here — this arm is an **enumeration**, and its output is a ranked
list, not a set of db edits.

## 3. What I will and will not change

**Will edit:** `tools/agx-isa/db.json` only (I am the sole editor this session).
**Will NOT edit:** `tools/agx-isa/validation.json`, `docs/`, `PROVENANCE.md`,
`docs/P0-P1-CLOSURE.md`, `CLAUDE.md`, `CODEX.md`, any other experiment's directory.
**Will NOT `git commit`.**
Orphaned `validation.json` rows are **listed** in `analysis/orphaned_validation_rows.json`,
not deleted.

## 4. Gates (all must hold, before → after)

1. `python3 analysis/ab_gate.py` — corpus **clean ≥ 833/1080** and **strict leftover ≤ 388,604**;
   any firing delta must be explained byte-for-byte.
2. `python3 tools/agx-isa/roundtrip_test.py` — ALL PASS. **Explicitly not treated as an emitter
   gate** (EXP-0170: it passes with an assembler that cannot clear a bit; EXP-0173: it passes
   with `falu3.srcA`↔`srcB` swapped). It is a regression tripwire only.
3. `python3 tools/agx-isa/validate_labels.py` — exit 0. A `db_sha256` WARN is expected and is
   the orchestrator's to clear; a FAIL stops me.
4. `python3 tools/agx-isa/emit_worklist.py` and `match_overlap_report.py` still run.

**Stop conditions.** Any corpus regression from a change ⇒ revert that change, report, do not
land it. Any `validate_labels.py` FAIL ⇒ revert and report. Any defect that fails its
re-derivation ⇒ **not applied**, and recorded as a first-class negative result.

## 5. Confounders acknowledged in advance

* **Reading EXP-0171's conclusions first is itself a confounder.** Mitigation: every
  re-derivation script computes its verdict from `raw/` alone and prints the numbers it
  found; the comparison against `RESULTS.md` happens only afterwards, and any mismatch is
  reported in favour of the raw.
* **The b_alu10 rows are aliases.** EXP-0171 swept `ilogic` at `opsel_hi == 1` and reported
  the same cases under `b_alu10_lof.*` / `b_alu10_loe.*` keys. Nothing in its raw exercises
  `opsel_hi ∈ {2,3,4,6,8,12}`. This is why H2 is separated from H1.
* **`invalid_run` / victim contamination.** EXP-0171 recorded 128 `invalid_run` cases per run
  and (run02) 1 hang. Every re-derivation excludes `invalid_run` and reports how many cases it
  dropped.
* **Cross-run agreement is the reproduction, not a second method.** run01 and run02 share one
  frozen matrix; they differ only in dispatch order. I report them separately and never treat
  their agreement as an independent probe.

## 6. Clean-room provenance

```text
Clean-room provenance: OWN-SHADER + HW-PROBE (re-analysis of committed evidence) + PUBLIC
Inputs inspected: experiments/EXP-0171-*/raw/** (our own compiled shaders' bytes, spliced by
                  us, run on our own harness), tools/agx-isa/db.json, validation.json,
                  experiments/EXP-M4-13-full-corpus/hex/** (our own + committed permissively
                  licensed corpus).
Apple binary introspection: NONE. No Apple binary was opened, disassembled, or symbol-dumped.
                  No device was dispatched to.
Reproduction: analysis/*.py (each self-contained; see README.md)
```
