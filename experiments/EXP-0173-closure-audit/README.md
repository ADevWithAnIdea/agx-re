# EXP-0173 — The acceptance-gate audit

## Question

`CLAUDE.md` → *Definition of Done* and `docs/P0-P1-CLOSURE.md` → *Completion gate* both say
closure is decided by a **final audit that positively reproduces the claimed generation paths
and proves that no required field or supported operation depends on captured Apple templates
or on inspection of Apple's implementation.** That audit had never been run. This is it.

The instruction was explicit: **reproduce the claims, do not re-read them**, and report where
the work stands *against the gate* rather than against a field count.

## Hypotheses

Pre-registered in `PRE_REGISTRATION.md` before any verdict was computed (H1–H7). Headline
pre-registration: *0 of 16 rows CLOSED, gate NOT PASSED*.

## Method

Pure analysis over the frozen tree at `2792d7ca` (`CAPTURE_CONTRACT.json` carries the input
hashes). **No device, no SSH, no GPU** — three device experiments (EXP-0168 / EXP-0171 /
EXP-0172) were running concurrently and none of their files was touched.

Six re-runnable analyses in `analysis/`:

| script | output | what it establishes |
|---|---|---|
| `gate_sensitivity.py` | `gate_sensitivity.json` | each tool gate run unmodified, then given a defect it is *claimed* to catch |
| `provenance_audit.py` | `provenance_audit.json` | every `PROVENANCE.md` row: `artifacts_exist` / `claim_reproduced` / `notes`, plus the **reverse** chain |
| `template_dependency.py` | `template_dependency.json` | per instruction: generable from documented rules, or which donor it needs |
| `vacuous_fields.py` | `vacuous_fields.json` | headline recomputed with and without the zero-free-bit fields |
| `operand_sanity.py` | `operand_sanity.json` | every field that cannot do what its name promises |
| `closure_rules.py` | `closure_rules.json` | rule-by-rule verdict per P0/P1 row |
| `compiler_readiness.py` | `compiler_readiness.json` | re-test of the `nir_op_mov` first-blocker claim |

## Commands

```sh
sh experiments/EXP-0173-closure-audit/analysis/run_all.sh
```

Raw transcripts of every gate invocation and every mutation run are appended to
`raw/gate_runs.txt` and `raw/mutation_runs.txt`.

## Constraints honoured

No `git commit`. No edit to `db.json`, `validation.json`, `docs/`, `PROVENANCE.md`, or
`docs/P0-P1-CLOSURE.md`. `tools/agx-isa/match_overlap.json` is rewritten as a side effect of
running `match_overlap_report.py`; the diff was recorded and the file restored with
`git checkout --`.

## Clean-room statement

```
Clean-room provenance: PUBLIC (pure analysis over our own committed artifacts)
Inputs inspected: our own db.json / validation.json / PROVENANCE.md / experiments/**, all authored in this repo
Apple binary introspection: NONE — no Apple binary was opened, read, hashed, or executed
Reproduction: sh experiments/EXP-0173-closure-audit/analysis/run_all.sh
Evidence: experiments/EXP-0173-closure-audit/analysis/*.json + raw/gate_runs.txt + raw/mutation_runs.txt
```
