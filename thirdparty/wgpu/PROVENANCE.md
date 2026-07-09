# Third-party source: wgpu / naga (MSL backend outputs)

- **Project:** gfx-rs/wgpu
- **Repo URL:** https://github.com/gfx-rs/wgpu
- **Cloned commit:** `48904f8e769a9b1ef146032a4fc94c53a1e02e00`
- **License (SPDX):** `MIT OR Apache-2.0` (both `LICENSE.MIT` and `LICENSE.APACHE`
  copied here)
- **Shader files taken:** 119 Metal source files
  - 118 from `naga/tests/out/msl/*.metal` — the naga MSL-backend test expectation
    outputs (real transpiled Metal Shading Language).
  - 1 hand-written passthrough shader `tests/tests/wgpu-gpu/passthrough/shader.metal`.
  - Paths preserved relative to the repo root under `shaders/`. Content unmodified.
    No exact duplicates found.

This is upstream third-party source, included unmodified as disassembler coverage-test
input, and retains its own MIT/Apache-2.0 dual license.
