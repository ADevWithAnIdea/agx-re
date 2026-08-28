# EXP-0105 — M4 encoding/registers (Part II ENC-* cluster)

## Question

`APPLE9_RE_IMPLEMENTATION_GAPS.md` Part II, "Register files, immediates,
and instruction encoding" (ENC-01..ENC-16) — see `PRE_REGISTRATION.md` §1
for the full per-item plan. **Top priority**: EXP-0099 refuted both
candidate models of `falu2`'s packed register field (our own db.json
7-bit-index reading, and an external engineer's retention-flag reading),
leaving the top bit HW-tested INERT and registers 64-95 with NO validated
addressing path in that instruction family, despite EXP-0092's
re-confirmed 96-GPR physical boundary. This experiment's central task:
determine empirically how a source operand addresses r64-r95 (or prove it
cannot) via a downstream-consumer-readback design, exactly as EXP-0099
did.

## Hypothesis

See `PRE_REGISTRATION.md` §2 (H1: does `falu2i`'s `srcA_reg` field — the
sibling of `falu2`'s already-refuted field, itself never independently
tested by EXP-0099 — genuinely address r64-95, or alias to its low 6
bits?) and §2 (H2: does any OTHER field, inspired by `get_sr`'s own
HW-VALIDATED separate register-extension mechanism, act as a bank
selector unlocking r64-95 addressing?).

## Method

Hand-assembled AGX programs (`tools/agx-isa` `isadb.assemble()`), spliced
over a compiled carrier kernel's `_agc.main` region (`tools/agxtest`),
executed on real M4 hardware, compared to an independently computed
oracle. See `casematrix.py` for the full case matrix and its extensive
design-rationale docstring (including why this experiment is
`falu2`/`falu2i`-only, not the originally-planned second, structurally
different family — a disclosed pilot-phase negative finding, see
`PROGRESS.md` Milestone 2).

## Commands

```
python3 -B verify.py --selftest      # no GPU, every tree state
python3 -B verify.py --seqtest       # no GPU, state-machine gate
python3 -B baseline.py               # re-derive CARRIER_LEN fresh (no GPU dispatch)
python3 -B verify.py --preflight     # before run01
python3 -B run.py --execute --run-id m4-20260827-run01
python3 -B verify.py --between-runs  # before run02
python3 -B run.py --execute --run-id m4-20260827-run02
python3 -B verify.py --captured
python3 -B analysis.py --write
python3 -B make_manifest.py --write
```

## Clean-room category

`OWN-SHADER + HW-PROBE + PUBLIC`. Every executed instruction byte is
either our own hand-assembled sequence via `tools/agx-isa`'s own
`isadb.assemble()`, or the compiled form of our own carrier MSL
(`tools/shdump`). `EXP-0092`'s `get_sr`/`device_store` `index_reg`
round-trip finding is cited as prior, already-committed repository
evidence (PUBLIC-to-this-experiment) wherever referenced, never
re-introspected from any Apple binary. No Apple binary, framework, kext,
or firmware inspected. See `RESULTS.md` for the full attestation.

## Layout

- `PRE_REGISTRATION.md` — frozen hypothesis, falsifiers, per-ENC-item plan.
- `CAPTURE_CONTRACT.json` — machine-readable capture contract.
- `isa_helpers.py` — instruction builders (falu2/falu2i/mov_imm/
  device_store/stop), adapted from EXP-0099's own proven helpers.
- `casematrix.py` — the 16-case matrix + extensive design rationale,
  including the abandoned-`iminmax` disclosure.
- `harness/` — `build.sh` (compiles `tools/shdump`+`tools/agxtest`),
  `case_exec.py` (per-case executor), `recorded_fixture_case0.json` (a
  REAL hardware record used by `verify.py --selftest`).
- `kernels/carrier.metal` — byte-identical to EXP-0099's own proven-good
  carrier (splice target only; its own arithmetic never executes).
- `run.py` / `verify.py` / `analysis.py` / `make_manifest.py` /
  `baseline.py` — capture/gate/analysis machinery, adapted from
  EXP-0099's own.
- `PROGRESS.md` — milestone log, including the full `iminmax` pilot
  post-mortem.
- `raw/` — the two gated captures (append-only).
- `RESULTS.md` — observations, per-ENC-item response blocks, proposed
  `db.json` corrections, gate results, clean-room attestation.
