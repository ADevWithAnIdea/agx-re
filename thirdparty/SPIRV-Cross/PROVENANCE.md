# Third-party source: SPIRV-Cross (MSL reference outputs)

- **Project:** KhronosGroup/SPIRV-Cross
- **Repo URL:** https://github.com/KhronosGroup/SPIRV-Cross
- **Cloned commit:** `6c09849fe88c48eaed08413aa022aaa136a3a057`
- **License (SPDX):** `Apache-2.0` (repo top-level `LICENSE`, copied here)
- **Shader files taken:** 1058 MSL source files
  - Source: the transpiler **reference outputs** under `reference/**` whose path
    contains `shaders-msl` (i.e. `reference/shaders-msl/`, `reference/shaders-msl-no-opt/`,
    `reference/opt/shaders-msl/`, `reference/opt/shaders-msl-no-opt/`). These are the
    expected Metal Shading Language emitted by SPIRV-Cross's own test suite; every file
    verified to contain Metal markers (`metal_stdlib` / `using namespace metal`).
  - Upstream keeps the original pipeline-stage extension on these MSL files
    (`.vert`, `.frag`, `.comp`, `.tesc`, `.tese`, `.mesh`, `.task`, plus `.aspN`/`.mslN`
    qualifiers). Each file was copied with `.msl` **appended** to its name (e.g.
    `pointsize.vert` -> `pointsize.vert.msl`) so the stage hint is preserved and the file
    is unambiguously MSL text. Content is byte-for-byte unmodified.
  - 1316 files matched; 258 exact byte-duplicates (mostly opt vs. no-opt emitting identical
    MSL) were de-duplicated, leaving 1058 unique files.
- **Excluded on purpose:** the `reference/shaders-ue4/**` category (Unreal-Engine-derived
  SPIR-V inputs) was NOT taken — although SPIRV-Cross ships it under Apache-2.0, its
  provenance is a third-party engine and is out of scope for a clean-room corpus. The
  `amd/` and `intel/` subdirs WERE included: those are SPIRV-Cross-authored test fixtures
  exercising vendor Vulkan *extensions* (e.g. `VK_AMD_shader_trinary_minmax`), not copied
  vendor code.

This is upstream third-party source, included unmodified as disassembler coverage-test
input, and retains its own Apache-2.0 license.
