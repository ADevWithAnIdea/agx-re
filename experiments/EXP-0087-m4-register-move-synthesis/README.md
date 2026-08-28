# EXP-0087 -- M4 register-move synthesis (DRV-ISA-01)

**Question.** `tools/agx-isa/db.json` documents FIVE separate opcodes for the
byte0-low-nibble-0xb "compact move" family (`reg_move_c0/c1/c9/cb/c2var`),
discriminated by byte+2, with byte+2's high nibble modeled as an opaque
`src_class` enum -- all from byte-diff/census provenance, never hardware
splice-validated. An external compiler engineer trying to emit a plain
register-to-register move from this documentation could not get one to
work. **Can this repository's own tools independently SYNTHESIZE (not
merely decode) a correct GPR-to-GPR move, and what is the exact rule a
compiler must follow to do so?**

**Hypothesis.** Byte+2 (jointly with byte+3, "op_desc") is a single
structured field on ONE instruction, not five different opcodes.

**Method.**
1. Compile four minimal, tid-varying MSL kernels (`kernels/census.metal`)
   designed to force a real GPR-to-GPR move in different source contexts
   (variable pass-through, swap, loop-carried phi, noinline call-argument
   marshal); disassemble with our own `tools/agx-isa`; record which move
   variant appears where.
2. Compile one purpose-built carrier kernel (`kernels/synth_move.metal`,
   16 constant-index loads -> 16 compact moves -> 4 vector stores, baseline
   `out[K]==in[K]`); INDEPENDENTLY RE-ASSEMBLE 49 candidate move encodings
   with `tools/agx-isa`'s own `assemble()` (field values chosen by us, never
   copy-pasted bytes); splice each in place of an existing 4-byte
   instruction (same length); run on the real M4 GPU; read the destination
   register's value back through the resulting output buffer. See
   `PRE_REGISTRATION.md` for the full frozen hypothesis/matrix/predictions.

**Clean-room provenance: OWN-SHADER.** Every byte inspected or spliced is
the compiled form of our own MSL (`tools/shdump`), assembled/disassembled
with our own `tools/agx-isa`, executed with our own `tools/agxtest` splice
testbed on the local M4. No Apple binary is ever introspected.

**Target.** Local M4/G16G host only (all testing per `CLAUDE.md`
2026-08-27 directive). A18 Pro is out of scope for this experiment
(hands-off).

**Reproduce (from this directory):**
```sh
python3 -B verify.py --selftest
python3 -B verify.py --seqtest
python3 -B make_manifest.py --check
python3 -B verify.py --preflight               # PRE_GPU state only
python3 -B run.py --execute --run-id m4-20260827-run01
python3 -B verify.py --between-runs
python3 -B run.py --execute --run-id m4-20260827-run02
python3 -B analysis.py --run-a m4-20260827-run01 --run-b m4-20260827-run02 --write
python3 -B make_manifest.py --write
python3 -B verify.py --captured
```

See `RESULTS.md` for observations vs. interpretation, `PROGRESS.md` for the
milestone log, and `CAPTURE_CONTRACT.json` for the exact frozen contract.
