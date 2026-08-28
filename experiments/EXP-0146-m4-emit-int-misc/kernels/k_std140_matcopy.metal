#include <metal_stdlib>
using namespace metal;
// EXP-0146 P4 carrier search: EXP-M4-13 located int_alu_ehi (0xef) only in std140-shaped
// uniform->storage matrix copies from committed permissively licensed Dawn/Tint shaders and
// recorded that OUR OWN MSL emits 0x9f (iadd) instead. This is an own-MSL attempt at the same
// shape (a std140-padded uniform matrix copied element-wise into a storage matrix).
struct Std140Mat4 { float4 c0; float4 c1; float4 c2; float4 c3; };
kernel void k(constant Std140Mat4 *u [[buffer(0)]],
              device float4x4 *outm  [[buffer(1)]],
              device uint *idx       [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    uint i = idx[gid] & 3u;
    Std140Mat4 s = u[i];
    float4x4 m;
    m[0] = s.c0; m[1] = s.c1; m[2] = s.c2; m[3] = s.c3;
    outm[gid] = m;
}
