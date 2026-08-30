# EXP-0182 — PRE-REGISTRATION

**Frozen 2026-08-30, before any edit to `tools/agx-isa/isadb.py`.**
Repo revision at freeze: `0f38e2f871ecb85e9c014c1398054debd044d0c3` (working tree dirty:
12 paths, all owned by the orchestrator or by EXP-0180/0181 — none of them `isadb.py`).

| artifact | sha256 at freeze |
|---|---|
| `tools/agx-isa/isadb.py` | `9cda47a1d4b3857c9f20423ab5d63c38050d37220da06bc5d2dc12a77d6ef1a8` |
| `tools/agx-isa/db.json` | `1ada4e7bb7879cd607829d7e7e657c8d3e5b9b000b63c5d602adfa3f7740be04` |
| `analysis/anchors.json` | `019d26b7305d1e71829d6efe9e41db9694606f72cc11222c0f866a79846b092c` |
| `analysis/anchor_decode_baseline.json` | `68ca7301312b6b4ce79bdd4710cb96f7a16043b51cf84c43602684ed5c438095` |

## 0. Clean-room provenance

```
Clean-room provenance: OWN-SHADER / HW-PROBE (re-analysis only — NO device, NO SSH, NO GPU)
Inputs inspected: our own db.json, our own isadb.py, our own committed experiments/EXP-*/raw,
                  our own EXP-M4-13-full-corpus/hex (own-MSL compiled shaders)
Apple binary introspection: NONE
Reproduction: analysis/*.py, all offline and re-runnable
```

## 1. Question

Our tokenizer cannot decode encodings our own hardware runs accepted. Five descriptors
(`bf_add_dst`, `bf_fma_dst`, `cvt_bf16`, `cvt_f2h_dst`, `hminmax`) are counted **emittable**
while the exact byte string each of them was dispatched as, and which the GPU executed
against a host oracle, does not tokenize. Can `isadb.instr_length` be fixed so the question
is moot — and if not, what exactly is the cost?

## 2. Hypotheses (falsifiable)

* **H1 — the defect is a FAMILY-GATING bug, not five accidents.** `instr_length` keys several
  families on bytes that are *operand or destination selectors*, not on the bits that identify
  the instruction. Named instances: the full-byte gate `if b0 == 0x10` (DEF-0180-7) when byte0's
  high nibble is the destination register; `if b0 == 0x11` and its partial low-nibble
  generalisation; and the low-nibble-2 per-dst fallbacks `if b0 == 0x02/0x12/0x22/0x32`.
  **Predicts:** a rule rewritten to key on the *identifying* bits (byte+2 op-select, byte+3
  source-descriptor class) decodes each anchor at every destination nibble.
  **Refuter:** an anchor that still fails after the rule is keyed on identifying bits alone, or
  a family where the identifying bits do not separate the lengths.
* **H2 — the fix is corpus-neutral or better.** Keying on identifying bits is *additive* where
  the old rule returned `LEN_UNKNOWN`, and changes an existing length only where the old rule
  was demonstrably wrong. **Predicts** T2 below holds. **Refuter:** clean files fall or leftover
  bytes rise.
* **H3 — some anchors cannot be closed from `isadb.py` alone.** Where a descriptor's `db.json`
  `match` pins a constant the hardware-validated anchor does not carry, no length rule can make
  it decode, because `decode_one` filters candidates by `match`. **Predicts** at least one of the
  five is BLOCKED on `db.json` (which this experiment must not edit). **Refuter:** all five decode.

## 3. Frozen acceptance thresholds

Measured **before** any edit; a candidate is judged against these numbers and nothing else.

| id | gate | frozen baseline | rule |
|---|---|---|---|
| **T1** | the five DEF-0181-2 anchors decode to their own mnemonic at the declared length | 0 of 5 | MUST reach 5 of 5, **or** a failure must be shown to be blocked by a `db.json` `match` constant, quoted exactly |
| **T2** | own-MSL corpus (1080 files, `EXP-M4-13-full-corpus/hex`) | **clean 833/1080, leftover 388604, tokens 25419** | clean MUST be ≥ 833 **and** leftover MUST be ≤ 388604. A candidate that regresses either is **REPORTED, NOT APPLIED** |
| **T3** | `roundtrip_test.py`, run in a **SUBPROCESS** (DEF-0175-2) | 302 OK / 0 FAIL / 0 crash / ALL PASS | MUST stay 0 FAIL, 0 crash, ALL PASS, OK ≥ 302 |
| **T4** | `analysis/anchors.json` regression corpus — 255 committed HW anchors | **245 of 255 self-decode** | every anchor passing at baseline MUST still pass; 0 regressions |
| **T5** | `tools/agx-isa/validate_labels.py` | exit 0 (pre-existing `db_sha256` WARN is the orchestrator's) | MUST stay exit 0 |
| **T6** | emittability headline (`emit_worklist.py`) against the **live** `validation.json` | **54 of 166 emittable** (the dispatch's "48" moved when the orchestrator merged EXP-0180; §RESULTS isolates my delta) | my `isadb.py` edit MUST NOT change it — it is not an input to that computation; measured, not assumed |

**Anchor selection rule (frozen, R-A1..R-A5).** See the docstring of
`analysis/collect_anchors.py`. `field: null` alone does NOT qualify a record as a baseline —
EXP-0171 writes field-less *mutated* sweep records, and admitting them put a byte+2 = 0x04
"`bf_alu`" into the set.

## 4. Method (order is binding)

1. **Re-derive every defect from committed `raw/` before changing anything.** Precedent:
   EXP-0165 re-derived nine and found one half wrong; EXP-0175 refused to propagate a fix that
   would have created a new defect. **A defect that does not survive re-derivation is reported
   and NOT applied.**
2. Build the general instrument first: `analysis/family_gate_audit.py` asks, from `db.json`
   alone, *for every descriptor whose own `match` leaves byte0's high nibble free, does
   `instr_length` return the declared length at all sixteen destination nibbles?*
3. Fix the family gating **generally**. A per-leader patch that leaves the next family broken
   is not a fix.
4. Gate every candidate with `analysis/ab_gate.py` (subprocess round trip — DEF-0175-2) and
   `analysis/anchor_decode_test.py`.
5. **Do not pre-empt EXP-0180.** DEF-0180-2's hardware verdict has landed (that experiment is
   complete; `analysis/length_rule.json` measures the half-ALU length as a function of
   `(byte+2 & 7, byte+4 & 3)` and finds *both* `db.json`'s stated rule and `isadb.py`'s
   implemented rule wrong). This experiment fixes the **family GATE**; it measures but does not
   silently adopt the **length FORMULA**, which is EXP-0180's result to merge.

## 5. Known confounders

* `validation.json` and several experiment trees are **modified in the working tree by other
  actors**. Every number is stated against the live file and the delta of *my* edit is isolated
  by an A/B against an unmodified copy of the tree.
* `roundtrip_test.py` is **not** an emitter gate (EXP-0170: it passes against an assembler that
  cannot clear a bit; EXP-0173: it passes with two operands swapped). It is used here only as a
  no-regression check, never as evidence that anything can be emitted.
* `ab_gate.py` must run the round trip in a **subprocess**: DEF-0175-2 showed the in-process
  (`runpy`) version reports ALL PASS for every tree after the first, because `import isadb`
  resolves once.
* Lengthing bytes that no descriptor matches makes `decode_one` **raise**, which halts the corpus
  walk at that offset. A length "fix" with no matching descriptor can therefore *regress* T2.
  This is the predicted shape of the `0x10` (DEF-0180-7) case, whose `half_alu` descriptor pins
  the full byte0 in `db.json`.
