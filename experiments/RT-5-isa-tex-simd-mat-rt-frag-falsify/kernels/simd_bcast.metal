#include <metal_stdlib>
using namespace metal;

// simd_broadcast(v, 3): every lane receives lane 3's value = 3*10+5 = 35.
// Splice byte+6 (=lane<<1) to change the source lane: 0x00->lane0(=5),
// 0x0a->lane5(=55). Splice byte0 0x47->0xc7 (dir bit) to test broadcast vs xor.
kernel void k(device uint* out [[buffer(0)]],
              uint lane [[thread_index_in_threadgroup]]) {
    uint v = lane * 10 + 5;        // 5,15,25,...
    out[lane] = simd_broadcast(v, 3);
}
