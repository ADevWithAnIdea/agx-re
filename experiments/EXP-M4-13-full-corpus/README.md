# EXP-M4-13 — full-corpus ISA convergence

**Goal:** drive the AGX G17P/G16 disassembler DB (`tools/agx-isa`) to *total*
decode coverage against a **large, deliberately-diverse own-shader corpus** —
every instruction byte cleanly tokenized (0 desync) and every instruction fully
field-decoded (0 family-only), verified by round-trip. This is the "make it work
on all of it, fully field-decoded" objective, run as a convergence loop.

**Method (clean-room, OWN-SHADER, compile-only on the M4):** parallel agents each
own a feature category and generate many maximally-different MSL kernels
(`corpus/<category>/*.metal`), compile each with our own `tools/shdump` (which
only *builds* an `MTLBinaryArchive` — it never dispatches, so there is no GPU-hang
risk on this host), and extract the `_agc.main` AGX bytes with our own
`agxparse.py` into `hex/`. A census tokenizes the whole corpus with the committed
DB and inventories every gap; decoders then close each gap by byte-diffing our own
shaders; descriptors are integrated into `tools/agx-isa` with the round-trip test
re-run after each.

Compile failures are kept as **first-class negative capability results** (e.g. no
64-bit buffer atomics, no strong-CAS, only `memory_order_relaxed`, no rectangular
/ integer `simdgroup_matrix`, no RGB9E5 / R11G11B10 pack intrinsic, no motion-blur
ray intersect on this toolchain) — these tell the driver team what to emulate.

## Round 1 baseline (this checkpoint)

575 unique stage programs, 31445 instruction tokens, committed DB:

| metric | value |
|---|---|
| byte coverage | 89.31% |
| named (op resolved) | 63.1% |
| family-only (length known, op/fields unmapped) | 24.4% |
| desync (unknown length) | 12.5% |
| distinct byte0 groups seen | 223 |

Gap inventory: `work/gaps_round1.json`; human census: `work/census_round1.txt`.
The gaps collapse to ~16 low-nibble instruction families (byte0 high-nibble is the
destination register), which is how the decode phase is fanned out.

## Layout

- `corpus/<category>/*.metal` — our own MSL sources (the corpus).
- `hex/*.hex` — extracted `_agc.main` AGX bytes, one program per file (evidence).
- `work/` — build artifacts (compiled `.bin`, `shdump_*`, logs) are gitignored;
  the census `*.json`/`*.txt` records are kept.
