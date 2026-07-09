#include <metal_stdlib>
using namespace metal;
// Four INDEPENDENT fma results, all live simultaneously at the float4 pack ->
// the register allocator must place x,y,z,w in FOUR DISTINCT registers.
// If byte0[4:8] (the high nibble) is the destination register field, the four
// fma instructions carry four distinct, typically incrementing, high nibbles.
kernel void k_fma_dst(device float4* out [[buffer(0)]],
                      device const float* a [[buffer(1)]],
                      uint gid [[thread_position_in_grid]]) {
    float x = fma(a[gid+0], a[gid+1],  a[gid+2]);
    float y = fma(a[gid+3], a[gid+4],  a[gid+5]);
    float z = fma(a[gid+6], a[gid+7],  a[gid+8]);
    float w = fma(a[gid+9], a[gid+10], a[gid+11]);
    out[gid] = float4(x, y, z, w);
}
