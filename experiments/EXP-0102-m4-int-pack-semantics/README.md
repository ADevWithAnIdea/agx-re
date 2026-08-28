# EXP-0102: M4 integer / pack-conversion compiler-contract semantics (INT-*/PACK-*)

- **Date:** 2026-08-28
- **Clean-room category:** OWN-SHADER + HW-PROBE (+ PUBLIC for NIR/GLSL/Metal-Shading-Language-
  Specification/IEEE754 op *definitions* used only to write the host oracle)
- **Phase / question:** Part II compiler questionnaire — the 14 `INT-*` and 11 `PACK-*` items in
  `APPLE9_RE_IMPLEMENTATION_GAPS.md`: exact integer semantics (bitfield extract/insert boundaries,
  rotate mod-32, IMAD wrap, CLZ/find-MSB, integer logic-LUT, 64-bit carry-generate) and pack/
  unpack conversion semantics (half/snorm/unorm/4x8 pack families, packed FP16 lane independence,
  packed-int16 absence).
- **Device:** Apple M4 / G16G, local host, macOS 26.6.2 (25G82), Metal 4 / Apple9. A18 Pro
  hands-off per standing directive; nothing here is A18-validated.

## Method

51 authored MSL kernel functions (`kernels/*.metal`), each compiled fresh via `tools/shdump`
(READ-ONLY) and dispatched via `tools/agxtest/agxtest.py`+`agxrun` (READ-ONLY), with bit-exact
readback compared against a from-scratch Python host oracle (`analysis/oracle.py`, computed from
NIR/GLSL/Metal-Shading-Language-Specification/IEEE754 definitions, exact `fractions.Fraction`
arithmetic where rounding correctness matters — never from a GPU result). Structural claims
(single-instruction vs. multi-instruction, op-family membership) are answered by tokenizing the
SAME already-captured `_agc.main` bytes with the READ-ONLY `tools/agx-isa` disassembler
(`analysis/structural.py`) — no additional hardware contact for those.

Two independently captured, gated runs (`raw/m4-20260828T063920Z-run01`,
`raw/m4-20260828T063935Z-run02`), 51/51 cases `status=OK` in both, **51/51 GATED records
byte-identical** across runs (`verify.py --captured --compare`). Five standing gates implemented
in `verify.py`: `--selftest` (pure-Python, hand-worked vectors), `--seqtest`
(`PRE_GPU`/`RUN01_PRESENT`/`RUN02_PRESENT` state check), a NON-RECORDED smoke gate before each run,
no nondeterministic field in the gated JSONL, and fixtures drawn only from elementary arithmetic
(never a hand-typed "known good" hardware byte fixture).

## Procedure (re-runnable)

```sh
cd experiments/EXP-0102-m4-int-pack-semantics
python3 -B kernels/gen_kernels.py            # (re)generate kernels/*.metal
python3 -B verify.py --selftest              # pure-Python gate, no GPU
python3 -B verify.py --seqtest
python3 -B run.py --run-id m4-<UTC>-run01 --repo ../..
python3 -B run.py --run-id m4-<UTC>-run02 --repo ../.. --between-runs
python3 -B verify.py --captured --compare raw/<run01> raw/<run02>
python3 -B analysis/structural.py --run raw/<run01> --repo ../..
```

## Raw results

- `raw/m4-20260828T063920Z-run01/`, `raw/m4-20260828T063935Z-run02/` — promoted, byte-identical,
  two-run gated capture (`01_results.jsonl` GATED, `01_timing.jsonl` non-gated, `00_env.json`,
  `02_dispatch.json`, `full/*.json` for the two 65536-element exhaustive cases and every
  `--dump-main` sidecar over 64 bytes).
- `raw/m4-20260828T063741Z-run01/` — **QUARANTINED** (see its `QUARANTINE.md`): an earlier capture
  whose harness accidentally wrote scratch binary archives under `raw/`, violating the text/JSON-
  only rule. The recorded DATA in it is intact and was never wrong; it is superseded because of
  where its scratch files landed, not because of a data defect. Retained, never reused, never
  cited as closure evidence.
- `analysis/structural_report.json` — full per-item tokenization detail behind the OBSERVED
  section of `RESULTS.md`.

## Analysis / established facts

See `RESULTS.md` for the full write-up: OBSERVED/INTERPRETED sections, a finite-resource table,
and a required-format response block for all 25 items (14 `INT-*`, 11 `PACK-*`). Headline
findings:

1. **`extract_bits`/`insert_bits` have a genuine three-way boundary contract** the project's prior
   docs did not capture: `cnt==0`→no-op, `cnt==32` EXACTLY→offset bypassed entirely (verbatim
   passthrough, even for enormous offsets), otherwise `off` is applied as a LITERAL (unmasked)
   shift — not NIR's presumed "mask offset mod 32, clamp width" contract. Established at the
   Metal-compiler-output tier (122/256-row boundary sweeps, 100% model fit); whether the raw
   `ibfe`/`ibfins` instruction alone (vs. compiler-added helper instructions) implements the
   `cnt==32` bypass is flagged open (see RESULTS.md INT-02/INT-11).
2. **Rotate**: immediate rotate is a single 12-byte `irotate` op with compile-time mod-32 folding
   (byte-identical bodies for K=0/32/64 and for K=33/1); runtime-amount rotate is a genuine
   10-instruction expansion — no one-instruction dynamic form exists.
3. **Integer logic-LUT**: a real `ilogic` instruction with a field-confirmed multi-value selector
   covers 10 of the 16 canonical 2-input Boolean functions; the other 6 (projections, negations,
   degenerate constants) route through different mnemonics in this compiler's output.
4. **Pack/unpack**: `pack_half_2x16`/`pack_snorm_2x16`/`pack_unorm_2x16` are all native
   single/dual-instruction conversions (no generic bitfield lowering); `pack_unorm2x16`'s rounding
   is confirmed round-to-nearest-even at the one true exact tie (after fixing a float64-vs-exact-
   Fraction methodology bug found during the pilot, see `PROGRESS.md`); `unpack_{snorm,unorm}2x16`
   are validated **exhaustively** over all 65536 possible 16-bit lane patterns; normalized 4x8
   pack/unpack are native (2-op), a hand-written GENERIC (non-normalized) 4x8 integer pack is NOT.
5. **Packed FP16 lane independence** (`half2` add/mul/fma) confirmed against a from-scratch,
   genuinely-fused, exactly-rounded binary16 reference across NaN/Inf/subnormal/signed-zero
   exceptional values in either lane; packed `short2` integer ALU confirmed absent for add/mul/and.

Deliverables: `analysis/oracle.py` (host oracle), `analysis/casematrix.py` (51 cases),
`analysis/structural.py` + `analysis/structural_report.json` (tokenized structural facts),
`kernels/gen_kernels.py` + `kernels/*.metal` (24 files, 51 kernel functions), `harness/build.sh` +
`harness/case_exec.py`, `verify.py` (5 gates), `run.py` (capture orchestrator),
`PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json`, `authored_hashes.json`, `PROGRESS.md`,
`RESULTS.md`.

## Items deferred / partial (not silently dropped — full detail in `RESULTS.md`)

- **INT-08** (IMAD full 96-register range): best-effort only; the register-pressure probe never
  forced allocation past r0–26 (compiler restructured the reduction as a multiply-add tree).
- **INT-09** (find-MSB primitive): answered by derivation (`31-clz`) + structural re-confirmation
  of the EXP-0033 decomposition, not by direct splice-isolation of the primitive's own output.
- **INT-12** (full 16-function LUT): closed for 10/16 functions with field-level confirmation; the
  other 6 were never observed routing through `ilogic` in this compiler's output.
- **INT-14** (self-contained carry-generate): deferred by design — `carry_gen`'s operand-field
  layout is not yet characterized well enough to safely splice an independent source without
  risking a silent-zero misread (per the project's standing hardware-behavior warning).
- **INT-02/INT-11 raw-instruction tier**: found post-freeze during analysis — the boundary
  behavior is established at the "what Metal's compiler emits" tier, not independently isolated to
  a bare `ibfe`/`ibfins` instruction without its surrounding compiler-generated helper code.

## Two disclosed, self-caught process issues (both fixed pre-promotion)

1. An initial capture wrote scratch Metal binary archives under `raw/<run>/work/`, violating the
   text/JSON-only rule for `raw/` — caught immediately, that run directory quarantined (its
   `QUARANTINE.md`), harness fixed, fresh official runs captured clean.
2. `verify.py`'s smoke gate initially used `tempfile.TemporaryDirectory()`, which resolves outside
   the repo on this host — caught immediately after `SUBAGENT_BRIEF.md` was updated mid-session to
   explicitly forbid any out-of-repo write, fixed to use an in-experiment `work/smoke/` directory.
   No gated evidence was affected (the smoke gate is non-recorded); no recapture was needed.

Full timestamped detail for both: `PROGRESS.md`.

## Clean-room status

Clean. Only our own MSL was compiled; only our own compiled bytes were dispatched, read back, or
tokenized (via the READ-ONLY `tools/agx-isa` disassembler). No Apple binary was disassembled,
decompiled, or otherwise introspected. `tools/shdump`, `tools/agxtest`, `tools/agx-isa` were used
read-only and not modified. Nothing outside this experiment directory was written to (see the
second disclosed issue above for the one close call, self-caught and fixed). Nothing was
committed; no `docs/`, `PROVENANCE.md`, or `docs/P0-P1-CLOSURE.md` file was touched.
