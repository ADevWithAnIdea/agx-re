# Third-party source: PyTorch (MPS Metal kernels)

- **Project:** pytorch/pytorch
- **Repo URL:** https://github.com/pytorch/pytorch
- **Cloned commit:** `e7206c023e2ca33746ca37a1d5eab45a54f8fe93`
- **License (SPDX):** `BSD-3-Clause` (repo `LICENSE`, copied here)
- **Shader files taken:** 48 Metal source files
  - 44 from `aten/src/ATen/native/mps/kernels/*.metal` — hand-written Metal Performance
    Shaders compute kernels for the MPS backend (activation, attention, binary/unary
    elementwise, convolution, indexing, layer/group/RMS norm, pooling, quantization,
    reductions, scan, scatter/gather, sort, etc.).
  - 3 from `aten/src/ATen/native/sparse/mps/kernels/*.metal` (sparse tensor ops).
  - 1 from `test/metal/test_kernels.metal`.
  - Paths preserved relative to the repo root under `shaders/`. Content unmodified;
    no exact duplicates. Fetched via a `blob:none` sparse checkout of the kernel dirs.

This is upstream third-party source, included unmodified as disassembler coverage-test
input, and retains its own BSD-3-Clause license.
