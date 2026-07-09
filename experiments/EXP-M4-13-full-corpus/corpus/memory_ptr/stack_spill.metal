#include <metal_stdlib>
using namespace metal;
// Thread-local (stack) array dynamically indexed — forces register spill to
// the per-thread stack, surfacing stack load/store address modes.
kernel void k(device float* out [[buffer(0)]],
              device const uint* idx [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
    float local[16];
    for (uint t = 0; t < 16u; ++t) local[t] = float(t * i);
    uint a = idx[i] & 15u;
    uint b = (idx[i] >> 4) & 15u;
    local[a] += 3.0f;             // dynamic index -> stack store
    out[i] = local[a] * local[b]; // dynamic index -> stack load
}
