# EXP-0183 — the native-half descriptor: re-derive, then repair

**PURE ANALYSIS. No device, no SSH, no GPU.** Target of the evidence re-read: **A18 Pro /
G17P** (EXP-0180's two gated runs, plus EXP-0169/0168/0162).

## Question

`docs/isa/emit-worklist.md` lists 22 instructions one field away from emittable. Several are
blocked by descriptor defects that EXP-0180 confirmed on hardware and EXP-0181 confirmed by
span audit — **none of which had been applied to `tools/agx-isa/db.json`**. Which of those
defects survive an *independent* re-derivation from the committed raw, and what is the
corrected descriptor?

The standing rule this experiment exists to honour: **a defect that does not survive
re-derivation is reported and NOT applied.** EXP-0165 re-derived nine and found one half
wrong; EXP-0175 refused to propagate a fix that would have created a new defect; EXP-0180
refuted and withdrew its own DEF-0180-3.

## Hypotheses and falsifiers

Frozen in `PRE_REGISTRATION.md` before any edit: H1/H1b/H1c (the destination is byte0's high
nibble), H2 (the measured length rule), H3 (the six semantic withdrawals), H4 (three citation
defects), H5 (EXP-0181's two re-scores). H1b2 and H6 were added during analysis and are
labelled as such in `RESULTS.md`.

## Method

1. `analysis/rederive.py` → `analysis/defects_rederived.json`. Reads only the raw trees listed
   in `raw/README.md`; does **not** import any prior experiment's analysis module. Recomputes
   register deltas, fp16 arithmetic, marker counts and cross-run agreement from scratch.
2. `analysis/apply_db_edits.py` builds a candidate `db.json` from a frozen snapshot
   (`work/base_live/`), in five independently selectable edit groups.
3. `analysis/ab_gate.py` gates each candidate. **Both** halves run in a subprocess
   (`analysis/corpus_probe.py`) — DEF-0175-2: EXP-0175's in-process gate let the first tree
   measured win `sys.modules['isadb']`, so every later candidate silently re-measured the
   first tree's database and it reported ALL PASS for a candidate that crashed. EXP-0182 fixed
   the round-trip half; this fixes both.
4. `experiments/EXP-0182-tokenizer-lengths/analysis/anchor_decode_test.py` run before and
   after — it asserts that byte strings our own GPU executed decode to the descriptor they
   were dispatched as, which the symmetric round trip cannot see.
5. `analysis/halfdst_decode_check.py` adds the population that test does not carry: EXP-0180's
   sixteen hardware-executed DSTNIB byte strings.
6. `analysis/make_validation_updates.py` → `analysis/validation_updates.json` for the
   orchestrator; `analysis/simulate_merge.py` proves that applying it exactly yields a
   `validation.json` that passes `validate_labels.py` with zero FAILs.

## Reproduction

```sh
cd /Users/user/asahi_re/public/agx-re/experiments/EXP-0183-halfalu-descriptor
python3 analysis/rederive.py                       # re-derive every defect from raw
python3 analysis/apply_db_edits.py work/base_live/db.json /tmp/out.json   # (use work/, not /tmp)
python3 analysis/ab_gate.py work/cand_final work/cand_final_plus_fold
python3 ../EXP-0182-tokenizer-lengths/analysis/anchor_decode_test.py --tree work/cand_final
(cd work/cand_final && python3 ../../analysis/halfdst_decode_check.py)
python3 analysis/make_validation_updates.py
python3 analysis/simulate_merge.py
```

The landed `tools/agx-isa/db.json` is reproduced exactly by

```sh
python3 analysis/apply_db_edits.py work/base_live/db.json tools/agx-isa/db.json \
        --only=half_match,half_fields,bf16_match,lengthdoc
```

## Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE (re-read offline; no new run)
Inputs inspected: the committed raw/ trees of EXP-0180, EXP-0169, EXP-0168 and EXP-0162 --
  records of AGX machine code compiled by the PUBLIC runtime API from MSL authored in this
  project, and byte splices of that same code; plus EXP-0180's own authored harness
  (harness/isa_helpers.py) and tools/agx-isa/db.json.
Apple binary introspection: NONE. No Apple binary was disassembled, decompiled,
  symbol-dumped, strings-scanned or debugged.
Reproduction: the commands above.
Evidence: analysis/{defects_rederived,ab_metrics,validation_updates,emittability_simulation,
  halfdst_decode_before,halfdst_decode_after}.json, work/{base_live,base_head,cand_*},
  work/inputs_sha256.json.
```
