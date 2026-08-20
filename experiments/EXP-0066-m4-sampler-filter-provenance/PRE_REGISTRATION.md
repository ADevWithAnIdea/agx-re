# EXP-0066 pre-registration — M4 sampler filter provenance contract

Frozen before builds. Two fresh M4 public-Metal runs sample the authored 2x2
texture at off-center `(.5,.25)` using zero/edge/repeat × nearest/linear,
explicit LOD 0. Every run records pre-build Git/source hashes, argv, environment
overrides, timeouts, build/run outputs, and full transcript. No binary, archive,
shader bytecode, BO, or Apple helper is retained/inspected. M4-only public API
behavior; no descriptor/native/A18 claim. Missing record or mismatch is a stop.
