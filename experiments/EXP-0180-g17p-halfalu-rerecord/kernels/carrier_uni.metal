// EXP-0180 SYNTH carrier `C_LO` (authored by us).
//
// Same "long body, never executed" role as carrier_dag.metal, but a DIFFERENT buffer
// signature: it also declares a `constant float4&`, so the shader container preloads the
// constant buffer into the UNIFORM register file. That is the dimension EXP-0087
// documented for read-back, and it is one of the four ways C_LO differs from C_HI
// (the others: a different seed permutation, a smaller-magnitude operand pair so
// `saturate` must be a no-op, 8 bytes of tail slack, and a second consumer of the
// block's source half-registers).
//
// Body shape copied from our own EXP-0169 kernels/carrier_uni.metal (itself our own
// EXP-0138 carrier), lengthened for EXP-0180's two-dump program.
// CLEAN-ROOM: our own MSL. No Apple source consulted.
#include <metal_stdlib>
using namespace metal;

kernel void k(device float* out [[buffer(0)]],
              device float* mem [[buffer(1)]],
              constant float4& u [[buffer(2)]],
              uint tid [[thread_position_in_grid]]) {
    float acc = mem[tid + 0] + u.x + u.y * 2.0f + u.z * 3.0f + u.w * 4.0f;
#define STEP(i) acc = acc * 1.0000001f + mem[tid + i##u];
#define STEP8(b) STEP(b+1) STEP(b+2) STEP(b+3) STEP(b+4) STEP(b+5) STEP(b+6) STEP(b+7) STEP(b+8)
    STEP8(0)   STEP8(8)   STEP8(16)  STEP8(24)  STEP8(32)  STEP8(40)  STEP8(48)  STEP8(56)
    STEP8(64)  STEP8(72)  STEP8(80)  STEP8(88)  STEP8(96)  STEP8(104) STEP8(112) STEP8(120)
    STEP8(128) STEP8(136) STEP8(144) STEP8(152) STEP8(160) STEP8(168) STEP8(176) STEP8(184)
#undef STEP8
#undef STEP
    out[tid + 0] = acc;
}
