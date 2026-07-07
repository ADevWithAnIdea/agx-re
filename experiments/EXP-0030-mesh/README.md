# EXP-0030: Hardware mesh shading (A18 Pro / G17P / Apple9)

- **Date:** 2026-07-07
- **Clean-room category:** OWN-SHADER (compile our own object+mesh+fragment MSL, inspect only our own
  compiled bytes) + DATA-TRACE (iotrace of our own mesh draw, read-only) + PUBLIC (agx-isa length rule).
- **Phase / question:** Capability backlog #1 — the biggest unmapped Apple9 feature. Apple advertises
  hardware-accelerated mesh shading on Family 9 (WWDC). Determine what it is on G17P.
- **Device state:** Apple A18 Pro / G17P, macOS 26.6 (25G5043d), 5 GPU cores, Metal 4 / Apple9. SIP off.

## Hypothesis
Apple9 has "hardware-accelerated mesh shading". Either (a) the object/mesh stages emit vertices and
primitives with **dedicated new opcodes** (like the matrix `0xcf` in EXP-0022 or the ray-intersect
`0xea` in EXP-0023), i.e. dedicated emit silicon, or (b) they lower to ordinary compute + memory stores
into a hardware-managed output buffer, i.e. structurally-accelerated but not new emit instructions. The
deciding test (same as EXP-0022/0023): does the mesh-stage ISA contain a **novel opcode group absent
from a hand-written compute control that writes the same primitives**?

## Method (why it is clean-room legal)
1. **OWN-SHADER extraction.** Extended `shdump`/`agxrender` in this dir (`harness/shdump_mesh.m`,
   `harness/agxrender_mesh.m`) to build an `MTLMeshRenderPipelineDescriptor` (object+mesh+fragment) from
   **our own** MSL, serialize it into an `MTLBinaryArchive`, and render it. Extended `agxparse` via
   `harness/mesh_extract.py` (monkeypatches `STAGE_SECTIONS` to add `__object`/`__mesh`; the shared tool
   is untouched). We inspect only the compiled form of MSL we wrote — no Apple binary is disassembled.
2. **Opcode diff (the deciding test).** Compiled a mesh triangle pipeline (`kernels/mesh_tri.metal`) and
   a **compute control** (`kernels/compute_emul.metal`) that manually writes the same 3 vertices + index
   triple + primitive count to device buffers. Compared opcode inventories (`mtok.py`, `walk.py`).
3. **Byte-diff field decode.** `kernels/mesh_variants.metal` — single-change variants (emit nothing,
   red vs green colour, reversed index, reversed vertex slot, grid 1 vs 2, payload 1.0 vs 2.0). Diffed
   the changed stage (`bytediff.py`) to localize each emit/amplification field.
4. **Cmdstream (DATA-TRACE).** `harness/iohello_mesh.m` mesh draw run under `tools/iotrace` (read-only)
   to capture the IOKit call sequence + control BOs; contrasted with an ordinary draw and a compute
   dispatch.
5. **HW-validate.** Rendered the mesh triangle from the **archived** machine code
   (`MTLPipelineOptionFailOnBinaryArchiveMiss`) into a 16×16 BGRA8 target and read the pixels back.

## Procedure (reproducible)
```sh
# on device ~/cleanroom_work/exp0030 (build tools):
clang -fobjc-arc -framework Metal -framework Foundation -o shdump_mesh    harness/shdump_mesh.m
clang -fobjc-arc -framework Metal -framework Foundation -o agxrender_mesh harness/agxrender_mesh.m
clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o iohello_mesh harness/iohello_mesh.m
clang -arch arm64e -dynamiclib -framework IOKit -framework Foundation -o iotrace.dylib iotrace.c

# 1. compile mesh pipeline + extract each stage
./shdump_mesh -o mesh_tri.bin --object obj_main --mesh mesh_main --fragment frag_main kernels/mesh_tri.metal
python3 mesh_extract.py mesh_tri.bin                                   # lists __object/__mesh/__fragment
python3 mesh_extract.py mesh_tri.bin --stage mesh   --extract-hex
python3 mesh_extract.py mesh_tri.bin --stage object --extract-hex
# 2. compute control + opcode census
./shdump -o compute_emul.bin -f emul_main kernels/compute_emul.metal
python3 mtok.py raw/mains.txt                                          # byte0 census; mesh emit = 0xe7/0xd7
# 3. variants + byte-diff  (see raw/variants.txt)
bash mkvariants.sh ; bash dumpvar.sh
# 4. cmdstream
IOTRACE_LOG=mesh.log DYLD_INSERT_LIBRARIES=./iotrace.dylib ./iohello_mesh
IOTRACE_LOG=mesh_d.log IOTRACE_DUMP_DIR=mesh_maps DYLD_INSERT_LIBRARIES=./iotrace.dylib ./iohello_mesh --dump
# 5. HW render
./agxrender_mesh --archive mesh_tri.bin --source kernels/mesh_tri.metal \
    --object obj_main --mesh mesh_main --fragment frag_main --width 16 --height 16
```

## Raw results → `raw/`
- `archive_structure.txt` — the mesh archive's stages (`__object`/`__mesh`/`__fragment`) + helper regions.
- `mains.txt` / `walk.txt` / `mtok.txt` — extracted stage bytes + opcode census.
- `variants.txt` — the single-change variant streams (byte-diff inputs).
- `iotrace_summary.txt` — IOKit call counts + selector histograms (mesh vs draw vs compute).
- `cmdstream.txt` — the VDM/TA `0x18000` records (mesh mesh-dispatch vs draw `0x61c4`), mesh-only
  dispatch descriptor `0x100000f8000`, mesh BO list.
- `hwval_render.txt` — the rendered green triangle coverage map + centre pixel.

See `RESULTS.md` for analysis. Every finding is tagged **HW-validated** vs **inferred**.

## Clean-room status
Clean. Everything inspected is the compiled form of our own MSL, our own container parse, our own
byte-diff, our own data trace, and a hardware render round-trip. Tools are ours; the only third-party
code is the public agx-isa length rule (read-only) and the public Mach-O format. No Apple binary was
disassembled. `raw/` holds only text (hex + hexdumps + logs); the `.bin` archives stay on the device.
`tools/agx-isa/` was NOT edited — new descriptors are in `new_descriptors.json` for the orchestrator.
