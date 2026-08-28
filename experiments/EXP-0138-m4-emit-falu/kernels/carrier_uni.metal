// EXP-0138 uniform-arm carrier. OWN MSL. Same long/low-pressure shape as
// carrier.metal, but ALSO declares a `constant float4&` so the shader
// container preloads the constant buffer into the UNIFORM register file --
// which is what the `mod_lo` uniform-source hypothesis needs live. The
// kernel's own arithmetic is never executed (every case replaces the whole
// `_agc.main` body); only the buffer bindings and the uniform preload matter.
#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              device float* mem [[buffer(1)]],
              constant float4& u [[buffer(2)]],
              uint tid [[thread_position_in_grid]]) {
    float acc = mem[tid + 0] + u.x + u.y * 2.0f + u.z * 3.0f + u.w * 4.0f;
    acc = acc * 1.0000001f + mem[tid + 1u];
    acc = acc * 1.0000001f + mem[tid + 2u];
    acc = acc * 1.0000001f + mem[tid + 3u];
    acc = acc * 1.0000001f + mem[tid + 4u];
    acc = acc * 1.0000001f + mem[tid + 5u];
    acc = acc * 1.0000001f + mem[tid + 6u];
    acc = acc * 1.0000001f + mem[tid + 7u];
    acc = acc * 1.0000001f + mem[tid + 8u];
    acc = acc * 1.0000001f + mem[tid + 9u];
    acc = acc * 1.0000001f + mem[tid + 10u];
    acc = acc * 1.0000001f + mem[tid + 11u];
    acc = acc * 1.0000001f + mem[tid + 12u];
    acc = acc * 1.0000001f + mem[tid + 13u];
    acc = acc * 1.0000001f + mem[tid + 14u];
    acc = acc * 1.0000001f + mem[tid + 15u];
    acc = acc * 1.0000001f + mem[tid + 16u];
    acc = acc * 1.0000001f + mem[tid + 17u];
    acc = acc * 1.0000001f + mem[tid + 18u];
    acc = acc * 1.0000001f + mem[tid + 19u];
    acc = acc * 1.0000001f + mem[tid + 20u];
    acc = acc * 1.0000001f + mem[tid + 21u];
    acc = acc * 1.0000001f + mem[tid + 22u];
    acc = acc * 1.0000001f + mem[tid + 23u];
    acc = acc * 1.0000001f + mem[tid + 24u];
    acc = acc * 1.0000001f + mem[tid + 25u];
    acc = acc * 1.0000001f + mem[tid + 26u];
    acc = acc * 1.0000001f + mem[tid + 27u];
    acc = acc * 1.0000001f + mem[tid + 28u];
    acc = acc * 1.0000001f + mem[tid + 29u];
    acc = acc * 1.0000001f + mem[tid + 30u];
    acc = acc * 1.0000001f + mem[tid + 31u];
    acc = acc * 1.0000001f + mem[tid + 32u];
    acc = acc * 1.0000001f + mem[tid + 33u];
    acc = acc * 1.0000001f + mem[tid + 34u];
    acc = acc * 1.0000001f + mem[tid + 35u];
    acc = acc * 1.0000001f + mem[tid + 36u];
    acc = acc * 1.0000001f + mem[tid + 37u];
    acc = acc * 1.0000001f + mem[tid + 38u];
    acc = acc * 1.0000001f + mem[tid + 39u];
    out[tid + 0] = acc;
}
