# EXP-0186 — RESULTS

**Status: COMPLETE.** Pure analysis, no device, no SSH, no GPU. **Promotes nothing.** Produces
drafted text for the orchestrator to apply, and reports two defects in the paper trail itself.

---

## 1. The counts

| | |
|---|---|
| candidate facts examined | **22** |
| already handled correctly, no action | **2** (the `fspecial`/`imad`/`op04_len8` emitter-safety block landed by `a7b0ed97`; and `EXP-0168`'s self-retracted r15 claim, which is correctly **absent** from `docs/` and must stay absent) |
| **facts surveyed as gaps** | **20** |
| **fully present in `docs/` today** | **0** |
| **wholly absent from `docs/`** | **15** |
| **present in a form a later experiment REFUTED or that is stage-blind** | **3** (`F05` `ext8` semantics, `F06` `sr_sel` "zero faults", `F16` the `sr_sel` enum's `0xa8` entry in `encoding-tables.md`) |
| **present only for the older target, or only in prose and not in the machine-readable table** | **2** (`F07` `tile_read`, `F13` the `call` bullet) |
| defects found **in the paper trail itself** | **4** (`D01`–`D04`; one is high severity) |

Fifteen of the twenty are silent-failure or fault-wall facts — the two classes `docs/isa/README.md`
already tells its reader are Apple9's dominant failure mode.

Drafted in full, in the register of their destination file: **all 20**, across
`docs/isa/README.md` (9 blocks, A.0-A.8), `docs/isa/memory-model.md` (2),
`docs/compiler-readiness.md` (6), `docs/isa/encoding-tables.md` (1) and
`docs/P0-P1-CLOSURE.md` (2) — **20 drafted blocks in all**. See `analysis/drafted_docs.md`.

---

## 2. THE SINGLE WORST OMISSION

> **The half-ALU family's destination is byte0's HIGH NIBBLE. `db.json` pins all eight bits of
> byte0 in `match` and models `dst` as a field that the arithmetic uses as a SOURCE. An emitter
> following the descriptor can only ever write `r1` — and there is no fault.**
> `EXP-0180` §3 (DEF-0180-1), `HW-VALIDATED`, `target: G17P`.

Why this one, over `n3_mov`'s one-bit-off source field or the unbound-slot silent drop:

1. **It is silent, and it is total.** Every `half_alu` / `half_alu_ext8` / `half_alu_fma12` result
   lands in `r1`. Not a wrong answer at an edge case — the wrong destination for the whole family,
   every time, with `STATUS OK`.
2. **The deliverable actively points the implementer at the wrong byte.** `docs/isa/agx3.xml` is
   generated from `db.json`, so the defective model is *in* `docs/`. The reader does not have to
   guess wrongly; they have to follow the specification correctly to be wrong. That is the exact
   failure mode `CLAUDE.md`'s "assume the reader has never seen the hardware" clause exists to
   prevent.
3. **The descriptor offers no escape.** Because byte0 is fully match-pinned, a descriptor-driven
   emitter has **no field at all** through which to name a destination. There is nothing to get
   right by luck.
4. **The correction is cheap and was already established three independent ways** — a dense
   nibble sweep (16/16, two carriers, both runs), a structural check across 33,470 gated cases,
   and an arithmetic decomposition — so nothing is blocking it except that nobody wrote it down.

Runner-up, and close: `n3_mov`'s byte+1 model (`F02`), which yields **the wrong register *and* the
wrong half**. It ranks second only because `n3_mov` is newly documented, so an implementer has no
prior expectation to be betrayed — whereas the half-ALU family has been in the docs since
`EXP-0033`.

---

## 3. DEF-0186-1 — the index disagrees with the evidence it indexes, on the most emitter-critical
   of the four `call` bytes

**HIGH severity.** `PROVENANCE.md`'s row for `EXP-0179` states:

> **`call.b6` and `call.tail` are INERT** over the full 0..255 — one distinct full observation per
> carrier across 256 values × 2 runs — so the corpus `0x56` is not load-bearing.

**`EXP-0179/RESULTS.md` §3 says the opposite for `b6`, and says so with a warning attached:**

> **`call.b6` bit 1 (`0x02`) MUST BE SET.** 128 of 256 values legal; bits 0 and 2..7 are
> don't-care. […] ⚠ **`call.b6`'s `encodable_range` is 128, not 256. The first version of this
> result said [inert].**

The experiment found `b6` inert on both *generated* carriers, whose callee is a leaf entered and
left immediately, and then a **second method** — mutating the same byte in the real
compiler-emitted call inside our own compiled `c_frame.metal`, a backward displacement into a
non-leaf callee — showed that the inertness was **carrier blindness**. The corpus value `0x56`
**has bit 1 set**.

**How it happened, mechanically:** commit `955eb6c7` ("call.b6 corrected by the experiment own
second method") landed *before* commit `384c16c1`, which appended the `PROVENANCE.md` row after an
`&&` chain had silently swallowed the first append. The row was written from the pre-amendment
text. This is the *same* `&&` hazard `SUBAGENT_BRIEF.md` documents twice — and here it did not
lose an append, it **preserved a withdrawn claim in the index**.

**Consequence if unnoticed:** anyone drafting `docs/` from `PROVENANCE.md` — which is exactly what
the index is for — would have published "`call.b6` is a don't-care". An emitter following that
would clear bit 1 and get a call whose return context is unestablished, presenting as
**nondeterministic garbage across runs** (`0.0` in one run, `3.0` in the other, which is what
`EXP-0179` measured at `b6 = 0x00`/`0x01`).

**This is the finding that justifies the dispatch's own rule.** "Do not draft a fact you cannot
trace to a committed artifact" is not bookkeeping hygiene; on the one occasion tonight where the
index and the evidence disagreed, the index was wrong, and it was wrong about a byte an emitter
must set.

**Recommended action:** correct the `b6` clause of the `EXP-0179` `PROVENANCE.md` row.
`call.tail` **is** inert — that half of the sentence stands and should not be touched.

---

## 4. Three further paper-trail defects, lower severity

- **`DEF-0186-2` — an unresolved cross-target contradiction with no ruling.**
  `docs/compiler-readiness.md:255` records (M4 lineage) *"slot 128 writes are DISCARDED; the
  128..255 mirror is load-only."* `EXP-0169` §14 measures `0x80` (= 128) on G17P as one of only
  **two** `base_slot` values that store at all. The runs differ in **target** *and* in **how many
  buffers were bound**, so the likely reconciliation is binding population rather than a hardware
  divergence — but **that is a hypothesis and no experiment has tested it.** The draft in
  `analysis/drafted_docs.md` §B.1/§C.4 carries **both** statements with their targets rather than
  overwriting either.
- **`DEF-0186-3` — `docs/P0-P1-CLOSURE.md`'s header contradicts its own table.** Lines 4–8 still
  read *"using the local M4/G16G as the **sole test target**"* and *"the A18 Pro/G17P is
  hands-off"*. That directive was lifted by the user on 2026-08-28 and both `CLAUDE.md` and
  `CODEX.md` carry the replacement; the board's own P0.6 and P0.8 rows are written against G17P.
- **`DEF-0186-4` — three of P0.8's five ranked blockers are closed and the row still lists them.**
  Blocker (1) "`get_sr.sr_sel` untested on G17P, so NO SYSTEM VALUE CAN BE EMITTED AT ALL" is
  closed by `EXP-0178`; blocker (2) "NO CALL CAN BE EMITTED" is closed by `EXP-0179`; blocker (5)
  "`tile_read`/`tile_read_mrt` measured only on M4" is closed as a *measurement* by `EXP-0178` §5
  (though neither instruction is emittable). Blockers (3) and (4) are partly answered by
  `EXP-0163` and `EXP-0172`. Replacement text drafted at `analysis/drafted_docs.md` §E.1.

---

## 5. Observation versus interpretation

**Directly observed (by reading committed files):** the presence or absence of each claim's text
in each `docs/` file at `HEAD`; the exact wording where `docs/` states a claim a later experiment
refuted; the divergence between `PROVENANCE.md`'s `EXP-0179` row and that experiment's own
`RESULTS.md`; and the commit ordering that produced it.

**Interpretation:** the ranking. "Silent wrong answer outranks fault outranks missing capability"
is the dispatch's rule, applied by me; another reviewer could reasonably rank `F06` (a vertex
shader faulting on 128 selector values, where `docs/` currently promises "zero faults") above
`F03` or `F04`. The *set* of gaps is an observation; their **order** is a judgement, and
`docs_gap.json` records the class of each so the order can be re-derived.

**Not established here:** whether any drafted text is *correct as documentation* — that is the
orchestrator's review. This experiment asserts only that each drafted claim is faithful to a
committed experiment artifact, including its bounds.

## 6. Limitations

- **Coverage is `PROVENANCE.md`-anchored.** A fact established since `f517d1e8` whose experiment
  never received a `PROVENANCE.md` row, and which no row mentions in passing, would be invisible
  to this survey. `EXP-0176` measured that class directly and found the reverse chain broken
  "nearly twice as widely as measured", so this is a real residual, not a formality.
- **`EXP-0183`, `EXP-0184` and `EXP-0185` are excluded** (no `RESULTS.md`; live). Their results
  will need the same pass.
- **The bounds were transcribed, not re-derived.** Where an experiment declared a limit
  (`E8_ADD` had no detection power; the half-ALU length rule is untested at byte +6 and later;
  "single link register" is `INFERRED`; `get_sr.form`'s `form = 0` is unidentified;
  `ret.scoreboard` is bounded to a leaf return with one outstanding async load), the draft carries
  the experiment's own words. I did not independently re-verify any bound against `raw/`.
- **Nothing here is a hardware claim.** Every hardware fact in the drafts belongs to the
  experiment cited beside it.

## 7. Verdict

**The audit that prompted this dispatch was not an isolated miss.** Of twenty emitter-facing facts
established in the last wave, **zero** had reached the deliverable intact, **three** were present
in `docs/` in a form a later experiment refuted — which is strictly worse than absence, because a
reader has no reason to doubt them — and one high-severity defect sits in `PROVENANCE.md` itself,
where the index preserves a claim its own experiment withdrew.

Drafted text for all twenty is in `analysis/drafted_docs.md`, ordered by rank, with the
highest-leverage single edit identified as `§A.0`: extending `docs/isa/README.md`'s existing
"a wrong operand-field value produces a **silent zero, not a fault**" list, which is the one place
in the deliverable that tells an implementer to distrust `STATUS OK`, and which currently stops at
the 2026-08-28 M4 wave.

## Clean-room provenance

```
Clean-room provenance: PUBLIC (this repository's own committed artifacts only)
Inputs inspected: PROVENANCE.md; experiments/EXP-{0163,0168,0169,0172,0174,0175,0178,0179,
  0180,0181,0182}/RESULTS.md; docs/**.md; git log f517d1e8..HEAD. No shader bytes were
  compiled, spliced, disassembled or executed. No device was contacted.
Apple binary introspection: NONE
Reproduction: README.md, "Reproduction"
Evidence: analysis/docs_gap.json, analysis/drafted_docs.md
```
