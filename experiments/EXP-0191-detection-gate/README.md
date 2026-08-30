# EXP-0191 — a detection-power gate on every INERT verdict in the corpus

**Status: COMPLETE. Pure offline analysis — no device, no GPU, no SSH.** The A18 Pro was
down for the whole run.

## The question

`EXP-0190` §7 recorded **DEF-0190-1**, the tenth "check that cannot come out the other
way" in this corpus: `audit.py`'s INERT buckets have **no detection-power conjunct**.
`moved` is derived from the hash of each record's `observed`, so **an arm whose observable
never varies returns `moved = 0` BY CONSTRUCTION**, and `classify()` reads that as *"the
field is inert"* rather than *"the instrument could not answer"*. `INERT-MULTI` is not
withheld, so such a field keeps emitter-grade status.

EXP-0190 measured the extent (8 arms with no observation at all; 128 arms — 80,138 field
records — with exactly one distinct `observed` payload; 21 `INERT-*` fields resting
entirely on them) and named the remedy without building it: the `_detect`, `__ladder_L_*`
and `_live_control` records **already in the corpus and discarded by the same underscore
filter**, consumed as a **gate on INERT verdicts** rather than as measurements.

This experiment builds that gate and applies it to **every** `INERT-*` field — all 79, not
just the 21.

> **For any (experiment, arm): did this arm ever demonstrate that its observable can
> move?** An arm passes only if a known-live control in the same arm produced a different
> `observed` payload. An arm whose observable is constant across every case fails, and an
> INERT verdict from it establishes nothing.

## Hypotheses (frozen in `PRE_REGISTRATION.md` before computing)

- **H1** the gate discriminates — it both passes arms with detection power and fails arms
  without it. Refuter: it passes (or fails) everything, in which case it is the eleventh
  cannot-come-out-the-other-way check and must be reported as one.
- **H2** at least one `INERT-*` field rests entirely on failing arms.
- **H3** after the orchestrator's five withholdings, no field currently labelled
  `hardware-run`/`isolated-byte-diff` has an INERT verdict resting on zero passing arms.

## Method

1. Reuse EXP-0190's **corrected indexer output** (`audit.json`) for bucket and
   `arms_tested` structure, and its **hand-written 96-name intent table**
   (`classify_underscore.py`, emitter `file:line` per name) for record classification. No
   third indexer is written.
2. Re-partition those names by **intent** into `CONTROL_LIVE` / `CONTROL_FALSIFIER` /
   `CONTROL_NEG` / `BASELINE` / `SIBLING` (`PRE_REGISTRATION.md` §4). No default bucket —
   an unclassified name aborts the run.
3. One pass over all 725 raw `*.jsonl` (5,200,282 lines), accumulating the distinct valid
   `observed` payloads per role per arm, at two join levels (strict arm key, and carrier).
4. Apply the frozen gate (§6) per arm, then per field; run the four pre-registered
   discrimination checks (§7).

## Commands

```sh
python3 analysis/detection_gate.py        # ~24 s, read-only, writes analysis/*.json
```

## Result

**The gate discriminates — 51 of 83 arms pass, 32 fail, and all 8 no-observation arms
fail — and every current emitter-grade INERT verdict survives it.** 0 fields are
reclassified by the frozen rule; the standing **34 of 166 / 550 of 1040** is unchanged.
Three INERT verdicts fail (all already `untested`), 76 of 79 survive and are thereby
*stronger*. Two side findings are recorded in `RESULTS.md` §4–§5: DEF-0190-1's extent is an
undercount, and `audit.py`'s `moved` counts a **fault** as movement, which carries four
currently emitter-grade STABLE-LIVE rows.

## Clean-room statement

```
Clean-room provenance: derived analysis of already-committed evidence
Inputs inspected: experiments/*/raw/**/*.jsonl (our own append-only capture records),
                  tools/agx-isa/{db,validation}.json, EXP-0190/analysis/*.json
Apple binary introspection: NONE. No shader compiled, no device contacted.
Reproduction: python3 analysis/detection_gate.py
Evidence: analysis/gate_results.json, analysis/reclassify.json
```

## Files

| path | what |
|---|---|
| `PRE_REGISTRATION.md` | frozen rule, role table, validity test, discrimination proof, thresholds |
| `analysis/detection_gate.py` | the gate; re-runnable, read-only over the corpus |
| `analysis/gate_results.json` | per INERT field: arm, pass/fail, controls relied on, record counts; plus the D1–D4 detail and the post-hoc sections |
| `analysis/reclassify.json` | `fields`: empty (frozen rule fired 0 times). `post_hoc_candidates`: 4 STABLE-LIVE rows with `start`/`width`, **not** a verdict of this experiment |
| `RESULTS.md` | observations vs interpretation, limitations, verdict |
| `manifest.json` | input hashes, environment, artifact hashes |
