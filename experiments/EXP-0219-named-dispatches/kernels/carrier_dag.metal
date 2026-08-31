// EXP-0160 SYNTH carrier (authored by us; shape reused from EXP-0154, same project).
//
// Purpose: give `_agc.main` a region long enough that we can replace the WHOLE
// body with a program assembled by `tools/agx-isa`'s own field rules, while the
// Metal-side binding shape (buffer 0 = out, buffer 1 = float in, buffer 2 = int
// in) stays exactly what `tools/agxtest/agxrun_persist` binds.
//
// The body itself is never executed in a sweep case -- every case overwrites it.
// Only its LENGTH and its buffer bindings matter. Shape reused (not values) from
// EXP-0139 kernels/carrier_dag.metal, same project, same rules.
//
// CLEAN-ROOM: our own MSL. No Apple source consulted.
#include <metal_stdlib>
using namespace metal;

kernel void k(device float* out  [[buffer(0)]],
              device float* mem  [[buffer(1)]],
              device int*   imem [[buffer(2)]],
              uint tid [[thread_position_in_grid]]) {
    float acc = mem[tid + 0];
#define STEP(i) acc = acc * 1.0000001f + mem[tid + i##u];
    STEP(1)  STEP(2)  STEP(3)  STEP(4)  STEP(5)  STEP(6)  STEP(7)  STEP(8)
    STEP(9)  STEP(10) STEP(11) STEP(12) STEP(13) STEP(14) STEP(15) STEP(16)
    STEP(17) STEP(18) STEP(19) STEP(20) STEP(21) STEP(22) STEP(23) STEP(24)
    STEP(25) STEP(26) STEP(27) STEP(28) STEP(29) STEP(30) STEP(31) STEP(32)
    STEP(33) STEP(34) STEP(35) STEP(36) STEP(37) STEP(38) STEP(39) STEP(40)
    STEP(41) STEP(42) STEP(43) STEP(44) STEP(45) STEP(46) STEP(47) STEP(48)
    STEP(49) STEP(50) STEP(51) STEP(52) STEP(53) STEP(54) STEP(55) STEP(56)
    STEP(57) STEP(58) STEP(59) STEP(60) STEP(61) STEP(62) STEP(63) STEP(64)
#undef STEP
#define ISTEP(i) acc = acc - float(imem[tid + i##u]) * 0.0000001f;
    ISTEP(1) ISTEP(2) ISTEP(3) ISTEP(4) ISTEP(5) ISTEP(6) ISTEP(7) ISTEP(8)
    ISTEP(9) ISTEP(10) ISTEP(11) ISTEP(12) ISTEP(13) ISTEP(14) ISTEP(15)
#undef ISTEP
    out[tid + 0] = acc;
}
