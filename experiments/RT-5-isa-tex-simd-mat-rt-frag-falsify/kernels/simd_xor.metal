#include <metal_stdlib>
using namespace metal;

// simd_shuffle_xor(v, 1): each lane gets its XOR-1 partner's value.
// v = lane*10+5, so out[lane] = (lane^1)*10+5. Swaps neighbours pairwise.
// Splice byte+6 (xor mask<<1) to change the mask: 0x02(mask1)->0x04(mask2).
kernel void k(device uint* out [[buffer(0)]],
              uint lane [[thread_index_in_threadgroup]]) {
    uint v = lane * 10 + 5;
    out[lane] = simd_shuffle_xor(v, 1);
}
