#include <metal_stdlib>
#include <metal_simdgroup_matrix>
using namespace metal;
// Large compute kernel exercising subgroup + matrix + atomics + memory, to
// stress the tokenizer/DB over many instruction families in one _agc.main.
kernel void k(device float* A [[buffer(0)]],
              device float* B [[buffer(1)]],
              device float* Dout [[buffer(2)]],
              device atomic_uint* ctr [[buffer(3)]],
              device uint* red [[buffer(4)]],
              texture2d<float> tex [[texture(0)]],
              sampler samp [[sampler(0)]],
              uint tid [[thread_position_in_grid]],
              uint lane [[thread_index_in_threadgroup]]) {
    // subgroup
    uint s = simd_sum(lane);
    uint p = simd_prefix_inclusive_sum(lane);
    uint b = simd_broadcast(lane, 0);
    uint x = simd_shuffle_xor(lane, 1);
    uint m = (uint)((simd_vote::vote_t)simd_ballot(lane < 8));
    // matrix
    simdgroup_float8x8 a,bb,c,d;
    simdgroup_load(a, A, 8);
    simdgroup_load(bb, B, 8);
    simdgroup_multiply_accumulate(d, a, bb, c);
    simdgroup_store(d, Dout, 8);
    // atomics + texture + memory
    atomic_fetch_add_explicit(ctr, s + p + b + x + m, memory_order_relaxed);
    float4 t = tex.sample(samp, float2(0.5,0.5));
    red[tid] = s ^ p ^ b ^ x ^ m ^ (uint)(t.x*255.0);
}
