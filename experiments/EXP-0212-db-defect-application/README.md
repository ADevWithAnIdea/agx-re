# EXP-0212 — applying the queued, hardware-confirmed descriptor defects

**Type:** desk experiment. **No device was touched.** A sibling experiment
(`EXP-0213-quiet-confirmation-2`) was running quiet confirmations on the G17P for the whole
of this work; see §"Isolation from the in-flight wave" below for the check that proves this
application could not disturb it.

## Question

`tools/agx-isa/PENDING_DB_DEFECTS.md` held **31 machine-extracted defects** (from the
`db_defects` blocks of EXP-0201, 0202, 0203, 0205, 0206 and 0207) plus an **11-item prose
tail** (EXP-0199, EXP-0200, EXP-0204). All were confirmed on G17P hardware on 2026-08-30 and
all were queued rather than applied, for one stated reason: several of them **move field
spans**, and `work/merge_verdicts.py` correctly REFUSES a verdict whose `start`/`width` no
longer match the descriptor (DEF-0166-2 — names get reused across a repair, so a name-keyed
merge would silently attach a verdict to the wrong byte).

Device experiments have drained off the live `db.json`. The question is therefore:

> Which of these 42 items can be applied **from committed evidence alone**, what does each
> one cost in tokenization, and for every span that moves, what happens to the
> `validation.json` rows that were measured against the *old* bits?

## Hypothesis / falsifier

- **H1.** Every defect in the queue is backed by a locatable committed artifact, so the
  application is a mechanical, auditable transform.
  **Falsifier:** a named defect whose evidence cannot be found under any keying. *(H1 held:
  every cited path resolved — see `analysis/evidence_check.txt`.)*
- **H2.** The span moves and match corrections are tokenization-neutral against the
  1080-file own-MSL corpus.
  **Falsifier:** any change to clean files, leftover bytes, or instruction count.
  *(H2 held for the strict metric and for instruction count; it is REFUTED in one bounded
  way — the `sfu_marker` match tightening re-attributes 31 resync tokens. See RESULTS §5.)*
- **H3.** At least one queued item will turn out to be **unsupported by its own evidence at
  the strength the PENDING file implies**, and must be left alone.
  *(H3 held: 6 items refused outright and 6 more applied only in part. RESULTS §3.)*

## Method

1. **Triage before touching anything** — `TRIAGE.md`, all 42 items, split into
   (a) non-span, (b) span-moving, (c) refused/partial.
2. **Verify each defect against committed evidence** — every cited raw/derived path resolved
   and, for the span moves, re-derived from the raw itself (value coverage counted per arm,
   not taken from prose).
3. **Apply (a) first**, then (b), then the match corrections, each as a re-runnable
   transform: `analysis/apply_db_edits.py <in> <out> [--only GROUP,...]`.
4. **Measure every group A/B in an isolated tree** (`analysis/mkvariant.sh`) with
   `work/dbtriage/tokenize_corpus.py` + `work/dbtriage/rt_shim.py`, so no measurement
   depends on the live tree being mutated.
5. **Handle the moved rows explicitly** — `analysis/apply_validation_notes.py`.
6. **Re-verify**: `validate_labels.py`, `roundtrip_test.py`, strict + resync corpus decode,
   `match_overlap_report.py`, and a whole-db field-overlap/overrun sweep.

## Exact reproduction

```sh
# from the repository root, against the pre-application db.json
git stash                                    # or start from raw/db.json.BEFORE
python3 experiments/EXP-0212-db-defect-application/analysis/apply_db_edits.py \
        tools/agx-isa/db.json /tmp/db_new.json
cp /tmp/db_new.json tools/agx-isa/db.json    # written with indent=1
python3 experiments/EXP-0212-db-defect-application/analysis/apply_validation_notes.py

python3 tools/agx-isa/validate_labels.py
python3 tools/agx-isa/roundtrip_test.py
python3 work/dbtriage/tokenize_corpus.py tools/agx-isa /tmp/strict.json
python3 work/dbtriage/tokenize_corpus.py tools/agx-isa /tmp/resync.json --resync

# the A/B variants (isolated trees; the live tree is never touched)
bash experiments/EXP-0212-db-defect-application/analysis/mkvariant.sh a   --only a_notes
bash experiments/EXP-0212-db-defect-application/analysis/mkvariant.sh ab  --only a_notes,b_spans
bash experiments/EXP-0212-db-defect-application/analysis/mkvariant.sh abd --only a_notes,b_spans,d_match
bash experiments/EXP-0212-db-defect-application/analysis/mkvariant.sh d   --only d_match
```

`work/var_L1` and `work/var_L2` carry the two **refused length candidates** with their
measured corpus numbers, so the next agent starts from the measurement rather than
re-deriving it.

## Isolation from the in-flight wave

`EXP-0213-quiet-confirmation-2/CAPTURE_CONTRACT.json` pins `pinned/db.json` at
`2412eac1cad4449eb385702062abd03e5c926d04f7d384e6bf3684c9c4c7c6c4`. That hash is
`EXP-0204-.../pinned/db.json` **and** `EXP-0206-.../pinned/db.json` — both frozen per-experiment
copies, both verified by `shasum` during this work — **not** `tools/agx-isa/db.json`. The
sibling also declares `tools/agx-isa/**` under `writes.forbidden`. So the running
confirmation reads a frozen copy and this application cannot disturb it, in either direction.

## Clean-room provenance

```text
Clean-room provenance: PUBLIC (this repository's own committed artifacts only)
Inputs inspected:      tools/agx-isa/{db,validation}.json, tools/agx-isa/PENDING_DB_DEFECTS.md,
                       the analysis/ and raw/ trees of EXP-0199..EXP-0207 (all produced from
                       MSL we authored, compiled at runtime and dispatched on our own G17P),
                       experiments/EXP-M4-13-full-corpus/hex (our own compiled shaders)
Apple binary introspection: NONE. No disassembly, no decompilation, no Apple binary opened.
                       No device was contacted; no shader was compiled.
Reproduction:          see "Exact reproduction" above
Evidence:              raw/db.json.BEFORE, raw/validation.json.BEFORE, raw/db_sha_before.txt,
                       raw/db_sha_after.txt, raw/corpus_{strict,resync}_{BEFORE,AFTER}.json,
                       raw/roundtrip_AFTER.txt, raw/validate_labels_AFTER.txt,
                       analysis/evidence_check.txt, work/var_*/
```
