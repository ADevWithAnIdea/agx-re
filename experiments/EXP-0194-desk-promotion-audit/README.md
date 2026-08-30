# EXP-0194 — can any blocked field be promoted to emitter grade WITHOUT device time?

**Pure desk analysis. No device work, no SSH, no GPU, no compilation, no Apple binary of
any kind was read.** Every input is already committed in this repository.

```
Clean-room provenance: re-analysis of our own committed capture records
Inputs inspected:      tools/agx-isa/{db,validation}.json
                       experiments/*/raw/**/*.jsonl        (our own append-only records)
                       experiments/*/analysis/field_verdicts*.json
                       experiments/*/RESULTS.md, PROGRESS.md, PRE_REGISTRATION.md
Apple binary introspection: NONE.
Target hardware:       OFFLINE and unreachable for the whole of this experiment.
Nothing outside experiments/EXP-0194-desk-promotion-audit/ was created or modified.
```

## Question

The headline is **32 of 166 emitter-relevant instructions emittable, 543 of 1040 fields at
emitter grade**. `docs/isa/emit-worklist.md` records the 134 blocked instructions as blocked
by **566 field-labels**: 260 `untested`, 141 `corpus-correlation`, 135 `tokenization-only`,
30 `single-template-inference`. (`analysis/scan_raw.py`'s companion enumeration reproduces
those four counts exactly from `db.json` + `validation.json`.)

`isolated-byte-diff` does not inherently need new hardware time. Its definition
(`docs/evidence-classification.md` §2) is:

> Changing exactly this field in code compiled from our own MSL produced an isolated,
> reproducible byte change, **and** the resulting program ran with the predicted effect at
> one or more points — but the field's range was not swept.

Both halves are *historical facts about data already captured*. So: **for how many of the
566 does the committed raw already contain both halves, such that the promotion could be
derived at the desk?**

## Method

1. Read the bar: `docs/evidence-classification.md` §2–§3, `experiments/FIELD-SWEEP-PROTOCOL.md`
   §3 and §5 (the disqualifiers), and `tools/agx-isa/validate_labels.py` (how citations resolve).
2. `analysis/scan_raw.py` — index every per-case record in all 727 `experiments/**/raw/**.jsonl`
   (5 201 306 lines, 1 028 378 field-tagged records, 9 119 carrier groups).
3. `analysis/extract_candidates.py` — pull the 263 687 records that touch one of the 566
   blocked rows.
4. `analysis/adjudicate2.py` — run each row through an eight-gate chain (below). Every gate
   can return NO.
5. `analysis/control.py` — **positive control**: run the identical chain over the 543 fields
   already at emitter grade, to prove the chain is not simply refusing everything.
6. `analysis/verdict_crosscheck.py` — independent second method: does some experiment's own
   committed `analysis/field_verdicts*.json` already carry an emitter-grade verdict for a row
   `validation.json` now shows blocked?
7. `analysis/verify_survivor.py` — re-derive the one surviving claim directly from the raw
   files, bypassing every intermediate this experiment produced.

### The gate chain

| gate | demands | why it can say NO |
|---|---|---|
| **G1** | ≥2 clean **executed** cases in one carrier group | faults, hangs, victims, `no_draw`, `undecodable`, tripped sentinels and poisoned buffers are not observations of the field (protocol §3d, §7) |
| **G2** | ≥2 distinct **encoded** field values, read out of `bytes` at `db.json` geometry | not the harness's nominal `value` |
| **G2b** | the value→bytes map is **injective** | DEF-0166-1: an assembler that cannot clear a `match`-pinned bit aliases several nominal values onto one program, and the harness's oracle then describes a program that never ran |
| **G3** | all bytes identical **outside** the field's bit range, same length | isolation |
| **G4** | ≥2 distinct observed payloads, after stripping `gputime_ns`/timestamps | a field whose observable never varies is not evidence; timing jitter is not movement |
| **G5** | each encoded value yields exactly one payload | otherwise G4's movement is noise |
| **G7** | two **matching** cases at **different** encoded values carrying **different** oracles | this is the "ran with the predicted effect" clause. A constant oracle predicts the *instruction's* effect while the field varies; agreeing with it is an inertness observation, not a predicted effect |
| **G8** | the value→payload map **reproduces across ≥2 raw run directories** | a one-run view cannot see instability |

`analysis/adjudicate.py` (deleted; superseded) was a first pass with only G1–G5 and a weaker
G7. It returned five candidates. **All five were wrong**, and each was wrong in a way the
brief warned about — see RESULTS §4. The three holes it had are now gates G2b, G7 and G8.
