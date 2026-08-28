# EXP-0103 progress log

- 2026-08-27T23:0x — dir scaffolded; read CLAUDE.md/CODEX.md/SUBAGENT_BRIEF.md;
  reviewed prior EXP-0074/0026/0047 for reuse; read Part II FP-*/TRIG-*/SFU-* exact
  wording from `APPLE9_RE_IMPLEMENTATION_GAPS.md`.
- host oracle `analysis/exact_ref.py` written; self-test green.
- MSL API discovery: `fast::`/`precise::` namespaces have no `recip()`; reciprocal is
  `divide(1.0, x)`. All 45 kernel functions in `kernels/probe.metal` smoke-compiled
  and dispatched once each (tiny scratch inputs) — all succeeded.
- CLEAN-ROOM PROCESS SLIP (self-corrected): several throwaway scratch files were
  briefly written to `/tmp` during the MSL API discovery / harness smoke-testing
  above, before noticing the tightened `SUBAGENT_BRIEF.md` rule ("do NOT write to
  /tmp ... not even briefly"). All deleted immediately on discovery; none contained
  Apple-authored or sensitive content (our own MSL/JSON scratch only). Disclosed per
  the brief's own precedent (EXP-0098, EXP-0109).
- Host-oracle performance bug found and fixed: Machin's-formula π bracket denominator
  blow-up made sin/cos reference calls take up to ~4 s each (root cause: repeated
  squaring of a bracket inheriting an irregular, thousands-of-bits denominator from
  combining base-5/base-239 rational series). Fixed via `_snap_out` (round every
  bracket to a clean power-of-2 denominator immediately after it is produced, before
  any caller can repeatedly multiply it). Second bug: `exp2` of a huge finite input
  (e.g. `x=2**127`) attempted `Fraction(2)**huge` — uncomputable, not just slow. Fixed
  with an explicit early-exit overflow/underflow classification in `ref_exp2` before
  building any bracket. Verified: self-test green; ~4.0s -> ~0.02s per call on the
  reproducer; zero mismatches over a ~7000-sample cross-check against `math.*`
  (sanity-check only, never the reference itself).
- `analysis/gen_all.py` run successfully: 47 cases, 449346 total records, 245139
  unique reference entries, 153.5s wall time. Finite-resource mandate applied: FP16
  `rcp`/`rsqrt`/`sqrt` (fast+precise, 6 cases) are EXHAUSTIVE over all 65536 bit
  patterns.
- `verify.py` written (state machine, `--selftest`, `--seqtest`, `--preflight`,
  `--between-runs`, `--captured`); `--selftest` and `--seqtest` both green after one
  bug fix (`run_dir_complete` needed to catch `exact_keys`'s `AssertionError` instead
  of letting it propagate).
- `run.py` written (gated capture runner). `CAPTURE_CONTRACT.json` frozen (git
  revision `2858c20f6703e307afa84436f8d38d1fdd2a35cc`, all authored-file hashes,
  corpus_manifest/references hashes). `PRE_REGISTRATION.md` written: all 31 items
  enumerated with exact wording and disposition (20 HW / 8 PARTIAL / 3 DEFERRED).
  `python3 verify.py --preflight` green against the frozen contract.
- State: **PRE_GPU**. Next milestone: run01 capture.
- run01 (m4-20260828-run01) and run02 (m4-20260828-run02) both captured: 47/47 cases
  OK, zero faults, zero timeouts. `verify.py --between-runs`/`--captured`: 47/47 cases
  byte-identical between runs (after fixing a `captured()` gate bug -- see
  `CAPTURE_CONTRACT.json`'s `post_freeze_verifier_fix_note` -- it originally hard-failed
  on git-revision drift between runs, exactly the false-positive class
  `SUBAGENT_BRIEF.md` warns about; fixed to check authored-file hashes instead).
- `analysis/score.py` written and run: full scoring against `references.json`.
  HIGH VALUE result confirmed: precise `rcp`/`rsqrt`/`sqrt` FP32 mismatches are 100%
  explained by the EXP-0074 DAZ+FTZ model (30/30, 77/77, 77/77 -- zero unexplained,
  zero normal-range residual error). `exp2`/`log2` are categorically different: fast
  and precise are BYTE-IDENTICAL (both numerically and in compiled AGX bytes -- no
  refined path exists at all), bounded ~1-2 ULP always, but subnormal INPUTS still
  read as zero (DAZ without an FTZ story, since there was never a correctly-rounded
  result to flush). FP16 rcp/rsqrt/sqrt (fast+precise): the full 65536-pattern
  exhaustive sweep shows ZERO mismatches -- FP16 preserves subnormal inputs AND
  outputs exactly (no DAZ, no FTZ), a clean contrast with FP32.
- Supplementary (non-contracted) findings surfaced by the scoring pass, each followed
  up: fast::sin/cos return exactly 0 (not NaN) for every NaN/Inf input and for every
  |x| at/above a cliff bracketed by a follow-up 501-point dense sweep to
  (6587824.0, 6588825.0]; precise::sin/cos do NOT have this cliff -- they stay
  ~1-2 ULP accurate even at FLT_MAX. `saturate()` flushes small positive subnormal
  inputs to +0 (composes fmax/fmin, which apparently DAZ on the ALU path too).
  FP32 relational comparisons DAZ (two differently-valued subnormals compare equal).
  `round()` loses the sign of `-0`. Native `float->int`/`int8` truncating conversion
  ALREADY saturates numeric overflow to the type's min/max (matches an explicit
  `clamp`-then-convert for every non-NaN case) -- strong FP-12 evidence.
- Structural bonus (OWN-SHADER, `tools/shdump` built fresh into `work/`, never
  modified in place): AGX byte-length disassembly comparison, saved to
  `raw/structural_probe/` with a hash manifest and a same-source repeat-determinism
  check (byte-identical). `k_sin_fast_f32`=136B vs `k_sin_precise_f32`=456B (NOT
  byte-identical on M4 -- refines EXP-0026's A18 "byte-identical" claim, which likely
  did not exercise NaN/Inf/huge-|x| control flow). `k_sincos_shared_f32`=198B <
  `k_sincos_independent_f32`=238B (structural evidence of range-reduction sharing,
  TRIG-03/04). `k_f32_to_int8_plain`=80B < `k_f32_to_int8_sat`=92B while their NUMERIC
  outputs agree for every non-NaN case (FP-12: native saturating convert exists;
  explicit clamp only changes the NaN case). `k_exp2_fast_f32`/`k_exp2_precise_f32`
  and `k_log2_*` byte-identical (cross-validates the numeric finding).
- Writing RESULTS.md now. State: RUN02_PRESENT, promotion gates green.
- Post-freeze bug found in the round-family reference (floor/ceil sign handling for
  negative non-integer inputs) while writing up round_family_f32's unexpectedly high
  mismatch count; fixed in `analysis/exact_ref.py`, self-test re-verified, corpus and
  references regenerated deterministically (no corpus/kernel/harness/raw hardware
  data touched), CAPTURE_CONTRACT.json hashes updated with a disclosed note, all four
  gates (`--selftest --seqtest --preflight --captured`) re-verified green.
- RESULTS.md written: TL;DR, OBSERVED-vs-INTERPRETED framing, all 31 item response
  blocks (23 HW / 6 PARTIAL / 2 DEFERRED -- three items upgraded from their
  pre-registered PARTIAL by stronger-than-planned capture-time evidence: FP-12,
  SFU-05, SFU-06), ULP summary table, gates section, limitations, clean-room
  attestation. DONE.
