# `work/dbtriage/` — supporting material for `work/DB-DEFECT-TRIAGE.md`

Desk work only: no GPU, no SSH, no device. Everything here reads committed repository
artifacts (`tools/agx-isa/*`, `experiments/EXP-01*/analysis/field_verdicts.json`, and the
own-MSL corpus `experiments/EXP-M4-13-full-corpus/hex`). No Apple binary was introspected.

| file | role |
|---|---|
| `EXP-*.defects.json` | the raw `db_defects` block extracted verbatim from each experiment's `field_verdicts.json` — the input to the triage |
| `apply_ab_defects.py` | **the class (a) + (b) patch.** Idempotent: re-running reports everything as already-present. Edits `tools/agx-isa/db.json` and mirrors the field-model changes into `validation.json` (which the `validate_labels.py` gate hard-requires), then recomputes the coverage block |
| `make_c_variant.py` | builds a variant copy of the ISA tree under `cvar/<name>/` with ONE class (c) change applied. `--list` for names. Never touches `tools/agx-isa/` |
| `ab_run.sh` | runs round-trip + the frozen corpus metrics for one variant into `ab/<name>/` |
| `tokenize_corpus.py` | the corpus metric (clean files + strict leftover bytes), same shape as `EXP-0148/analysis/tokenize_corpus.py` so the numbers compare directly |
| `rt_shim.py` | runs `roundtrip_test.py` against a variant tree (copied from EXP-0148) |
| `c_functional_check.py` | asks what a corpus A/B cannot: does the variant decode the encoding the **hardware** accepts? This is what exposed that four of the (c) candidates are gated by the length rule, not the match |
| `ab/*/metrics.json`, `ab/*/strict.json` | the measurements quoted in `DB-DEFECT-TRIAGE.md` §4 |
| `show.py`, `fields.py` | one-line descriptor / field-layout dumpers |
| `roundtrip_final.txt` | the post-change round-trip transcript (302 OK / 0 FAIL) |

Regenerate the variant trees (deleted after measurement; they are ~5.6 MB of copied tooling):

```sh
for v in baseline c1_pixel_order c1b_pixel_order c2_carry_gen c3_cvt_bf16 \
         c7_sfu_marker c7b_sfu_marker c8_reg_move; do
  python3 work/dbtriage/make_c_variant.py $v && bash work/dbtriage/ab_run.sh $v
done
python3 work/dbtriage/c_functional_check.py
```

The pre-change `db.json` / `validation.json` baseline is `git show HEAD:tools/agx-isa/db.json`
(and likewise `validation.json`); no local copy is kept.
