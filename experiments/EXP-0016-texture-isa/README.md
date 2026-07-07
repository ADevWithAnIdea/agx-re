# EXP-0016: Texture / sample instruction family (HW-validated)

- **Date:** 2026-07-06
- **Clean-room category:** OWN-SHADER (+ PUBLIC for the ISA DB/Mach-O format)
- **Phase / question:** Phase 1 shader ISA — decode the texture sample/read/write/query
  instruction family the fragment/compute path exposes (`docs/isa/README.md` flags
  sample=`0x18/0xb0`, derivatives=`0x37/0x38/0x39/0x90/0x92`).
- **Device state:** A18 Pro / G17P, macOS 26.6 (25G5043d). Command Line Tools only,
  runtime `newLibraryWithSource:`. No boot-arg changes.

## Hypothesis
The texture ops flagged by EXP-0008 (`0x18/0xb0` sample, `0x37…` derivatives) form a
sample/read/write/query family. Each op encodes a texture-slot reference, a sampler-slot
reference, coordinate register(s), result register(s), and a variant selector
(sample / bias / lod / grad / gather / read); LOD/bias/gradient operands live in the op
or a preceding ALU. The texture/sampler slots index the Tier-2 argument-buffer descriptor
table decoded in EXP-0011.

## Method (clean-room: OWN-SHADER)
1. **Provoke** — write our own MSL (`kernels/tex_frag.metal` fragment battery sharing a
   uv-passthrough `v_main`; `kernels/tex_comp.metal` compute battery) that each force
   exactly one texture op / variant (`docs/isa/msl-feature-map.md` A15/A16/A18 snippets).
2. **Extract** — `shdump` (compute `-f`, render `--vertex/--fragment`) → `agxparse.py`
   carves `_agc.main` per stage (`extract.sh` → `raw/mains.txt`).
3. **Byte-diff** — `analyze.py` aligns shaders differing in one op to localize each field
   (`raw/field_map.txt`).
4. **HW-validate (splice-and-observe)** — `texr.m` (enhanced render testbed: binds a 4×4
   distinct-texel grid + a 2nd texture + 2 samplers) and `texcomp.m` (compute texture
   runner: writable texture read-back) force our own archived (spliced) machine code
   (`MTLPipelineOptionFailOnBinaryArchiveMiss`) and read pixels/texels back. Splicing a
   field and observing the sampled value changes proves the field HW (`hwval.sh` →
   `raw/hw_validation.txt`).

Every byte inspected/spliced is the compiled form of our own MSL. No Apple binary was
disassembled.

## Procedure
```sh
# device ~/cleanroom_work/exp0016 (tools pushed from tools/shdump, tools/agxtest, tools/agx-isa):
clang -fobjc-arc -framework Metal -framework Foundation -o shdump  shdump.m
clang -fobjc-arc -framework Metal -framework Foundation -o texr    texr.m
clang -fobjc-arc -framework Metal -framework Foundation -o texcomp texcomp.m
bash extract.sh        # compile+carve every kernel -> raw/mains.txt
bash hwval.sh          # all splice-and-observe HW validations -> raw/hw_validation.txt
# host:
python3 analyze.py diff frag:f_sample frag:f_bias   # localize the LOD/bias field, etc.
```

## Raw results
- `raw/mains.txt` — `_agc.main` hex of all 17 fragment + 19 compute texture kernels.
- `raw/field_map.txt` — the sample-op field table (byte-diff).
- `raw/hw_validation.txt` — the 6 HW splice-and-observe tests (all STATUS OK, no wedge).

See `RESULTS.md` for the decode and analysis.

## Established facts → docs
See `RESULTS.md` §"Answers to the brief"; DB updated in `../../tools/agx-isa/` (descriptors
`tex_sample`, `tex_write`, `tex_deriv` + length rules; `roundtrip_test.py` ALL PASS).
Orchestrator to fold into `docs/isa/` + `PROVENANCE.md`.

## Follow-ups
- Full result-register / coordinate-register bit decode (op+0 high nibble, op+1).
- Gather component field full enum; offset gather; depth-compare (`sample_compare`) op.
- Array/cube/3D/MSAA index-operand bit positions (kernels compiled; byte-diff pending).
- Derivative fine/coarse decode (0x37 byte+1/+6 sub-fields); implicit-LOD internal grad.
