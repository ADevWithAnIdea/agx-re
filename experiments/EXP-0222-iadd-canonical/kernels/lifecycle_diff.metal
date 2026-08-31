#include <metal_stdlib>
using namespace metal;

// Authored after AMENDMENT-01. These kernels nominate lifecycle bits only;
// their instruction bytes are never copied into the generated recipe.

kernel void add_dead(device const uint *in [[buffer(0)]],
                     device uint *out [[buffer(1)]],
                     uint tid [[thread_position_in_grid]])
{
    uint ii = tid * 2u;
    uint oi = tid * 3u;
    uint a = in[ii + 0u];
    uint b = in[ii + 1u];
    uint c = a + b;
    out[oi + 0u] = c;
    out[oi + 1u] = c + 17u;
    out[oi + 2u] = c ^ 0x5a5a5a5au;
}

kernel void add_live(device const uint *in [[buffer(0)]],
                     device uint *out [[buffer(1)]],
                     uint tid [[thread_position_in_grid]])
{
    uint ii = tid * 2u;
    uint oi = tid * 3u;
    uint a = in[ii + 0u];
    uint b = in[ii + 1u];
    uint c = a + b;
    out[oi + 0u] = c;
    out[oi + 1u] = a + 17u;
    out[oi + 2u] = b ^ 0x5a5a5a5au;
}

kernel void sub_live(device const uint *in [[buffer(0)]],
                     device uint *out [[buffer(1)]],
                     uint tid [[thread_position_in_grid]])
{
    uint ii = tid * 2u;
    uint oi = tid * 3u;
    uint a = in[ii + 0u];
    uint b = in[ii + 1u];
    uint c = a - b;
    out[oi + 0u] = c;
    out[oi + 1u] = a + 17u;
    out[oi + 2u] = b ^ 0x5a5a5a5au;
}
