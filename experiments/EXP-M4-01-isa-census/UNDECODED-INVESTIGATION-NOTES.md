# M4 census — undecoded byte0-group investigation (starting notes)

## Context
Repeating the A18 RE on the **local Mac Mini M4** (Apple M4, Mac16,10, 10-core GPU, Metal 4, this host — NOT a remote device; compile/extract/splice run LOCALLY). M4 shares the A18 ISA: all 57 A18-corpus shaders compile on M4, and the A18 DB (`tools/agx-isa`) tokenizes them at **88.6% tokens / 91.5% bytes** — same as A18. But the resync census reports **~28 undecoded byte0 groups**. The user wants these driven to ~0 ("we shouldn't have any of those").

## What's established
- The census (`experiments/EXP-M4-01-isa-census/census/census.py`, reads `census/hex/*.hex`) resyncs by advancing ONE 2-byte parcel on a length failure — so a SINGLE length-mis-count cascades into MANY spurious "undecoded groups" until it re-aligns. The undecoded-group count is therefore inflated; the real cause is a small number of length bugs and/or genuinely-missing encodings.
- `0x2b` (the byte the user first noticed) is NOT a real group head — it appears only INSIDE resync samples (mid-instruction). Ignore it as a symptom, not a cause.
- **Integer multiply/MAD is NOT the gap in isolation:** minimal `o=a*b` / `o=a*b+c` / int `a*b` kernels (`work/mul.metal`) tokenize 100% clean — `imad` = byte0 `0x9f`/`0x1f`, **byte+2=0x56** (vs `iadd2` byte+2=0x54), 12 bytes, already in the DB. So the desyncs in dense kernels (`k_uint_arith` 83%, `k_int64` 81%, `k_transcend` 75%, `k_tex_atomic`/`k_tex_array_cube` 84%) come from something subtler — likely **imad/iadd LENGTH VARIANTS** (immediate operand or wider forms with a length ≠ 12), or other instructions.
- Recurring motif around the desyncs (see `raw/M4_census.txt` and a walk of `k_uint_arith`): `a7 07 54`, `27 07 54`, `81 27 80`, `32 80 25 8b`, `9f 00 54 …` with trailing `03 0c 8e` / `03 08 06` operand tails. These look like arithmetic/address-math instructions whose LENGTH the DB gets wrong, desyncing the walk.

## The task (for the subagent)
Drive the census to ~0 undecoded on the M4 corpus (and re-check on the A18 corpus — same ISA, so fixes should apply to both; A18 hex is in `experiments/EXP-0036-consolidation-census/hex/`).

Method per group: pick a shader with a desync (start with `k_uint_arith`, `k_int_arith`, `k_transcend`), walk it, find the FIRST instruction whose decoded length is wrong (the one right before the first `<UNDECODED>`), isolate that instruction by compiling a minimal provoking MSL kernel (`work/*.metal` + `shdump` built locally), byte-diff to pin its true length/fields, splice-and-run on the M4 (`tools/agxtest`, build locally) to HW-validate, then add/fix the descriptor + length rule in `tools/agx-isa`. Keep `roundtrip_test.py` GREEN. Re-run the census after each fix; watch the undecoded-group count collapse.

Distinguish: (a) length bug in an existing instruction (fix the length rule) vs (b) genuinely-missing instruction (add descriptor) vs (c) true resync artifact (rare). Most are expected to be (a).

Build harnesses locally: `clang -fobjc-arc -framework Metal -framework Foundation -o shdump tools/shdump/shdump.m` (already done in `census/` and `work/`); agxtest similarly.
