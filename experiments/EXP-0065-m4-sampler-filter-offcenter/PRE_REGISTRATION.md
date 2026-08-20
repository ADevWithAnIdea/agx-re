# EXP-0065 pre-registration — M4 off-center sampler filtering

Frozen before build/run. EXP-0063 showed its texel-center/out-of-range points
did not discriminate nearest from linear. This successor changes only the
second authored UV to in-range off-center `(.5,.25)` on the same asymmetric 2x2
RGBA8 texture, explicit LOD 0, and address/filter matrix.

Hypothesis: at least one in-range off-center sample differs between nearest and
linear in each of two M4 runs, while address-mode boundary outputs remain
finite. A missing difference, error, timeout, or cross-run mismatch is a stop.
Only public Metal, authored MSL/source, status, and full authored readback may
be retained. No Apple binary, archive, shader bytecode, BO, or helper data may
be captured/inspected. M4-only; no descriptor/native/A18 claim.
