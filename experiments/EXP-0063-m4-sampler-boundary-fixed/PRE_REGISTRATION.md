# EXP-0063 pre-registration — corrected M4 sampler boundary matrix

Frozen before build/run. EXP-0061 is preserved as a pre-GPU host-build failure.
This successor changes only the authored host source by importing
`<simd/simd.h>` for `simd_float4`; its MSL, public 2x2 texture, UVs, sampler
matrix, readback, two-run requirement, and clean-room boundary are unchanged.

The matrix is clamp-to-zero/clamp-to-edge/repeat × nearest/linear at explicit
LOD 0 and four authored UVs. It is M4 public-Metal behavior only: no A18,
native descriptor, archive, binary, shader-bytecode, BO, or Apple-code claim.
Capture-time source/revision hashes precede every build. Any build/run error,
non-finite output, cross-run mismatch, or missing address/filter distinction is
a preserved stop.

Clean-room provenance: HW-PROBE / OWN-SHADER source. Apple binary
introspection: NONE.
