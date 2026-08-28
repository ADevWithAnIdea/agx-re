# EXP-0119 — M4 register-lifecycle field map

**Question:** four remaining unknowns in the register-lifetime arc
(EXP-0086 → EXP-0089 → EXP-0099): what do `falu2`'s bits 15/31 encode (or
what tested space are they inert over)? What is the per-family lifetime
field map for every family a compiler must emit (integer/memory/compact/
extended/12-byte forms, `unpack_convert`/`cvt_i2f`, control-flow ops)? Does
the literal bit 17 generalize as one mechanism or several distinct ones
sharing a bit position? Which architectural model (persistent producer-side
writeback suppression vs. one-shot bypass cache) survives a discriminating
test (register-file-vs-forwarding, later-write restoration, memory-op and
barrier crossing)?

**Hypothesis / method:** see `PRE_REGISTRATION.md` (H1-H4, falsifier design
per group, the extensive informal pilot phase and the real bugs it caught)
and `CAPTURE_CONTRACT.json` (frozen 77-case matrix, gates, hypothesis-to-
group map). Two execution modes: MODE A hand-assembles whole straight-line
programs via `tools/agx-isa`'s own `isadb.assemble()` (full field control,
independent of compiler scheduling) spliced into `kernels/carrier.metal`'s
`_agc.main` region; MODE B (H2_CACHEBYTE_* only) splices individual fields
into two real compiled kernels reused verbatim from EXP-0089
(`kernels/lit17_unpack.metal`, `kernels/lit17_cvt.metal`), whose register
addressing this experiment does not itself validate.

**Clean-room category:** OWN-SHADER + HW-PROBE + PUBLIC (this document, its
`RESULTS.md`, and every file below cite the exact category per finding; no
Apple binary is inspected anywhere — see the clean-room attestation in
`RESULTS.md`).

**Commands:**

```sh
python3 -B verify.py --selftest        # synthetic, no GPU
python3 -B verify.py --seqtest         # gate-sequence check
python3 -B baseline.py                 # re-derive carrier/lit17_* facts fresh (no GPU dispatch)
python3 -B make_manifest.py --check    # authored-file presence
python3 -B run.py --execute --run-id m4-20260828-run01   # real GPU, append-only
python3 -B verify.py --between-runs
python3 -B run.py --execute --run-id m4-20260828-run02   # real GPU, append-only
python3 -B verify.py --captured
python3 -B analysis.py --write
```

**Layout:** `isa_helpers.py` (instruction builders, register-addressing
scope discipline), `casematrix.py` (the 77-case frozen matrix, single
source of truth for run.py/verify.py/analysis.py), `harness/` (build +
per-case executor), `kernels/` (own MSL: `carrier.metal` reused from
EXP-0099, `lit17_unpack.metal`/`lit17_cvt.metal` reused from EXP-0089),
`raw/` (append-only captures), `work/` (scratch, never committed evidence,
never outside this experiment directory).

**Do NOT `git commit`** — the orchestrator reviews and commits.
