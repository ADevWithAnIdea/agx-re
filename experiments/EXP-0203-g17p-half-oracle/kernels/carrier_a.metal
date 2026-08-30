// EXP-0203 SYNTH carrier `A` (authored by us).
//
// Role: provide an `_agc.main` region long enough that the WHOLE body can be replaced by a
// program assembled from `tools/agx-isa`'s own field rules, while the Metal-side binding
// shape (buffer 0 = out, buffer 1 = float in, buffer 2 = int in) stays exactly what
// `tools/agxtest/agxrun_persist` binds. The body is NEVER executed in a sweep case -- every
// case overwrites it; only its LENGTH and its buffer bindings matter.
//
// Shape (not values) reused from our own EXP-0180 kernels/carrier_dag.metal.
// CLEAN-ROOM: our own MSL. No Apple source consulted.
#include <metal_stdlib>
using namespace metal;

kernel void k(device float* out  [[buffer(0)]],
              device float* mem  [[buffer(1)]],
              device int*   imem [[buffer(2)]],
              uint tid [[thread_position_in_grid]]) {
    float acc = mem[tid + 0];
#define STEP(i) acc = acc * 1.0000001f + mem[tid + i##u];
#define STEP8(b) STEP(b+1) STEP(b+2) STEP(b+3) STEP(b+4) STEP(b+5) STEP(b+6) STEP(b+7) STEP(b+8)
    STEP8(0)   STEP8(8)   STEP8(16)  STEP8(24)  STEP8(32)  STEP8(40)  STEP8(48)  STEP8(56)
    STEP8(64)  STEP8(72)  STEP8(80)  STEP8(88)  STEP8(96)  STEP8(104) STEP8(112) STEP8(120)
    STEP8(128) STEP8(136) STEP8(144) STEP8(152) STEP8(160) STEP8(168) STEP8(176) STEP8(184)
#undef STEP8
#undef STEP
#define ISTEP(i) acc = acc - float(imem[tid + i##u]) * 0.0000001f;
    ISTEP(1)  ISTEP(2)  ISTEP(3)  ISTEP(4)  ISTEP(5)  ISTEP(6)  ISTEP(7)  ISTEP(8)
    ISTEP(9)  ISTEP(10) ISTEP(11) ISTEP(12) ISTEP(13) ISTEP(14) ISTEP(15) ISTEP(16)
    ISTEP(17) ISTEP(18) ISTEP(19) ISTEP(20) ISTEP(21) ISTEP(22) ISTEP(23) ISTEP(24)
    ISTEP(25) ISTEP(26) ISTEP(27) ISTEP(28) ISTEP(29) ISTEP(30) ISTEP(31) ISTEP(32)
#undef ISTEP
    out[tid + 0] = acc;
}
