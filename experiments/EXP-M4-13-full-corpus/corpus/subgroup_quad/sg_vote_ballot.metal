#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    bool pred = a[i] > 100u;
    simd_vote bal = simd_ballot(pred);
    ulong m = (ulong)(simd_vote::vote_t)bal;
    o[i]    = (uint)m ^ (uint)(m >> 32);
    o[i+1u] = simd_all(pred) ? 1u : 0u;
    o[i+2u] = simd_any(pred) ? 1u : 0u;
    o[i+3u] = simd_is_first() ? 1u : 0u;
    simd_vote act = simd_active_threads_mask();
    ulong am = (ulong)(simd_vote::vote_t)act;
    o[i+4u] = (uint)am + (uint)(am >> 32);
}
