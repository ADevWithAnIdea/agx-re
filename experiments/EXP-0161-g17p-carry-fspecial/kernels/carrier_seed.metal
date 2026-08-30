// EXP-0161 SYNTH carrier (authored by us).
//
// Purpose: give `_agc.main` a region long enough that the WHOLE body can be
// replaced by a program assembled from `tools/agx-isa`'s own field rules, while
// the Metal-side binding shape stays exactly what `tools/agxtest/agxrun_persist`
// binds:  buffer(0) = read-back (poisoned before every dispatch),
//         buffer(1) = the SEED vector this experiment loads r0..r14 from.
//
// The body itself never executes in a sweep case -- every case overwrites the
// whole region. Only its LENGTH and its buffer bindings matter. Shape (not
// values) reused from EXP-0139/EXP-0154 `carrier_dag.metal`, same project.
//
// CLEAN-ROOM: our own MSL.
#include <metal_stdlib>
using namespace metal;

kernel void k(device uint *out        [[buffer(0)]],
              device const uint *seed [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    uint acc = seed[tid];
#define STEP(i) acc = acc * 2654435761u + seed[tid + i##u];
    STEP(1)  STEP(2)  STEP(3)  STEP(4)  STEP(5)  STEP(6)  STEP(7)  STEP(8)
    STEP(9)  STEP(10) STEP(11) STEP(12) STEP(13) STEP(14) STEP(15) STEP(16)
    STEP(17) STEP(18) STEP(19) STEP(20) STEP(21) STEP(22) STEP(23) STEP(24)
    STEP(25) STEP(26) STEP(27) STEP(28) STEP(29) STEP(30) STEP(31) STEP(32)
    STEP(33) STEP(34) STEP(35) STEP(36) STEP(37) STEP(38) STEP(39) STEP(40)
    STEP(41) STEP(42) STEP(43) STEP(44) STEP(45) STEP(46) STEP(47) STEP(48)
    STEP(49) STEP(50) STEP(51) STEP(52) STEP(53) STEP(54) STEP(55) STEP(56)
    STEP(57) STEP(58) STEP(59) STEP(60) STEP(61) STEP(62) STEP(63) STEP(64)
    STEP(65) STEP(66) STEP(67) STEP(68) STEP(69) STEP(70) STEP(71) STEP(72)
    STEP(73) STEP(74) STEP(75) STEP(76) STEP(77) STEP(78) STEP(79) STEP(80)
#undef STEP
    out[tid] = acc;
}
