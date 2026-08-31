# EXP-0217 — applying EXP-0216's descriptor proposals

**Type:** desk experiment. **No device was touched.** `EXP-0213-quiet-confirmation-2` held
the A18 Pro for quiet Gate E confirmations throughout; see "Isolation" below.

## Question

`experiments/EXP-0216-descriptor-identity/analysis/proposed_db_edits.json` holds six
descriptor-geometry proposals (P1…P6) produced by a pure re-analysis of committed raw. None
was applied; EXP-0216 edited nothing and committed nothing. The question here is the same
one EXP-0212 asked of its own queue:

> Which of these proposals can be applied **from committed evidence alone**, what does each
> one cost in tokenization, and which of them imply an edit **stronger than the evidence
> behind them**?

## Hypothesis / falsifier

- **H1.** Every proposal is backed by a locatable committed artifact and re-derivable
  numbers. *Falsifier:* a claimed count that the committed analysis does not reproduce.
  *(H1 held — the four headline counts were re-derived here from
  `EXP-0216/analysis/q2_sibling.json` before being written into any note.)*
- **H2.** The proposals that are prose or field metadata are tokenization-neutral.
  *Falsifier:* any change to clean files, leftover bytes, instruction count, resync gap,
  descriptor firing mix, or record-set tokenization. *(H2 held — every metric is
  **bit-identical** before and after, including the firing mix.)*
- **H3.** At least one proposal will turn out to imply an edit its own evidence does not
  carry, and must be refused. *(H3 held — **six** refusals, three of them match-bit
  candidates that were built and measured first.)*

## Method

1. **Triage before editing** — `TRIAGE.md`, every item, split into prose / match-bit /
   field-change / refused. No file was opened for writing until it was complete.
2. **Re-derive every quoted count** from EXP-0216's committed analysis JSON, never from the
   proposal's prose.
3. **Build each match-bit candidate into an isolated tree** with
   `analysis/mkvariant.sh` (the EXP-0212 precedent) and measure it against **two**
   independent denominators — the 1 080-file own-MSL corpus and the two committed record
   sets EXP-0216 analysed — plus `roundtrip_test.py`. Report per change, not in aggregate.
4. **Apply only the prose/metadata groups** to the live tree, as a re-runnable transform.
5. **Amend, never relabel** — the `validation.json` notes that EXP-0216's finding makes
   wrong are amended in place; no `label`, `range`, `evidence`, `target`, `start` or
   `width` is touched.
6. **Re-verify**: `validate_labels.py`, `roundtrip_test.py`, strict + resync corpus decode,
   record-set decode, `match_overlap_report.py`, and a whole-db field overlap/overrun sweep.

## Exact reproduction

```sh
# from the repository root, against the pre-application tree
git checkout tools/agx-isa/db.json tools/agx-isa/validation.json

python3 experiments/EXP-0217-descriptor-application/analysis/apply_db_edits.py \
        tools/agx-isa/db.json /tmp/db_0217.json
cp /tmp/db_0217.json tools/agx-isa/db.json          # written with indent=1
python3 experiments/EXP-0217-descriptor-application/analysis/apply_validation_notes.py

python3 tools/agx-isa/validate_labels.py
python3 tools/agx-isa/roundtrip_test.py
python3 work/dbtriage/tokenize_corpus.py tools/agx-isa /tmp/strict.json
python3 work/dbtriage/tokenize_corpus.py tools/agx-isa /tmp/resync.json --resync
python3 experiments/EXP-0217-descriptor-application/analysis/tokenize_records.py \
        tools/agx-isa /tmp/records.json
python3 tools/agx-isa/match_overlap_report.py

# the three REFUSED match candidates (isolated trees; the live tree is never touched)
bash experiments/EXP-0217-descriptor-application/analysis/mkvariant.sh m1 --only m1_cvt_f2h_match
bash experiments/EXP-0217-descriptor-application/analysis/mkvariant.sh m2 --only m2_bf_alu_match
bash experiments/EXP-0217-descriptor-application/analysis/mkvariant.sh m3 --only m3_bf_dst_match
# then tokenize_corpus.py / tokenize_records.py / work/dbtriage/rt_shim.py against each

# the independent re-check of the already-applied isadb._n1_len widening (commit 1fd2f16f)
mkdir -p .../work/var_prewiden
git show 1fd2f16f~1:tools/agx-isa/isadb.py > .../work/var_prewiden/isadb.py
cp tools/agx-isa/agxisa.py tools/agx-isa/db.json .../work/var_prewiden/
```

All numbers are in `analysis/measurements.json`.

## Isolation from the in-flight wave

`EXP-0213-quiet-confirmation-2/CAPTURE_CONTRACT.json` pins its own frozen `pinned/db.json`
(sha256 `2412eac1…`, which is *not* `tools/agx-isa/db.json`) and declares `tools/agx-isa/**`
under `writes.forbidden`. The running confirmation reads a frozen copy, so this application
cannot disturb it in either direction. No device was contacted from this experiment; no
shader was compiled.

## Clean-room provenance

```text
Clean-room provenance: PUBLIC (this repository's own committed artifacts only)
Inputs inspected:      tools/agx-isa/{db,validation,isadb}.json|py,
                       experiments/EXP-0216-descriptor-identity/{RESULTS.md,analysis/},
                       experiments/EXP-0212-db-defect-application/{RESULTS.md,analysis/},
                       RE_EXPERIMENT_PROCESS_CORRECTIONS.md,
                       the raw JSONL of EXP-0144 (M4/G16G) and EXP-0171 (G17P) -- all
                       produced from MSL we authored, compiled at runtime and dispatched
                       on our own hardware,
                       experiments/EXP-M4-13-full-corpus/hex (our own compiled shaders)
Apple binary introspection: NONE. No disassembly, no decompilation, no Apple binary opened.
Device contacted:      NONE.  Shader compiled: NONE.  Raw observations created: NONE.
Frozen inputs:         raw/db.json.BEFORE          sha256 02a47fc6…  (matches the dispatch)
                       raw/validation.json.BEFORE  sha256 6e7ff3f1…
                       raw/isadb.py.FROZEN         sha256 731e8a2f…
Result:                raw/db.json.AFTER           sha256 90166d96…
                       raw/validation.json.AFTER   sha256 7e90e4d5…
Committed:             NOTHING. The tree is left dirty, per the dispatch.
```
