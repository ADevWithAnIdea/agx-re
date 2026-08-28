# EXP-0126 — M4 UAPI field-by-field mapping (P0.3 / DRV-UAPI-03)

**Question.** For every field in `drm_asahi_cmd_render`, `drm_asahi_cmd_compute`, and
`drm_asahi_queue_create` (65 leaves per `EXP-0045-uapi-field-matrix`), establish:
`userspace derivation -> UAPI value -> kernel/firmware marshaling -> observed Apple9
behavior`. Full task in `PRE_REGISTRATION.md`; full result in `RESULTS.md`.

**Numbering note.** `experiments/EXP-0126-m4-lifecycle-boundary-probe/` also exists under
the `EXP-0126` number (concurrent orchestrator activity, observed mid-session). This
experiment kept the exact dispatched path.

## Method

1. **Synthesis** across all 65 leaves: `asahi_drm.h` doc comments (exact file:line) +
   this repository's own prior M4/A18 experiments + the pinned MIT-licensed Mesa reference
   driver (`mesa/src/asahi/**`, read-only PUBLIC shape reference per `CLAUDE.md` — never
   edited, never a source of Apple9-specific numeric claims).
2. **Two new M4 hardware probes** (pre-registered, two independent captures, all five
   standing gates green): an exhaustive sample-position grid/rounding/boundary probe
   (`harness/sampos126.m`, DATA-TRACE via the unmodified `tools/iotrace` interposer) and a
   `render.samples` valid-range boundary probe (`harness/sampcount.m`, public-Metal
   HW-PROBE).

## Result

7/65 leaves MAPPED, 58/65 PARTIAL, 0/65 UNDETERMINABLE-FROM-USERSPACE (the one genuinely
undeterminable item, `command_timestamp_frequency_hz`, is outside the 65-leaf matrix — see
`RESULTS.md`). Settles how the captured sample-position BO relates to
`render.ppp_multisamplectl` (it doesn't — the field *is* the packed value, no extra submit
parameter), and boundary-tests `render.samples`'s documented `{1,2,4}` constraint both ways.
Full table, evidence, and gate results in `RESULTS.md`.

## Reproduce

```sh
cd harness
python3 run.py --run <new_id> --out raw/<new_id>     # builds + runs the 59-case matrix
python3 verify.py --selftest
python3 verify.py --seqtest
python3 verify.py --captured --run01 m4_20260828_run01 --run02 m4_20260828_run02
```

## Layout

```
PRE_REGISTRATION.md    hypotheses, method, confounders, safety, schema
CAPTURE_CONTRACT.json  frozen source hashes, matrix, gates, run ids
RESULTS.md             the full field table + new hardware evidence + gate results
PROGRESS.md            milestone log
harness/               sampos126.m, sampcount.m (frozen probes); sampcov.m (superseded,
                        kept as process history — see PRE_REGISTRATION.md); casematrix.py,
                        hexparse.py, run.py, verify.py
fixtures/               recorded_reality.json — 10 real M4 records used by --selftest
raw/                    m4_20260828_run01/, m4_20260828_run02/ — records.jsonl + hex/
work/                   build artifacts, smoke-gate JSON, pilot logs (non-evidence)
```

## Clean-room

DATA-TRACE (`tools/iotrace`, read-only) + HW-PROBE (public Metal API) + OWN-SHADER (inline
MSL) + PUBLIC (pinned Mesa/`asahi_drm.h`, MIT-licensed). No Apple binary introspected. Full
attestation in `RESULTS.md`.
