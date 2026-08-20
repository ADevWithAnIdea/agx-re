# EXP-0063 results

**PARTIAL PUBLIC-METAL OBSERVATION; FILTER HYPOTHESIS FALSIFIED.** Two M4 runs
match exactly and show address-mode distinctions at out-of-range UVs: clamp to
zero returns zero, clamp to edge returns edge texels, and repeat wraps to the
opposite edge for this 2×2 authored texture at explicit LOD 0.

Nearest and linear outputs are identical at every selected UV. The frozen
filter-distinction hypothesis is therefore falsified: all UVs were texel-center
or out-of-range points that do not discriminate interpolation. This experiment
makes no filter rule, descriptor encoding, native/Vulkan, A18, or BO claim.
Raw public outputs are retained in both `raw/m4-20260820-run*/02_run.json`.
No binary/archive/shader-bytecode/BO artifact was retained or inspected.
