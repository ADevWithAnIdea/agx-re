# `thirdparty/` — external MSL corpus for disassembler coverage testing

This directory holds **upstream, third-party Metal Shading Language (MSL) source**,
collected only as **coverage-test input** for our AGX disassembler ("disassemble anything
that compiles"). Nothing here is authored by this project.

**All files under `thirdparty/` are unmodified upstream third-party source and retain their
ORIGINAL licenses.** Each project keeps its own `LICENSE`/`COPYING`/`NOTICE` file and a
`PROVENANCE.md` recording the exact upstream repo, the cloned commit SHA, the SPDX license,
and how many shader files were taken. Only text shader source was collected — no compiled
artifacts (`*.metallib`, `*.air`, objects, binaries), no non-text files.

Every included project's license is on our permissive allow-list
(MIT / BSD-2-Clause / BSD-3-Clause / Apache-2.0 / ISC / Zlib / CC0 / Unlicense / MIT-0).
No copyleft (GPL/LGPL/AGPL/MPL), proprietary, or unlicensed source is included, and no
Apple-authored / Apple-sample shaders are included.

## Included projects

| Project | Upstream URL | Cloned commit | SPDX license | Shader files | What they are |
|---|---|---|---|---:|---|
| SPIRV-Cross | https://github.com/KhronosGroup/SPIRV-Cross | `6c09849` | `Apache-2.0` | 1058 | MSL transpiler reference outputs (`reference/**/shaders-msl*`); original stage extension preserved with `.msl` appended |
| dawn / Tint | https://github.com/google/dawn | `a5c6297` | `BSD-3-Clause` | 11812 | Tint Metal-backend test expectations (`test/tint/**/*.wgsl.expected.msl`) |
| wgpu / naga | https://github.com/gfx-rs/wgpu | `48904f8` | `MIT OR Apache-2.0` | 119 | naga MSL-backend test outputs + 1 hand-written passthrough shader |
| PyTorch | https://github.com/pytorch/pytorch | `e7206c0` | `BSD-3-Clause` | 48 | hand-written MPS Metal compute kernels |
| llama.cpp / ggml | https://github.com/ggerganov/llama.cpp | `64c8b7d` | `MIT` | 1 | ggml Metal compute backend (one large multi-kernel file) |
| ToyPathTracer | https://github.com/aras-p/ToyPathTracer | `ff20bfe` | `Unlicense` | 1 | Metal path-tracer compute + blit shaders |
| **Total** | | | | **13039** | 12870 `.msl` + 169 `.metal` |

## Notes on selection

- **De-duplication:** exact byte-identical files within a project were dropped (they add no
  disassembler coverage). SPIRV-Cross: 258 dropped (mostly opt vs. no-opt emitting identical
  MSL); dawn: 1270 dropped. Counts above are the unique files kept.
- **SPIRV-Cross renaming:** upstream keeps the pipeline-stage extension on its MSL reference
  outputs (`.vert`/`.frag`/`.comp`/`.tesc`/`.tese`/`.mesh`/`.task`, plus `.mslN` qualifiers);
  `.msl` was appended to each filename (content unchanged) so the stage hint is preserved and
  the file is unambiguously MSL.
- **Deliberately excluded:** SPIRV-Cross's `reference/shaders-ue4/**` category (Unreal-Engine-
  derived inputs) was not taken, despite being Apache-2.0 upstream, to keep this corpus free of
  third-party-engine provenance.

## Projects evaluated but SKIPPED (no permissive standalone MSL to take)

| Project | License | Reason skipped |
|---|---|---|
| KhronosGroup/MoltenVK | Apache-2.0 | No standalone `.metal`/`.msl` files; its Metal shaders live as C-string literals inside `.mm` sources. |
| bkaradzic/bgfx | BSD-2-Clause | No `.metal`/`.msl`; uses its own `.sc` shader language compiled per-backend. |
| godotengine/godot | MIT | No `.metal`/`.msl`; its Metal backend generates MSL at runtime (via SPIRV-Cross), ships no MSL source. |
| ConfettiFX/The-Forge | Apache-2.0 | No `.metal`/`.msl`; current tree uses its own `.fsl` shading language. |
| shader-slang/slang | Apache-2.0 WITH LLVM-exception | No standalone `.metal`/`.msl` test expectations in the tree. |
