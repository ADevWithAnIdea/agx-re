# EXP-0166 — recovering EXP-0146's 94 orphaned field verdicts

**Target of the evidence under adjudication:** Apple **M4 / G16G** (EXP-0146's only target).
**Target of this experiment:** none. This is an **offline re-derivation** from committed raw
evidence. No device was touched — see "Device arm" below.

## Question

`experiments/EXP-0146-m4-emit-int-misc/analysis/field_verdicts.json` holds 94 field verdicts, all
labelled `hardware-run`, from dense sweeps on the M4. **None of them ever reached
`tools/agx-isa/validation.json`.** The mechanical cause is a key-convention mismatch: EXP-0146 keys
its verdicts `<mnemonic>.<field>@<carrier>` while `work/merge_verdicts.py` requires exactly
`<mnemonic>.<field>`, so every key was rejected and the file was skipped.

The question is **not** "can the keys be renamed". It is: *which of those 94 verdicts survive as
defensible, mergeable, emitter-grade evidence* once (a) they are re-derived from EXP-0146's own raw
records rather than from its analysis JSON, and (b) the later G17P work that has overtaken parts of
its interpretation is applied?

## Hypotheses, falsifiers, thresholds

All frozen in `PRE_REGISTRATION.md` before the adjudication was written: H1–H4, falsifiers F1–F5,
the three-verdict liveness policy with its numeric thresholds, gates G1–G5, and the G3 veto list.
Seven amendments (A1–A7) are recorded with timestamps and a direction ledger; five can only weaken
a row, one is neutral, and the single two-directional one (A3) is reported in both versions.

## Method

Pure re-analysis. No new machine code was produced or inspected; the only bytes read are hex
strings inside EXP-0146's append-only JSONL, which came from compiling `EXP-0146/kernels/*.metal`,
which we wrote.

1. **Re-derive from raw.** Load `raw/run01` and `raw/run03` (the two gated runs; `run02` is
   EXP-0146's own declared contaminated capture and stays excluded). Per field, per carrier, per
   value: is the observation informative, do the two runs agree, and does it move the observable?
2. **Re-locate every field's bits from the recorded bytes** (A2), so a verdict is matched to the
   `db.json` field that occupies *those bits today* rather than to a name that may have been
   renamed, split, or moved.
3. **Decompose** dense byte sweeps into the sub-fields they contain (A5), recovering evidence that
   a strict name/bit match would discard.
4. **Adjudicate** with the frozen thresholds, then apply the gates: db-field existence, no
   downgrade, later-experiment veto, target labelling, no `db.json` edits.
5. **Cross-check** every survivor against every later experiment that touched the same instruction
   (EXP-0139, 0153, 0154, 0155, 0157, 0158, 0161, 0164, 0165) and report divergences instead of
   averaging them.

## Commands

```sh
python3 analysis/adjudicate.py          # stage 1 — per-arm statistics  -> derived_stats.json
python3 analysis/verdicts.py            # stage 2 — decomposition + gates -> decomposed_fields.json
python3 analysis/emit_deliverables.py   # stage 3 — the deliverables (runs 1 and 2 itself)
python3 ../../work/merge_verdicts.py --dry-run analysis/field_verdicts.json   # verification
```

Stage 3 is the single entry point; stages 1 and 2 are importable and run automatically.

## Device arm

`PRE_REGISTRATION.md` §6 pre-registered a *conditional* confirmation run on the A18 Pro / G17P,
permitted only after the offline analysis was complete. **It was not run.** The coordinator placed
a hold on all device work (EXP-0167 needs a quiet machine), and independently
`FIELD-SWEEP-PROTOCOL` §7 now records that a busy-machine re-run manufactures faults, so a single
unlocked confirmation run would not have been confirmation anyway. Every finding here is offline.

## Outputs

| file | content |
|---|---|
| `RESULTS.md` | observations vs interpretation, survivor count, emittability impact, limitations |
| `analysis/field_verdicts.json` | **12 merge-ready rows**, flat `<mnemonic>.<field>`, survivors only |
| `analysis/withheld.json` | all 53 rejected keys with reason and numbers |
| `analysis/proposed_db_defects.json` | 6 descriptor defects with evidence (dispatch §4) |
| `analysis/derived_stats.json` | per-arm counters, both comparators, bit relocation, coverage |
| `analysis/decomposed_fields.json` | the A5 sub-field extractions |
| `analysis/exp0146_disposition.json` | all 94 original keys → what happened to each |
| `analysis/h3_srcB_ext.json` | the H3/F3 test on `iadd2.srcB_ext` |
| `work/db_snapshot.json`, `work/validation_snapshot.json` | the pinned tool state (EXP-0165 was editing `db.json` live) |

## Clean-room provenance

```text
Clean-room provenance: OWN-SHADER + HW-PROBE (re-analysis of committed raw evidence only)
Inputs inspected: EXP-0146's append-only JSONL captures, produced from MSL we authored;
                  tools/agx-isa/{db,validation}.json; later experiments' committed RESULTS.md
                  and analysis/*.json
Apple binary introspection: NONE
Reproduction: python3 analysis/emit_deliverables.py
Evidence: EXP-0146 raw/ (SHA-256 in PRE_REGISTRATION.md §7 and manifest.json) + this analysis/
```

No Apple binary was disassembled, decompiled, symbol-dumped, strings-scanned or debugged. No new
machine code was inspected at all. Nothing outside this experiment directory was written, nothing
was committed, and `tools/agx-isa/db.json`, `tools/agx-isa/validation.json`, `docs/`,
`PROVENANCE.md` and `work/merge_verdicts.py` were read but never modified (`work/merge_verdicts.py`
was executed only with `--dry-run`, which does not write).
