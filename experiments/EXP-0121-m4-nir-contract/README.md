# EXP-0121 — M4 NIR-contract closure (OPT-01, 03, 04, 05, 06, 07, 08, 10, 11)

**Question.** `APPLE9_RE_IMPLEMENTATION_GAPS.md` Part II "P0 — Questions that gate the
initial NIR contract" lists eleven items. OPT-02 (precise FP32 division correctness) and
OPT-09 (discard/demote semantics) are already answered (EXP-0074, EXP-0091). This
experiment answers the remaining nine: does preserving `fdiv` select two observably
distinct hardware sequences (OPT-01); does `pow` need a fixup beyond
`exp2(y*log2(x))` (OPT-03); is dynamic-exponent `ldexp` a single decoded instruction
(OPT-04); does one instruction fuse compare+select over arbitrary register values
(OPT-05), across FP32/I32(signed)/U32 and every NIR condition (OPT-06); can a
varying/input be read (OPT-07) or a varying/output written (OPT-08) with a
dynamically-selected slot; and does an ordinary aligned load (OPT-10) / store (OPT-11)
satisfy atomic-load/store ordering under fences.

**Method.** OWN-SHADER MSL kernels compiled by the public Metal runtime, dispatched on
real M4 hardware via the read-only `tools/shdump`/`tools/agxtest` pipeline, with
runtime (buffer-sourced, non-compile-time-foldable) operand corpora compared against an
independently written host oracle (`harness/oracle.py`). Structural decoding via
`tools/agx-isa`'s tokenizer (read-only) on the exact compiled bytes. OPT-10/11 use a
cross-threadgroup message-passing litmus test (pattern from EXP-0093, freshly authored
here) crossing {atomic, plain} access method × {fenced, unfenced} × `PAIRS`∈{1,4,8,16}.
No novel instruction encodings are hand-assembled from `db.json` field tables (see
`PRE_REGISTRATION.md`'s explicit scope limit, given `docs/isa/register-move-and-liveness.md`'s
documented hand-splicing hazards on this ISA).

**Target:** local Apple M4 / G16G only. No A18 Pro claim anywhere in this document.

**Clean-room category:** OWN-SHADER + HW-PROBE (+ PUBLIC for the C99/IEEE-754 semantics
used only to write the host oracle). No Apple binary was disassembled, decompiled, or
otherwise introspected. `tools/*` used read-only; `harness/fsrun.m` is copied unchanged
from `experiments/EXP-0111-m4-fragment-semantics/harness/fsrun.m` (our own prior
committed code).

**Two-run gate: MET.** `raw/m4-20260828T000000Z-run01` and `raw/m4-20260828T000100Z-run02`,
94/94 cases `status=OK` in both. `verify.py --compare` reports all `GATED_FIELDS`
identical after one documented, narrow coarsening for concurrency verdicts (see
`verify.py::_normalize_gated` and RESULTS.md's Gates section).

See `RESULTS.md` for the full per-item findings, `PRE_REGISTRATION.md` for the frozen
hypotheses, and `CAPTURE_CONTRACT.json` for the pinned revision/source hashes/schema.

## Layout

- `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json` — frozen before capture.
- `kernels/*.metal` — authored MSL, one file per OPT item (or item pair).
- `harness/` — `oracle.py` (host reference), `casematrix.py` (94 frozen cases),
  `case_exec.py` (per-case executor), `build.sh`, `fsrun.m`.
- `run.py`, `verify.py` — capture orchestrator and the five standing gates.
- `raw/<run-id>/` — `01_results.jsonl` (GATED), `01_detail.jsonl` (non-gated, incl.
  concurrency per-lane counts and full observed arrays), `01_timing.jsonl`,
  `00_env.json`, `02_dispatch.json`.
- `analysis/analyze.py` — structural + functional analysis over a captured run;
  `analysis/report_<run>.json` is its output.
- `work/` — scratch (tool binaries, pilot/diagnostic probes referenced as
  supplementary evidence in RESULTS.md, never part of the gated two-run contract).
- `PROGRESS.md` — milestone log.

## Reproduce

```sh
python3 -B verify.py --selftest
python3 -B run.py --run-id m4-<UTC>-run01
python3 -B run.py --run-id m4-<UTC>-run02 --between-runs
python3 -B verify.py --compare m4-<UTC>-run01 m4-<UTC>-run02
python3 -B analysis/analyze.py m4-<UTC>-run01
```
