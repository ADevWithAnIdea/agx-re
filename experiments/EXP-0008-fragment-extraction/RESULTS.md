# EXP-0008 Results — vertex/fragment AGX extraction + render testbed

Clean-room category: **OWN-SHADER** (+ PUBLIC for the ISA DB used to tokenize).
Every byte below is the compiled form of MSL **we wrote** (`kernels/render_*.metal`).
No Apple binary was disassembled or introspected — only structure inspection of
**our own** serialized archive (public Mach-O format) with our own parser.

## 1. Render-pipeline extraction WORKS — and the archive layout

`shdump.m --render` compiles our vertex+fragment MSL, builds an
`MTLRenderPipelineDescriptor` (one `bgra8Unorm` color attachment),
`newRenderPipelineStateWithDescriptor:` (validates it), then serializes via
`MTLBinaryArchive` `addRenderPipelineFunctionsWithDescriptor:` → `serializeToURL:`.

**Layout (discovered by parsing OUR OWN archive; `raw/render_min.info.txt`):** the
serialized render archive is the same **Metal fat binary** (magic `0xCBFEBABE`) as
the compute case, with an **AIR64** image (bitcode, ignored) and one **AppleGPU**
image (`cputype 0x1000013`). The key finding:

> Vertex and fragment are **two separate `__TEXT` sections in the *same* AppleGPU
> image** — `__TEXT,__vertex` and `__TEXT,__fragment` — sitting alongside
> `__reflection`, `__descriptor`, `__metallib`. They are **not** separate fat
> images and **not** separate `_agc.main` symbols in one section.

Each of `__vertex` / `__fragment` is **itself a nested Mach-O** whose `__TEXT,__text`
holds the AGX code, carved by the symbol table exactly like `__compute`:
`_agc.main.constant_program` (fixed 64-byte prolog) + `_agc.main` (the program).
So the compute carving method extends verbatim; only the **outer section name**
changes per stage. `agxparse.py` now enumerates all stages and takes a
`--stage {compute,vertex,fragment}` selector; `locate_region(...,stage=)` gained a
stage argument for splicing (both are backward-compatible — the compute path is
byte-identical to EXP-0001, regression-checked in `analyze.py`).

Example (`render_min`): AppleGPU image at file off 7776; `__vertex` off 2384
size 1824 → nested `__text` 184B = cprog(64)+`_agc.main`(120); `__fragment` off
4208 size 2096 → nested `__text` 118B = cprog(64)+`_agc.main`(54).

## 2. Carving is correct; streams tokenize as far as the DB covers

**Carve-correctness (all 8 stages, `analyze.py` §1):** for every stage,
`__whole_text__ == constant_program ++ _agc.main` **byte-exact**, and every
`_agc.main` **ends in the `0e000000` stop word** (same terminator as compute) — the
symbol-table carve partitions `__text` with no gap/overlap and lands on real
instruction boundaries.

**Determinism (`raw/determinism.txt`):** every vertex and fragment `_agc.main` is
**byte-identical across 3 independent compilations** (all `STABLE`). Same source →
same bytes. Cross-check: `render_tex` and `render_deriv` share identical vertex MSL
and produced **byte-identical vertex code** (sha `1ab88ad2…`).

**Compute regression:** the reference compute kernels still tokenize **CLEAN, 0
leftover** under the current DB through the refactored parser (`k01_fadd`,
`k10_load_store` — `analyze.py` §2). The refactor did not disturb the compute path.

**Vertex/fragment do NOT fully tokenize under the current compute-only DB — that
is the finding.** They begin with instruction groups the DB cannot even *length*,
so tokenization stops at the first one. This is exactly the "fragment reveals
instructions the compute DB doesn't cover" result the experiment sought.

## 3. The NEW fragment/vertex instruction surface (what compute lacks)

**PROVEN-boundary new leaders** (each sits at a real instruction boundary because
everything before it tokenized cleanly, or is the program's first instruction;
`analyze.py` §3):

| byte0 | where | note |
|---|---|---|
| `0x2f` | first instr of `render_interp/tex/deriv` **fragments** | low-nibble-`f` ALU family |
| `0x97` | first instr of `render_min` **fragment** | low-nibble-`7` memory family |
| `0x9f` | first real instr of **every vertex** | int-ALU family (also in compute int kernels — not fragment-new) |

**Full new-group surface (structural / byte-diff, boundaries past the first
unknown are inferred — NOT decoded):** the vertex/fragment streams are dominated by
three instruction families **none of which the current DB contains** (the DB covers
low-nibble `c`=preamble, `9`=float-ALU, `7`=`0x67/0xe7` load/store, `e`=stop, plus
`0x0b/0x12` float):

- **low-nibble `0xf` ALU family:** `0x2f`, `0x3f`, `0xaf` (siblings of the
  known-but-unsolved int-ALU `0x9f`). Carries interpolation / varying math.
- **low-nibble `0x7` memory family beyond compute's `0x67/0xe7`:** `0x07`, `0x87`,
  `0x97`, `0xa7` — attribute/varying loads, fragment-output stores, `0xa7` in vertex.
- **vertex varying/attribute stores:** `0x05`/`0x06`/`0x57` forms (the position &
  varying output writes).

**Feature attribution by differential (`analyze.py` §4).** All 4 fragments share a
**28-byte epilogue** `87 02 54 0c 08 00 | e7 06 54 …4e… | 07 02 54 0c 02 00 | 0e00
0000` = the color-output store path (present in every fragment). The per-feature
deltas isolate:

- **Interpolation** (`render_interp` reads a `[[stage_in]]` varying): adds the
  `0x2f/0xaf/0x3f` ALU-family body (~112 B) — absent from the constant-color frag.
- **Texture sample, implicit-LOD** (`render_tex`): uniquely adds **`0x18`, `0xb0`**
  byte0 groups (the sampler/texture op) on top of the interpolation family.
- **Derivatives** (`render_deriv`, `dfdx/dfdy`): uniquely adds **`0x37`, `0x38`,
  `0x39`, `0x90`, `0x92`** byte0 groups (quad-difference ops).

These `0x18/0xb0` (sample) and `0x37/0x38/0x39` (derivative) groups are the concrete
fragment-only instruction surface the compute path can never expose.

## 4. Render hardware testbed — BUILT and HW-validated (`tools/agxtest/agxrender.m`)

Draws a full-screen triangle (3 vertices, no vertex buffer) with our archived
vertex+fragment code into a small `bgra8Unorm` render target and reads the pixels
back. It forces the **archived (spliceable) machine code** to run via
`binaryArchives` + `MTLPipelineOptionFailOnBinaryArchiveMiss` (pipeline creation
*fails* rather than recompiling from AIR on a miss → `PIPELINE_SOURCE archive`
proves the archived code executed). Results (`raw/render_hw.txt`):

- **`render_min` 1×1** → `rgba=1.000,0.502,0.251,1.000` = exactly
  `float4(1.0,0.5,0.25,1.0)`. Byte-identical across 2 runs (determinism).
- **`render_interp` 4×4** → the interpolated varying varies smoothly across pixels
  (red 0.125→0.875 L→R, green 0.875→0.125 T→B): fragment **interpolation** running.
- **`render_tex` 2×2** (`--tex-fill 10,20,30,40`) → every pixel = the sampled
  constant `0.039,0.078,0.118,0.157`: implicit-LOD **sample** running.
- **`render_deriv` 4×4** → constant `dfdx+dfdy` (red `0.251`) across the primitive:
  fragment **derivatives** running.

**Runs MODIFIED fragment code (the brief's ask), HW-validated:** splicing the
`render_min` fragment `_agc.main[0x06]` `0x80`→`0x40` changed the pixel from
`rgba=1.000,0.502,0.251,1.000` to `1.000,0.251,0.251,1.000` — green `0.502`→`0.251`
(exactly `128/255`→`64/255`), while `PIPELINE_SOURCE archive` still held. So the
spliced *fragment* machine code is what ran, and byte `+0x06` of that `0x97`
instruction embeds the green color constant. (Micro-finding, not pursued further.)

**Usage & limits:** `agxrender --archive A.bin --source S.metal --vertex V
--fragment F [--width W --height H] [--tex-fill R,G,B,A]`. One-shot per run (fresh
`MTLDevice`), so no in-process code memoization (unlike a persistent sweeper — a
`newLibraryWithURL:` per-request loop, as in `agxrun_persist`, is the follow-up for
fast fragment sweeps).

## 5. Answers to the brief
1. **Render extraction works.** Vertex & fragment are two `__TEXT` sections
   (`__vertex`, `__fragment`) in one AppleGPU image, each a nested Mach-O carved by
   `_agc.main`/`_agc.main.constant_program` — same shape as `__compute`, distinct
   only by section name. `--stage` selects the stage.
2. **They carve correctly and tokenize as far as the DB reaches**; the new
   fragment/vertex byte0 groups the compute DB lacks are the low-nibble-`f` ALU
   family (`0x2f/0x3f/0xaf`, proven leader `0x2f`), low-nibble-`7` memory family
   (`0x07/0x87/0x97/0xa7`, proven leader `0x97`), vertex varying stores
   (`0x05/0x06/0x57`), and the feature-localized sample (`0x18/0xb0`) and derivative
   (`0x37/0x38/0x39/0x90/0x92`) groups.
3. **Render testbed built** (`tools/agxtest/agxrender.m`) and HW-validated on all
   four shaders + a fragment splice. Run it as in §4.
4. **Determinism:** all stages STABLE over 3 compiles. **Obstacle:** none blocking;
   the new groups' exact lengths/semantics are deferred (decode experiment).
   **Recommended next:** a decode experiment for the fragment families above,
   using `agxrender` for hardware validation (interpolation modes, sample LOD/bias,
   derivative fine/coarse, programmable-blend/imageblock next).

## 6. Clean-room status
Clean. Everything inspected is the compiled form of our own MSL. Tools are ours
(`shdump.m --render`, `agxparse.py --stage`, `agxrender.m`, `analyze.py`); the only
third-party code is the public ISA DB (`tools/agx-isa/`, read-only) applied to our
own bytes. No Apple binary was disassembled. No Apple blob is committed — `raw/`
holds only hex/text; the `.bin` archives stay on the device under `~/cleanroom_work/`.
