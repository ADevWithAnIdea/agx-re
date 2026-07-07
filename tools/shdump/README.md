# shdump — OWN-SHADER AGX byte extractor

Turns **our own** MSL source into the raw **A18 Pro AGX machine-code bytes** the
GPU executes. This is the foundational clean-room capability (ROADMAP 0.2): it
feeds the assembler, the hardware testbed, and all ISA RE.

**Clean-room:** OWN-SHADER. Only our own MSL is compiled, and only our own
compiled shader bytes are inspected. Nothing here disassembles or introspects any
Apple binary. The container parser walks the *public* Mach-O format; the only
third-party code in the pipeline is the public MIT applegpu disassembler, run on
our own bytes.

## Pieces

| file | role | runs on |
|---|---|---|
| `shdump.m` | Compile MSL at runtime (`newLibraryWithSource:`), build a **compute** pipeline *or* (`--render`) a **vertex+fragment** render pipeline, serialize it into an `MTLBinaryArchive` container. | device (A18) |
| `agxparse.py` | Our own Mach-O / Metal-fat parser. Isolates the AGX bytes (`_agc.main`, `_agc.main.constant_program`, or whole `__text`) for any stage (`--stage compute|vertex|fragment`) and reports AIR-vs-AGX structure. | anywhere (py3) |
| `bytediff.py` | Differential-compilation helper: align two extracted byte strings and localize which bytes/bits moved. | anywhere (py3) |

## Build (device, Command Line Tools only — no `metal` CLI needed)

```sh
clang -fobjc-arc -framework Metal -framework Foundation -o shdump shdump.m
```

## Use

```sh
# 1. compile our MSL -> serialized binary-archive container (device)
./shdump -o out.bin kernel.metal            # compute (default); or: -o out.bin - (stdin)
#   options: -f <fn> pick a function; --no-fast-math
# render pipeline (vertex+fragment) -> archive carries BOTH stages (EXP-0008):
./shdump -o out.bin --render --vertex v_main --fragment f_main render.metal
#   options: --color-format N (default 80 = bgra8Unorm); vertex/fragment auto-picked by type if omitted

# 2. inspect container structure (AIR vs AGX, sections, all stages present)
python3 agxparse.py out.bin

# 3. extract the AGX bytes as hex (default target: _agc.main; default stage: compute else first)
python3 agxparse.py out.bin --extract-hex
python3 agxparse.py out.bin --stage fragment --extract-hex        # render: pick the stage
python3 agxparse.py out.bin --stage vertex --extract-hex --symbol _agc.main.constant_program
python3 agxparse.py out.bin --stage fragment --extract-hex --whole-text
python3 agxparse.py out.bin --stage fragment --extract-bin frag.bin
python3 agxparse.py out.bin --stage fragment --locate _agc.main   # 'ABS_OFF LEN' for splicing
python3 agxparse.py out.bin --json                                # machine-readable report

# 4. differential compilation: localize an encoding field
python3 bytediff.py a.main.hex b.main.hex labelA labelB
python3 bytediff.py --hex 1ca0..  1ca1..  labelA labelB
```

## What the container looks like (A18 Pro, macOS 26.6)

`serializeToURL:` writes a **Metal fat binary** (magic `0xCBFEBABE`) with two images:

- **AIR64** image (`cputype 0x1000017`) — LLVM bitcode (`BC\xC0\xDE`); the portable
  AIR, *not* machine code. Ignored.
- **AppleGPU** image (`cputype 0x1000013`) — native AGX. For a **compute** pipeline
  it has a `__TEXT,__compute` section; for a **render** pipeline (EXP-0008) it has
  **both `__TEXT,__vertex` and `__TEXT,__fragment`** sections in the *same* image
  (not separate images, not separate symbols). Each such section is a **nested**
  Mach-O whose `__TEXT,__text` holds the code, split by symbols `_agc.main` (main
  program) and `_agc.main.constant_program` (prolog).

`agxparse.py` returns exit status 0 on a clean AGX extraction, 2 if only AIR was
found. `--symbol __whole_text__` (or `--whole-text`) dumps both regions together;
`--stage {compute,vertex,fragment}` picks the stage (default: compute, else the
first stage present). The structural report lists every stage found.

## Notes / limits

- Handles compute kernels and vertex+fragment render pipelines (EXP-0008). The
  vertex/fragment streams use instruction groups the current `agx-isa` DB does not
  yet cover (low-nibble-`f` ALU, low-nibble-`7` memory variants, varying stores,
  sample/derivative ops), so they don't fully `tokenize` yet — that's later work.
- The `.bin` archive is a Metal container built from our source — keep it on the
  device workspace; commit only the extracted hex/text (repo `.gitignore` blocks
  `*.metallib`/`*.air` by default).
- The A18 Pro AGX ISA is a **new instruction set** (EXP-0001): the extracted bytes
  do **not** decode under the public G13 applegpu disassembler.
