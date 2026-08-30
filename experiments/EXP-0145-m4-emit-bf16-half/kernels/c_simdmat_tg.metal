// EXP-0145 carrier -- AUTHORED BY US (clean-room OWN-SHADER).
#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]], device const float* a [[buffer(1)]],
              device const float* b [[buffer(2)]], device uint* sent [[buffer(4)]],
              threadgroup float* tg [[threadgroup(0)]], uint g [[thread_position_in_grid]]) {
    for (uint i = 0; i < 64; ++i) tg[i] = a[i];
    threadgroup_barrier(mem_flags::mem_threadgroup);
    simdgroup_float8x8 A, B, C;
    simdgroup_load(A, tg, 8);
    simdgroup_load(B, b, 8);
    simdgroup_multiply_accumulate(C, A, B, C);
    simdgroup_store(C, out, 8);
    sent[g] = 0xA5A5A5A5u;
}
