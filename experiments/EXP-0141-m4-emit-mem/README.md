# EXP-0141 — M4 memory / atomic / fence family: emission, not decoding

**Target:** local Apple M4 / G16G (`Mac16,10`, macOS 26.6.2 / 25G82). A18 Pro
hands-off; M5 out of scope. Every claim here is an M4 claim.

## Question

`docs/evidence-classification.md` / DOC-02: **58 of the 81 fields** of the ten
memory/atomic/fence instructions — `atomic_mem`, `atomic_rmw`, `atomic_tg`,
`dev_scoreboard_fence`, `device_load`, `device_store`, `mem_fence`,
`mem_fence8`, `tg_addr_compute`, `threadgroup_barrier` — are below emitter
grade. The family gates every load, store and atomic a compiler emits.

The named blocker is **`device_load.dst_lo` / `dst_ext9`**, which
`work/DOC-02-LABELLING-REPORT.md` calls *the largest single synthesis blocker in
the ISA*: `EXP-0112`'s generator produces 100 correct random DAGs only by
copying those two fields **verbatim** from a compiled shader.

## Method

Two case kinds, both HW-PROBE on the local M4:

* **synthesis** — a complete hand-assembled AGX program (`tools/agx-isa`
  `isadb.assemble()` only, never a captured byte string) spliced over
  `kernels/carrier.metal`'s compiled `_agc.main[0:170]`, for `device_load`,
  `device_store` and a synthesised `dev_scoreboard_fence`;
* **in-place splice** — a single-byte mutation at a located instruction inside
  one of our own compiled MSL carriers, for `atomic_mem`, `atomic_rmw`,
  `atomic_tg`, `threadgroup_barrier`, `mem_fence` and `tg_addr_compute`.

Every field of width <= 8 is swept **densely over all 2^w values**; the
`dst_lo` x `dst_ext9` pair is swept over its **full 512-value product**, at four
independent target registers. Oracles are host-computed in `carriers.py` from
the MSL we wrote and are checked against the unspliced carriers before any
mutation. Six falsifiers are pre-registered to FAIL.

## Reproduction

```sh
python3 -B verify.py --selftest --preflight
python3 -B run.py --run-id m4-20260828-run11 --execute     # main matrix
python3 -B run.py --run-id m4-20260828-run12 --execute     # independent repeat
python3 -B run.py --run-id m4-20260828-run21 --execute     # atomic_rmw addendum
python3 -B run.py --run-id m4-20260828-run22 --execute
python3 -B verify.py --captured
python3 -B analysis/summarize.py
python3 -B analysis/verdicts.py
```

## Layout

| path | role |
|---|---|
| `PRE_REGISTRATION.md` | frozen hypotheses, oracles, falsifiers, confounders + AMENDMENTS 1 and 2 |
| `CAPTURE_CONTRACT.json` | frozen authored-blob hashes, raw schema, timeouts, hang budget |
| `kernels/*.metal` | our own MSL carriers |
| `isa_helpers.py` | instruction builders (all through `isadb.assemble`) |
| `carriers.py` | carrier table + host-computed oracles + integrity sentinels |
| `sweepdefs.py` | the whole frozen case matrix |
| `harness/locate.py` | re-derives every splice site by disassembly; asserts, never assumes |
| `harness/sweeprun.py` | the executor (robustness machinery lives here) |
| `verify.py` | selftest / preflight / between-runs / captured gates |
| `raw/m4-20260828-run11,run12` | main capture pair (append-only) |
| `raw/m4-20260828-run21,run22` | `atomic_rmw` addendum capture pair |
| `raw/m4-20260828-run01` | RETAINED partial capture, superseded, see its `PARTIAL.md` |
| `analysis/` | `summarize.py`, `verdicts.py`, `summary.json`, `field_verdicts.json` |

## Clean-room provenance

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected: our own MSL (kernels/*.metal), our own hand-assembled AGX
  programs (tools/agx-isa isadb.assemble), our own compiled shader bytes
Apple binary introspection: NONE
Reproduction: see above
Evidence: raw/<run_id>/sweep.jsonl (append-only), raw/<run_id>/00_manifest.json,
  raw/<run_id>/01_progress.json
```
