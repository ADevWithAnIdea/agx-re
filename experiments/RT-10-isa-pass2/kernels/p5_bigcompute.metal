#include <metal_stdlib>
using namespace metal;
// RT-10 Part5: BIG compute kernel — subgroup + matrix + divergent CF + textures + atomics,
// to measure census % over a broad realistic shader.
kernel void k(device float* out          [[buffer(0)]],
              device const float* aIn     [[buffer(1)]],
              device const float* bIn     [[buffer(2)]],
              device atomic_uint* counter [[buffer(3)]],
              device const uint* idx      [[buffer(4)]],
              texture2d<float> tex        [[texture(0)]],
              sampler samp                [[sampler(0)]],
              uint tid  [[thread_position_in_grid]],
              uint lane [[thread_index_in_simdgroup]]) {
    // --- matrix ---
    simdgroup_float8x8 A, B, C, D;
    simdgroup_load(A, aIn, 8);
    simdgroup_load(B, bIn, 8);
    C = simdgroup_float8x8(0.5f);
    simdgroup_multiply_accumulate(D, A, B, C);
    threadgroup float md[64];
    simdgroup_store(D, md, 8);
    float acc = md[lane & 63u];

    // --- texture sample ---
    float2 uv = float2((float)(tid & 15u) / 16.0f, (float)((tid >> 4) & 15u) / 16.0f);
    float4 t = tex.sample(samp, uv);
    acc += t.x + t.y * 2.0f;

    // --- divergent CF: switch + nested loops + break/continue ---
    uint sel = idx[tid] & 3u;
    switch (sel) {
        case 0:
            for (uint i = 0; i < (tid & 7u); i++) {
                if (i == 3u) continue;
                acc += (float)i * 1.5f;
            }
            break;
        case 1: {
            uint j = 0;
            while (j < 20u) {
                if (acc > 100.0f) break;
                acc += aIn[j & 7u];
                j++;
            }
            break;
        }
        case 2:
            acc = (acc < 0.0f) ? -acc : acc * 0.25f;
            break;
        default:
            acc -= 3.0f;
            break;
    }

    // --- subgroup reduce + shuffle + ballot ---
    float sg = simd_sum(acc);
    acc += simd_shuffle_xor(sg, 4);
    simd_vote v = simd_ballot(acc > 0.0f);
    if ((uint)((simd_vote::vote_t)v) & (1u << (lane & 31u))) {
        atomic_fetch_add_explicit(counter, 1u, memory_order_relaxed);
    }
    acc += simd_broadcast(acc, 0);

    out[tid] = acc;
}
