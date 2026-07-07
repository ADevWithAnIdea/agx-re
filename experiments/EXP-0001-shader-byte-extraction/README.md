# EXP-0001: Extract raw A18 Pro AGX machine-code bytes from our own shaders

- **Date:** 2026-07-06
- **Clean-room category:** OWN-SHADER (compile our own MSL, extract its compiled
  bytes) + PUBLIC (run the public dougallj/applegpu disassembler on those bytes).
- **Phase / question:** ROADMAP Phase 0 → **0.2** (own-shader compile+extract tool)
  and a first taste of **0.3** (differential compilation).
- **Device state:** Apple A18 Pro, SoC T8140, macOS 26.6 (25G5043d), 5 GPU cores,
  Metal feature family Apple9. Command Line Tools only (no `metal` CLI). SIP off.
  No boot-args / nvram changes for this experiment.

## Hypothesis

Metal's `MTLBinaryArchive.serializeToURL:` writes a container that embeds the
**device-compiled** GPU program for a compute pipeline. We expect that container
to hold *both* AIR (LLVM bitcode, portable IR) *and* native AGX machine code, in
separate images we can tell apart by Mach-O `cputype`. If so, a container parser
of our own can isolate the raw AGX bytes the GPU executes for a kernel we wrote.
We further expect those bytes to be **deterministic** (same source → same bytes)
and to **not** decode under the public G13/M1 applegpu disassembler (the A18 ISA
is given to be a new instruction set).

## Method (and why it is clean-room legal)

Allowed technique #3 from `../../CLAUDE.md`: *compile our OWN shaders and inspect
those*. Every shader here is our own MSL (`kernels/*.metal`). The pipeline is:

1. `tools/shdump/shdump.m` — runtime-compile our MSL with the **public** Metal API
   (`newLibraryWithSource:`), build an `MTLComputePipelineState`, add it to an
   `MTLBinaryArchive`, and `serializeToURL:`. No Apple binary is inspected; we only
   ask Metal to compile *our* source.
2. `tools/shdump/agxparse.py` — **our own** Mach-O/Metal-fat container parser. It
   walks the public, documented Mach-O format (section + symbol tables) to slice
   out the bytes of the shader *we* compiled. This is container parsing, not
   disassembly of an Apple binary. (Structure was informed by the public/MIT
   applegpu `metal-archive-extractor.cpp`; the implementation is ours.)
3. `tools/shdump/bytediff.py` — diffs two extracted byte strings (differential
   compilation) over our own bytes.
4. The public MIT applegpu disassembler is then run on our own extracted bytes to
   demonstrate the ISA is different (PUBLIC tool, OWN-SHADER data).

No `otool -tv`/`-tV`, no disassembler, no decompiler is ever pointed at an Apple
binary. The only machine code we look at is the compiled form of source we wrote.

## Procedure (reproducible)

On the device, under `~/cleanroom_work/exp0001/`:

```sh
# build the extractor (Command Line Tools only)
clang -fobjc-arc -framework Metal -framework Foundation -o shdump shdump.m

# one kernel, by hand:
./shdump -o out/k01.bin kernels/k01_fadd.metal      # compile+serialize (ours)
python3 agxparse.py out/k01.bin                      # structural report
python3 agxparse.py out/k01.bin --extract-hex --symbol _agc.main   # AGX bytes

# whole corpus + 3x determinism + per-region hex:
bash run_all.sh
```

The driver (`run_all.sh`) compiles every kernel **three times** and records the
sha256 of the extracted `_agc.main` for each run (determinism), plus per-region
hex (main / constant_program / whole __text) under `raw/`.

Host-side analysis (in the repo):

```sh
# minimal-pair diffs
python3 tools/shdump/bytediff.py raw/k01_fadd.main.hex raw/k02_fmul.main.hex fadd fmul
# public G13 disassembler on our A18 bytes (expected to fail / garble)
python3 gpu_knowledge/isa/applegpu/disassemble.py <ourbytes.bin>
```

## Raw results

See `raw/`:
- `manifest.txt` — per-kernel byte lengths (main / constant_program / whole text).
- `determinism.txt` — sha256 of `_agc.main` across 3 independent compiles (all STABLE).
- `k*.main.hex`, `k*.cprog.hex`, `k*.text.hex` — extracted AGX bytes as hex.
- `k*.info.txt` — the parser's structural report per kernel (container layout,
  AIR-vs-AGX evidence, symbol regions).
- `diffs.txt` — the minimal-pair byte diffs.
- `applegpu_attempt.txt` — public G13 disassembler output on our A18 bytes.

Key observations are summarized inline in `RESULTS.md`.

## Analysis

See `RESULTS.md` for the full write-up. Headline: extraction works and is
deterministic; the AGX code is cleanly separable from the AIR bitcode; and the
A18 encoding does not match G13 (confirming a new ISA). Minimal pairs localize
the op-select, float-immediate, and source-operand fields to single bytes/bits.

## Established facts → docs

Proposed (for the orchestrator to commit into `docs/` + `PROVENANCE.md`):
- `MTLBinaryArchive` serialization yields a Metal-fat container with a separate
  **AIR64** image (AIR/bitcode, `BC\xC0\xDE`) and an **AppleGPU** image (native
  AGX). → `docs/isa/` provenance OWN-SHADER (this experiment).
- AGX code for a kernel lives in the AppleGPU image's `__TEXT,__compute` nested
  Mach-O, `__TEXT,__text`, split by symbols `_agc.main` and
  `_agc.main.constant_program`. → `docs/isa/`.
- A18 Pro AGX is not decoded by the G13 applegpu disassembler (new ISA). → ROADMAP
  premise confirmed empirically.

## Follow-ups

- Stand up the empty A18 instruction database (Phase 1) and begin decoding
  `_agc.main` structure (instruction lengths, the `0e000000` terminator, the fixed
  `1ca01006…` preamble) via more differential pairs.
- Build the 0.4 hardware testbed to validate any decoded encoding by round-trip.
- Where does the Metal buffer *index* live, if not in the code? (k08/k09 were
  byte-identical.) Trace it at bind time in a later experiment.
