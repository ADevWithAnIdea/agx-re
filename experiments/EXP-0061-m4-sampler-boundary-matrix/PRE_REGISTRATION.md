# EXP-0061 pre-registration — M4 sampler boundary matrix

Frozen before build/run. Target is local Apple M4 only; no A18, native driver,
or descriptor-byte claim is made. P1.3 asks for texture/image behavior needed
by a compiler/driver. This public-Metal probe bounds only sampled color results
for a tiny authored texture at explicit LOD 0.

An authored 2x2 RGBA8 texture has four distinct texels. An authored compute MSL
samples UV `(-.25,.25),(.25,.25),(.75,.75),(1.25,.25)` for each cartesian pair:
address mode `clampToZero`, `clampToEdge`, `repeat`; filter `nearest`, `linear`.
Every process writes all 24 float4 outputs to an authored shared buffer and
prints complete values. Two append-only runs are required.

Hypothesis: out-of-range samples distinguish the three address modes; nearest
and linear differ for at least one non-edge sample. Falsified by command error,
non-finite output, cross-run mismatch, absent expected address-mode distinction,
or no filter distinction. Results are public API behavior only; they do not
identify an AGX descriptor encoding, prove native Vulkan semantics, sample
precision beyond these points, image writes, mip choice beyond explicit LOD 0,
or hardware/A18 behavior.

Only authored Objective-C/MSL, public Metal/Foundation API status, and authored
readback are inspected. No binary, archive, shader bytecode, BO, data trace,
or Apple helper/framework contents may be captured or inspected. A capture-time
input record binds the preregistration, runner, and harness hashes/revision
before build. Raw output is append-only.

Clean-room provenance: HW-PROBE / OWN-SHADER source. Apple binary
introspection: NONE.
