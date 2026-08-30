# EXP-0182 — the tokenizer could not decode encodings our own hardware ran

**Status: COMPLETE. `tools/agx-isa/isadb.py` is edited and STABLE.**
No device, no SSH, no GPU: this is pure re-analysis of committed evidence and of our own tools.

## Question

Three experiments reached the same wall from different directions:

* **DEF-0181-2 (EXP-0181)** — five descriptors' HW-VALIDATED anchors do not tokenize:
  `bf_add_dst`, `bf_fma_dst` (the known DEF-0171-2) plus `cvt_bf16`, `cvt_f2h_dst` and
  `hminmax`, the last three newly found. `hminmax` decoded at **2 of 16** destination
  nibbles — and not at the validated one.
* **DEF-0180-7 (EXP-0180)** — `isadb.instr_length` gates the native-half family on the
  **full byte** (`if b0 == 0x10`) although byte0's **high nibble is the destination
  register**, so any half op writing anything but `r1` does not length and does not
  tokenize. The same function's docstring records this exact bug being found and fixed for
  the `0x09` float family and never applied to `0x10` or `0x11`.
* **DEF-0180-2 (EXP-0180)** — `db.json`'s stated half-ALU length rule and `isadb.py`'s
  implemented one contradict each other, and EXP-0180's G17P measurement refutes both.

It decides a published number: all five descriptors are currently counted **emittable**. If
an instruction whose validated encoding our own tokenizer cannot decode is held not to be
emittable, the headline drops by five. **This experiment's job was to make the question moot
by fixing the tokenizer, or to state exactly what the fix costs.**

## Hypotheses

Frozen in `PRE_REGISTRATION.md` before any edit: **H1** the defect is one family-gating bug,
not five accidents — `instr_length` keys several families on bytes that select *operands or
destinations* rather than on the bits that *identify* the instruction; **H2** keying on the
identifying bits is corpus-neutral or better; **H3** at least one anchor cannot be closed
from `isadb.py` at all, because `decode_one` filters candidates by a `db.json` `match`
constant this experiment must not edit.

All three held. See `RESULTS.md`.

## Method

1. **Re-derive every defect from committed `raw/` before touching anything** (§1 of
   `RESULTS.md`). A defect that did not survive re-derivation would have been reported and
   not applied.
2. Build general instruments first: `analysis/collect_anchors.py` (255 HW anchors over 95
   mnemonics under a frozen selection rule), `analysis/anchor_decode_test.py` (the asymmetric
   regression test the repo did not have), `analysis/family_gate_audit.py` and
   `analysis/opsel_length_map.py` (the family-gating question asked mechanically from
   `db.json`).
3. Fix the family gating **generally**, as named patches in `analysis/apply_fix.py`.
4. Gate every candidate on the frozen thresholds with `analysis/ab_gate.py` — whose round
   trip runs in a **subprocess**, the DEF-0175-2 fix. Refuse anything that regresses.

## Exact reproduction

```sh
cd experiments/EXP-0182-tokenizer-lengths
python3 analysis/collect_anchors.py > analysis/anchors.json     # 255 anchors, frozen rule
python3 analysis/anchor_decode_test.py                          # the five + 255-anchor corpus
python3 analysis/family_gate_audit.py                           # dst-nibble audit from db.json
python3 analysis/opsel_length_map.py                            # low-nibble-2 op-select map
python3 analysis/apply_fix.py work/cand_full n1 r9 n2 n2b n2c n0c
python3 analysis/ab_gate.py work/cand_full                      # corpus + subprocess round trip
python3 analysis/demo_cvt_bf16_dbfix.py                         # the one db.json change, NOT applied
# what was actually applied:
python3 analysis/apply_fix.py --inplace ../../tools/agx-isa n1 r9 n2 n2b n2c n0c
```

`work/tree_before/` is the pristine pre-fix `tools/agx-isa`, so every candidate stays
reproducible after the fix has been applied in place; `work/cand_check` rebuilt from it is
byte-identical to the applied `tools/agx-isa/isadb.py`.

## Clean-room attestation

```
Clean-room provenance: OWN-SHADER / HW-PROBE (re-analysis only — no device was touched)
Inputs inspected: our own tools/agx-isa/{isadb.py,db.json,validation.json}; our own committed
                  experiments/EXP-*/raw/**/*.jsonl and EXP-0156's 00_inputs.json; our own
                  own-MSL compiled corpus experiments/EXP-M4-13-full-corpus/hex
Apple binary introspection: NONE
Reproduction: the commands above; every analysis script is offline and deterministic
Evidence: analysis/{anchors,anchor_decode_baseline,ab_metrics,family_gate_audit_*,
          opsel_length_map_*}.json, work/isadb.py.{before,after}
```

## Files not owned by this experiment

`db.json`, `validation.json`, `docs/`, `PROVENANCE.md` and `docs/P0-P1-CLOSURE.md` were
**not modified**. `db.json`'s sha256 is unchanged from pre-registration
(`1ada4e7bb7879cd6…`). The one `db.json` change this experiment recommends is built and
measured in `work/demo_dbfix/` and left for the orchestrator.
