# Third-party source: Dawn / Tint (MSL test expectations)

- **Project:** google/dawn (Tint shader compiler test suite)
- **Repo URL:** https://github.com/google/dawn
- **Cloned commit:** `a5c62978bcb5c767959066f00b85adce333342f3`
- **License (SPDX):** `BSD-3-Clause`
  - Dawn's `LICENSE` is a DEP5-style file. The default stanza (`Files: *`) is
    3-clause BSD ("The Dawn & Tint Authors"); a few unrelated subdirs
    (`generator/templates/art/*`, `tools/android/webgpu/*`) are Apache-2.0. Every file
    we took lives under `test/tint/**`, which falls under the default `Files: *`
    BSD-3-Clause stanza. The full `LICENSE` is copied here.
- **Shader files taken:** 11812 MSL source files
  - Source: `test/tint/**/*.wgsl.expected.msl` — Tint's Metal-backend test expectation
    outputs (real emitted Metal Shading Language), fetched via a `blob:none` sparse
    checkout of `test/tint`. Paths preserved relative to the repo root under `shaders/`.
    Content unmodified.
  - 13082 files matched; 1270 exact byte-duplicates were de-duplicated, leaving 11812
    unique files. This is a very broad, machine-generated corpus (texture load/store,
    subgroup/subgroup-matrix, atomics, builtins, packing, etc.) — high-value for
    exercising many distinct instruction encodings.

This is upstream third-party source, included unmodified as disassembler coverage-test
input, and retains its own BSD-3-Clause license.
