# EXP-0165 — db.json defect repair (EXP-0161, EXP-0160, EXP-0157)

**Analysis + tool repair only. No hardware was run.** Every number in this
experiment is re-derived from the immutable `raw/` trees of EXP-0161, EXP-0160 and
EXP-0157, which ran on the **Apple A18 Pro / G17P**.

```
Clean-room provenance: OWN-SHADER + HW-PROBE (derived: re-analysis of committed
  raw observations from our own authored probes; no new device work)
Inputs inspected: experiments/EXP-0161-g17p-carry-fspecial/raw/**,
  experiments/EXP-0160-g17p-last-field/raw/**,
  experiments/EXP-0157-g17p-emit-misc/analysis/length_rule.json + length_map_q.json,
  and the harness/kernels of those experiments (all authored by us).
  tools/agx-isa/{isadb.py,roundtrip_test.py,validate_labels.py} used READ-ONLY.
  experiments/EXP-M4-13-full-corpus/hex/ (our own compiled shader bytes) for the
  corpus A/B.
Apple binary introspection: NONE
Reproduction: see "Reproduction" below
Evidence: analysis/*.py + work/*.json in this directory; the raw trees cited above
```

## Question

Three experiments reported `db_defects` — descriptors in `tools/agx-isa/db.json`
that say something different from what the hardware does. Two of them (EXP-0161's
`DEF-0161-1` and `-2`) were blocking 20 field verdicts from being merged.

1. Does each defect survive an **independent re-derivation from raw**, done without
   reading the reporting experiment's own verdicts or conclusions?
2. Can the surviving ones be applied to `db.json` **without regressing** the
   round-trip test or the corpus decode metric?
3. Can the 20 held-back `fspecial` / `fspecial_est` / `mov_zext16` verdicts be
   re-expressed against the repaired descriptor from the existing raw data alone?

## Method

For each defect: locate the cited `raw/` records, write an analysis script that
recomputes the claim **from the authored seed vector and the committed register
dumps only**, and compare. Bit rules are checked against *every* value in the
sweep by an exhaustive search over all 256 candidate masks — the rule must accept
exactly the accepted set and reject exactly the rejected set — not against the
accepted set alone. Generation-proof cases are re-scored from the committed block
bytes, ignoring the reporting harness' own `verdict` field.

Then the survivors are applied to `db.json` by a guarded script
(`analysis/apply_defects.py`, `analysis/apply_defects2.py`) — every edit asserts on
the value it replaces — and gated on:

* `tools/agx-isa/roundtrip_test.py` → must be ALL PASS;
* the EXP-0148/EXP-0162 corpus metric (clean files and strict leftover bytes over
  the 1080-file own-MSL corpus) → must not regress;
* `tools/agx-isa/validate_labels.py` → exit 0 (a `db_sha256` WARN is expected);
* a new **functional check** (`analysis/functional_check.py`): does the repaired
  descriptor *decode* and *re-emit* the encodings the HARDWARE accepted in
  EXP-0161's generation runs?

### A constraint that shaped every edit

`validate_labels.py` hard-fails on any `db.json` field with no `validation.json`
entry, and on any `validation.json` entry naming a field `db.json` no longer has.
This experiment may not edit `validation.json`. So the repairs **move existing
field names onto the bytes the hardware uses** rather than introducing new names,
wherever a same-arity permutation exists. Every name whose new position makes the
name itself historical says so in its own `note`, and the re-expressed verdicts in
`analysis/field_verdicts.json` follow the **byte**, not the name.

The single exception is `sfu_marker`, which had ZERO fields and therefore could
carry no evidence at all; giving it its two measured live-bit fields necessarily
adds two new names. That is the only reason `validate_labels.py` exits 1 after
this experiment, and merging `analysis/field_verdicts.json` clears it.
`analysis/revert_sfu_marker_fields.py` is the escape hatch.

## Reproduction

```sh
# re-derivations (each prints its own evidence table; none touches the device)
python3 experiments/EXP-0165-db-defect-repair/analysis/rederive_def1_fspecial.py
python3 experiments/EXP-0165-db-defect-repair/analysis/def1_summary.py
python3 experiments/EXP-0165-db-defect-repair/analysis/rederive_gen03.py
python3 experiments/EXP-0165-db-defect-repair/analysis/rederive_def2_zext.py
python3 experiments/EXP-0165-db-defect-repair/analysis/rederive_def3_fnclass.py
python3 experiments/EXP-0165-db-defect-repair/analysis/rederive_def4_roundmode.py
python3 experiments/EXP-0165-db-defect-repair/analysis/rederive_def67_carry.py
python3 experiments/EXP-0165-db-defect-repair/analysis/rederive_imad.py
python3 experiments/EXP-0165-db-defect-repair/analysis/rederive_0160_misc.py

# the repair itself (run against a PRISTINE db.json; every edit is guarded)
python3 experiments/EXP-0165-db-defect-repair/analysis/apply_defects.py  tools/agx-isa/db.json
python3 experiments/EXP-0165-db-defect-repair/analysis/apply_defects2.py tools/agx-isa/db.json

# gates
python3 tools/agx-isa/roundtrip_test.py
python3 experiments/EXP-0165-db-defect-repair/analysis/ab_gate.py            # corpus A/B
python3 experiments/EXP-0165-db-defect-repair/analysis/functional_check.py tools/agx-isa
python3 tools/agx-isa/validate_labels.py

# the re-expressed verdicts for the orchestrator to merge
python3 experiments/EXP-0165-db-defect-repair/analysis/make_verdicts.py \
  > experiments/EXP-0165-db-defect-repair/analysis/field_verdicts.json
python3 work/merge_verdicts.py --dry-run \
  experiments/EXP-0165-db-defect-repair/analysis/field_verdicts.json
```

`analysis/ab_gate.py <tree>...` also A/B's candidate trees; `work/probe_r9`,
`work/probe_op04` and `work/probe_hp` are the three MEASURED-BUT-NOT-APPLIED
length-rule variants discussed in `RESULTS.md`.

## Verdict

See `RESULTS.md`. Twelve of the thirteen defects re-derived cleanly; one
(`DEF-0161-3`) is **confirmed in part and refuted in part** and was applied only in
its corrected form; one severity claim (`DEF-0161-2`'s "the register selector is
invisible to an emitter") is **wrong** and is reported as such.
