// EXP-0030 compute_emul.metal — OWN-SHADER software-mesh CONTROL.
// A plain compute kernel that manually writes the SAME primitives the mesh
// shader emits (3 vertices + 1 index-triple + a primitive count) into device
// buffers. This is what a *software* mesh-shading emulation would compile to
// (device stores, no dedicated mesh-output opcodes). Diffing the mesh-stage
// ISA against this control decides "dedicated mesh HW vs compute+buffer writes"
// — exactly the method EXP-0022 (matrix 0xcf) and EXP-0023 (RT 0x?4/ea) used.
//
// Clean-room: OUR OWN MSL; inspect only OUR OWN compiled bytes.
#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 position;
    float4 color;
};

kernel void emul_main(device VOut         *vbuf   [[buffer(0)]],
                      device uchar        *ibuf   [[buffer(1)]],
                      device atomic_uint  *pcount [[buffer(2)]],
                      constant float      &scale  [[buffer(3)]],
                      uint lane [[thread_position_in_grid]]) {
    if (lane >= 3) return;
    float2 P[3] = { float2(-0.5, -0.5), float2(0.5, -0.5), float2(0.0, 0.5) };
    VOut v;
    v.position = float4(P[lane] * scale, 0.0, 1.0);
    v.color    = float4(0.0, 1.0, 0.0, 1.0);
    vbuf[lane] = v;
    ibuf[lane] = uchar(lane);
    if (lane == 0)
        atomic_store_explicit(pcount, 1u, memory_order_relaxed);
}
