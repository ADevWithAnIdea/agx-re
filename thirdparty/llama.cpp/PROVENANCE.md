# Third-party source: llama.cpp / ggml (Metal compute backend)

- **Project:** ggerganov/llama.cpp (ggml)
- **Repo URL:** https://github.com/ggerganov/llama.cpp
- **Cloned commit:** `64c8b7db72fbd871512b371b5c141c00fd0a8ba6`
- **License (SPDX):** `MIT` (repo `LICENSE`, "The ggml authors", copied here)
- **Shader files taken:** 1 Metal source file
  - `ggml/src/ggml-metal/ggml-metal.metal` — the ggml Metal compute backend: a single
    large, hand-written MSL file packed with diverse GPU compute kernels (GEMM/GEMV,
    many quantization formats, softmax, RoPE, flash-attention, norms, etc.). Very high
    instruction-diversity per file. Path preserved relative to the repo root under
    `shaders/`. Content unmodified.

This is upstream third-party source, included unmodified as disassembler coverage-test
input, and retains its own MIT license.
