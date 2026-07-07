# EXP-0008: extend extraction to VERTEX and FRAGMENT shader code

- **Date:** 2026-07-06
- **Clean-room category:** OWN-SHADER (+ PUBLIC for the ISA DB used to tokenize).
- **Phase / question:** ROADMAP Phase 1 — the current pipeline extracts only the
  `__compute` image; interpolation / derivative / sampling / imageblock / blending
  instruction families live **only** in vertex/fragment code and can't be
  characterized until we can extract non-compute stages.
- **Device state:** Apple A18 Pro (G17P), macOS 26.6 (25G5043d), Command Line
  Tools only (runtime `newLibraryWithSource:` — no `metal` CLI). Device workspace
  `~/cleanroom_work/exp0008/`.

## Hypothesis
A render pipeline serialized via `MTLBinaryArchive` carries the vertex and
fragment AGX machine code in the same Metal-fat / AppleGPU container shape as the
compute path, so the EXP-0001 carving method (nested Mach-O → `__TEXT,__text`
carved by `_agc.main` symbols) extends to both stages. Fragment code will contain
instruction groups the current compute-only ISA DB does not cover.

## Method (clean-room legal: OWN-SHADER)
1. Compile **our own** minimal `[[vertex]]`+`[[fragment]]` MSL at runtime, build an
   `MTLRenderPipelineDescriptor` (one `bgra8Unorm` color attachment), validate it
   with `newRenderPipelineStateWithDescriptor:`, and serialize it into an
   `MTLBinaryArchive` (`addRenderPipelineFunctionsWithDescriptor:` →
   `serializeToURL:`). Tool: `tools/shdump/shdump.m --render`.
2. Structurally parse **our own** archive with our own Mach-O parser
   (`tools/shdump/agxparse.py`, extended with `--stage {compute,vertex,fragment}`)
   to carve the vertex and fragment code. **Only structure inspection of OUR OWN
   archive** — never disassembling any Apple binary.
3. Tokenize the carved bytes with the current `tools/agx-isa/` DB (read-only here;
   another experiment owns it) and catalog the NEW byte0 groups fragment reveals.
4. Stretch: a render hardware testbed (`tools/agxtest/agxrender.m`) — draw a
   full-screen triangle into a small render target and read the pixel back — so
   future experiments can run *modified* fragment code and observe output.

## Procedure (copy-pasteable)
```sh
# device: build + run the whole render corpus (compile x3 for determinism)
scp tools/shdump/{shdump.m,agxparse.py} experiments/EXP-0008-*/kernels/*.metal \
    experiments/EXP-0008-*/run_render.sh  user@DEV:~/cleanroom_work/exp0008/
ssh DEV 'cd ~/cleanroom_work/exp0008 && clang -fobjc-arc -framework Metal \
    -framework Foundation -o shdump shdump.m && ./run_render.sh'
# pull hex back, analyze on host
scp 'user@DEV:~/cleanroom_work/exp0008/raw/*' experiments/EXP-0008-*/raw/
python3 experiments/EXP-0008-fragment-extraction/analyze.py

# render hardware testbed
ssh DEV 'cd ~/cleanroom_work/exp0008 && clang -fobjc-arc -framework Metal \
    -framework Foundation -o agxrender agxrender.m && \
    ./agxrender --archive out/render_min.run1.bin --source kernels/render_min.metal \
    --vertex v_main --fragment f_main --width 1 --height 1'
```

## Files
- `kernels/render_{min,interp,tex,deriv}.metal` — our vertex+fragment pairs
  (constant color / interpolated varying / implicit-LOD sample / dfdx+dfdy).
- `run_render.sh` — device driver: compile ×3 (determinism), carve vertex+fragment
  `_agc.main`/`constant_program`/`__text`, sha256.
- `analyze.py` — host analysis: carve-correctness reconstruction, compute
  regression, front-tokenize, differential feature attribution.
- `raw/` — all extracted hex, `manifest.txt`, `determinism.txt`, `analysis.txt`,
  `render_hw.txt` (hardware testbed output), per-shader `*.info.txt` (layout).
  **Text only — no Apple blobs / archives.**

## Raw results
See `RESULTS.md` and `raw/`.

## Follow-ups
Solve instruction lengths + decode the new fragment/vertex groups (the
low-nibble-`0xf` ALU family `0x2f/0x3f/0xaf`, the low-nibble-`0x7` memory family
`0x07/0x87/0x97/0xa7`, the vertex varying stores `0x05/0x06/0x57`, and the
sample-`0x18/0xb0` / derivative-`0x37/0x38/0x39` bytes) — a decode experiment,
using `agxrender` for hardware validation.
