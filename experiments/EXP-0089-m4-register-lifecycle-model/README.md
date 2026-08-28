# EXP-0089 — M4 register-lifecycle model (successor to EXP-0086)

## Question

`EXP-0086-m4-register-liveness-bits` found that a bit in the same conceptual
role/family as the literal `0x54`/`0x56` "cache/last-use" field corrupts a
later, separate instruction's read of a shared register — refuting the doc
claim that this class of bit is inert — but left five things open: (1) its
own formal two-run gate never closed (run02 died at 113/135 from a host
interruption); (2) the LITERAL bit 17 was never reachable (opcode-determining
in every family it could compile into); (3) the corrupting bit (CAND_B) was
only tested on the simplest kernel, not swept across distance/pressure/
control-flow; (4) its presumed-inert `ctrl`/`ctrl_lo` control field turned out
NOT inert (faulted 4/7 kernels, silently wrong in 3/7) and was never
characterized; (5) no experiment discriminates between competing models of
the mechanism (last-use/discard hint vs. register-cache residency vs. other).
This experiment closes all five.

## Hypothesis

See `PRE_REGISTRATION.md` for the full falsifiable H1-H5 statements, refuters,
and the frozen case matrix (549 cases/run: 168 from the 7 EXP-0086 kernels
carried over verbatim + a new CAND_B sweep + a new `ctrl`/`ctrl_lo` value
sweep, 10 from two NEW literal-bit-17 kernels, 5 from a NEW 3-reader
producer/consumer discriminating kernel).

## Method

1. Carry over EXP-0086's 7 kernels/anchors/oracle verbatim (re-verified
   byte-identical on this session's fresh compile) for the two-run-gate
   completion, the CAND_B distance/pressure/control-flow sweep, and the
   `ctrl`/`ctrl_lo` value sweep.
2. Locate two NEW instruction families (`unpack_convert`, `cvt_i2f`) where
   `tools/agx-isa/db.json`'s own `match` table proves instruction bit 17 is a
   genuinely free field (not opcode-determining, unlike every family EXP-0086
   could reach), and author two new kernels (`lit17_unpack.metal`,
   `lit17_cvt.metal`) where two different MSL builtins/casts on the SAME
   source value defeat CSE and each naturally emit two separate instructions
   reading that shared register with the doc's claimed `0x56`(first)/
   `0x54`(second) polarity.
3. Author a 3-reader kernel (`discrim3.metal`, `v+10/v+20/v+30`) to
   discriminate producer/consumer models: does corruption ever reach a
   reader scheduled BEFORE the flipped instruction (would refute a
   time-forward mechanism entirely), and does it look like it would persist
   to a THIRD, later reader (discard/writeback-skip model) vs. stay localized
   to the immediate next differently-marked consumer (bypass-cache model)?
4. Splice ONE field (or, for `lit17_unpack`'s positive control, one raw byte
   with no named db.json field) via `isadb.decode_one`/`assemble` or a new
   minimal `_splice_raw` primitive, same instruction length, no other byte
   changed; run via `tools/agxtest/agxtest.py` on real M4 hardware in a fresh
   process per case; compare to an independent host-side oracle
   (`casematrix.EXPECTED`, including a from-spec re-implementation of the
   public MSL unorm/snorm unpack formulas).
5. Two full capture runs (549 cases each, 3 repeats per case) with a
   byte-identical-gated-file cross-run gate (authored-hash pinned, NOT live
   `git HEAD` pinned — see `PRE_REGISTRATION.md` §9 and `run.py`'s docstring)
   and a separate non-gated raw timing record.

## Commands

```sh
python3 -B casematrix.py                          # case matrix summary (no GPU)
python3 -B baseline.py --bin-dir <bindir> --out <report.json>   # host-only compile check
python3 -B verify.py --selftest                    # synthetic, no GPU
python3 -B verify.py --seqtest                      # synthetic, no GPU
python3 -B run.py --execute --run-id m4-lifecycle-20260828-run01   # REAL GPU capture
python3 -B run.py --execute --run-id m4-lifecycle-20260828-run02   # REAL GPU capture
python3 -B analysis.py --run-a m4-lifecycle-20260828-run01 --run-b m4-lifecycle-20260828-run02 --write
```

## Clean-room category

**OWN-SHADER** + **HW-PROBE** (+ **PUBLIC** for the unorm/snorm/int-float
conversion oracle formulas, which are documented public Metal Shading
Language builtin semantics, independently re-implemented in Python). Every
byte inspected or spliced is the compiled form of our own MSL
(`kernels/*.metal`), compiled at runtime via `newLibraryWithSource:`
(`tools/shdump`) and decoded/re-assembled with our own `tools/agx-isa`
database. Splices are executed on the real M4 GPU via `tools/agxtest`. No
Apple binary, framework, kext, or firmware is disassembled, decompiled, or
otherwise introspected.

## Files

- `PRE_REGISTRATION.md` / `CAPTURE_CONTRACT.json` — frozen hypothesis,
  variables, matrix, environment (filed before any GPU capture).
- `kernels/*.metal` — 10 authored probe kernels (7 carried over from
  EXP-0086 verbatim, 3 new: `lit17_unpack`, `lit17_cvt`, `discrim3`).
- `casematrix.py` — kernel metadata, frozen anchors, independent oracle,
  case generator (single source of truth for `run.py`/`verify.py`/`analysis.py`).
- `baseline.py` — pre-GPU compile + anchor-freshness check.
- `harness/build.sh` — builds the read-only `tools/shdump`/`tools/agxtest`
  sources into this experiment's private `work/` bin dir.
- `run.py` — the capture runner (device-touching only under `--execute`).
- `verify.py` — fail-closed static + post-capture verifier
  (`--selftest`/`--seqtest`/`--preflight`/`--between-runs`/`--captured`).
- `analysis.py` — cross-run comparison + verdict/determinism summary.
- `make_manifest.py` — whole-tree artifact manifest (PRE_GPU / CAPTURED).
- `RESULTS.md` — observations vs interpretation, verdict on each open item.
- `PROGRESS.md` — timestamped milestones.
