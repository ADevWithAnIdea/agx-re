#include <metal_stdlib>
using namespace metal;
// RT-10 Part1: ONE corpus that emits ballot(0x17/+1=0x17), active-mask(0x17/+1=0x07),
// broadcast+shuffle_xor(0x47/0xc7 byte+2=0x54), and unpack_convert(0x17/+1=0x04) together,
// to prove there is NO collision when all coexist in a single _agc.main.
kernel void k(device uint* out [[buffer(0)]],
              device const uint* in [[buffer(1)]],
              uint tid  [[thread_position_in_grid]],
              uint lane [[thread_index_in_simdgroup]]) {
    uint v = in[tid];
    uint acc = 0u;
    // ballot(predicate)  -> 0x17, byte+1 = 0x17
    simd_vote b = simd_ballot((v & 7u) > 3u);
    acc ^= (uint)((simd_vote::vote_t)b);
    // active-mask        -> 0x17, byte+1 = 0x07
    simd_vote a = simd_active_threads_mask();
    acc ^= (uint)((simd_vote::vote_t)a) << 1;
    // broadcast          -> 0x47, byte+2 = 0x54
    acc += simd_broadcast(v, 5);
    // shuffle_xor        -> 0xc7, byte+2 = 0x54
    acc += simd_shuffle_xor(v, 2);
    // unpack_convert     -> 0x17, byte+1 = 0x04
    float2 f = unpack_unorm2x16_to_float(v);
    acc += (uint)(f.x * 255.0f) + (uint)(f.y * 255.0f);
    out[tid] = acc;
}
