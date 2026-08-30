// EXP-0179 SYNTH carrier (authored by us).
//
// Purpose: give `_agc.main` a region long enough that we can replace the WHOLE
// body with a program assembled by `tools/agx-isa`'s own field rules -- seeds,
// a GENERATED call, a GENERATED callee placed past the `stop`, and a GENERATED
// return -- while the Metal-side binding shape (buffer 0 = out, buffer 1 = float
// in, buffer 2 = int in) stays exactly what `tools/agxtest/agxrun_persist` binds.
//
// The body below is NEVER executed in a sweep case -- every case overwrites it.
// Only its LENGTH and its buffer bindings matter. Required length (worst arm):
//   32 seeds + 20 PRE sentinel + 4 if_push + 14 call + 6 reconverge + 2 marker
//   + 274 dump + 4 stop + up to 96 gap + 8 ladder + ~40 callee + 4 stop
//   ~= 505 B, so the chain is sized to comfortably exceed it;
// `harness/isa_helpers.build_program` pads whatever is left with 2-byte writes
// of a register's OWN seed, which is a no-op with respect to the register dump.
//
// Shape reused (not values) from EXP-0174/kernels/carrier_n3.metal, which took
// it from EXP-0168/kernels/carrier_dag.metal -- same project, same rules.
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
    STEP(1) STEP(2) STEP(3) STEP(4) STEP(5) STEP(6) STEP(7) STEP(8)
    STEP(9) STEP(10) STEP(11) STEP(12) STEP(13) STEP(14) STEP(15) STEP(16)
    STEP(17) STEP(18) STEP(19) STEP(20) STEP(21) STEP(22) STEP(23) STEP(24)
    STEP(25) STEP(26) STEP(27) STEP(28) STEP(29) STEP(30) STEP(31) STEP(32)
    STEP(33) STEP(34) STEP(35) STEP(36) STEP(37) STEP(38) STEP(39) STEP(40)
    STEP(41) STEP(42) STEP(43) STEP(44) STEP(45) STEP(46) STEP(47) STEP(48)
    STEP(49) STEP(50) STEP(51) STEP(52) STEP(53) STEP(54) STEP(55) STEP(56)
    STEP(57) STEP(58) STEP(59) STEP(60) STEP(61) STEP(62) STEP(63) STEP(64)
    STEP(65) STEP(66) STEP(67) STEP(68) STEP(69) STEP(70) STEP(71) STEP(72)
    STEP(73) STEP(74) STEP(75) STEP(76) STEP(77) STEP(78) STEP(79) STEP(80)
    STEP(81) STEP(82) STEP(83) STEP(84) STEP(85) STEP(86) STEP(87) STEP(88)
    STEP(89) STEP(90) STEP(91) STEP(92) STEP(93) STEP(94) STEP(95) STEP(96)
    STEP(97) STEP(98) STEP(99) STEP(100) STEP(101) STEP(102) STEP(103) STEP(104)
    STEP(105) STEP(106) STEP(107) STEP(108) STEP(109) STEP(110) STEP(111) STEP(112)
    STEP(113) STEP(114) STEP(115) STEP(116) STEP(117) STEP(118) STEP(119) STEP(120)
    STEP(121) STEP(122) STEP(123) STEP(124) STEP(125) STEP(126) STEP(127) STEP(128)
    STEP(129) STEP(130) STEP(131) STEP(132) STEP(133) STEP(134) STEP(135) STEP(136)
    STEP(137) STEP(138) STEP(139) STEP(140) STEP(141) STEP(142) STEP(143) STEP(144)
    STEP(145) STEP(146) STEP(147) STEP(148) STEP(149) STEP(150) STEP(151) STEP(152)
    STEP(153) STEP(154) STEP(155) STEP(156) STEP(157) STEP(158) STEP(159) STEP(160)
#undef STEP
#define ISTEP(i) acc = acc - float(imem[tid + i##u]) * 0.0000001f;
    ISTEP(1) ISTEP(2) ISTEP(3) ISTEP(4) ISTEP(5) ISTEP(6) ISTEP(7) ISTEP(8)
    ISTEP(9) ISTEP(10) ISTEP(11) ISTEP(12) ISTEP(13) ISTEP(14) ISTEP(15) ISTEP(16)
    ISTEP(17) ISTEP(18) ISTEP(19) ISTEP(20) ISTEP(21) ISTEP(22) ISTEP(23) ISTEP(24)
    ISTEP(25) ISTEP(26) ISTEP(27) ISTEP(28) ISTEP(29) ISTEP(30) ISTEP(31) ISTEP(32)
    ISTEP(33) ISTEP(34) ISTEP(35) ISTEP(36) ISTEP(37) ISTEP(38) ISTEP(39) ISTEP(40)
#undef ISTEP
    out[tid + 0] = acc;
}
