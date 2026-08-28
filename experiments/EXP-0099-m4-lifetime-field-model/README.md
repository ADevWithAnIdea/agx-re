# EXP-0099 — M4 lifetime-field model (falu2/falu2i source-register split)

## Question

An external compiler engineer's `apple9_isa_explainer.md` (repo root) claims
`falu2`/`falu2i`'s source-register field is a **6-bit register index plus a
per-source retention flag** (his bit15/bit31), not the **7-bit literal
register index** `tools/agx-isa/db.json` currently models — and that the
consumer-route field (his bits 45–47, our `mod_hi` bits 1–3) determines
whether a `device_load`-produced operand can feed a float-ALU instruction
(EXP-0090's blocker #1). This experiment settles both claims, plus a
complementary-pair sub-question, a register-move retry (EXP-0090's blocker
#2), and two of his encoding tables, on real M4 hardware.

Full hypothesis list (H1–H6), falsifier design, and the pilot-phase incident
that shaped the final case design: `PRE_REGISTRATION.md`. Results:
`RESULTS.md`. Milestone log: `PROGRESS.md`.

## Method

Every case is a hand-built AGX instruction sequence (`tools/agx-isa`'s own
`isadb.assemble()`, never a captured template), spliced over
`kernels/carrier.metal`'s compiled `_agc.main` (offset 0) via
`tools/agxtest`, executed on the real M4 GPU, and compared to an
independently-computed Python oracle. Same architecture as
`EXP-0090-m4-handbuilt-program-suite` (whole hand-built programs,
subprocess-per-case, two independent gated runs).

## Reproduce

```sh
python3 -B baseline.py                 # re-derive carrier facts (no GPU)
python3 -B casematrix.py               # list the 35 cases + oracles (no GPU)
python3 -B verify.py --selftest        # synthetic, no GPU
python3 -B verify.py --seqtest         # synthetic, no GPU
python3 -B verify.py --preflight       # pre-run01, no GPU
python3 -B run.py --execute --run-id m4-20260828-run01   # GPU
python3 -B verify.py --between-runs
python3 -B run.py --execute --run-id m4-20260828-run02   # GPU
python3 -B verify.py --captured
python3 -B analysis.py --write
python3 -B make_manifest.py --write    # (or --check pre-GPU)
```

## Clean-room provenance

```text
Clean-room provenance: OWN-SHADER + HW-PROBE + PUBLIC
Inputs inspected: kernels/carrier.metal (our own MSL), tools/agx-isa's
  isadb.assemble()/disassemble()/imm_encode()/imm_decode() (read-only),
  tools/agxtest (read-only), tools/shdump (read-only).
  apple9_isa_explainer.md is cited as the HYPOTHESIS ORIGIN (PUBLIC
  category, a third-party document available to us like any other public
  reference) -- no GLSL source or byte sequence from that document is
  copied into any file in this experiment; every instruction byte is our
  own field values passed through our own assembler.
Apple binary introspection: NONE.
Reproduction: see command sequence above.
Evidence: raw/m4-20260828-run01/, raw/m4-20260828-run02/, analysis.json.
```
