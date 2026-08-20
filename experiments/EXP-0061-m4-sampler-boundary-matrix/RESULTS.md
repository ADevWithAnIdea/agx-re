# EXP-0061 results

**STOPPED BEFORE GPU RUN.** The first append-only build failed because the
frozen authored Objective-C harness used `simd_float4` without importing its
host definition. `raw/m4-20260820-run01/00_inputs.json` binds the frozen inputs
before build; `01_build.json` preserves the compiler rejection. No probe binary
was produced, no Metal command ran, and no shader/archive/BO data was captured
or inspected. P1.3 remains open.

This failure must be corrected only by a separately preregistered successor.
Clean-room provenance: authored-source build record only; Apple binary
introspection: NONE.
