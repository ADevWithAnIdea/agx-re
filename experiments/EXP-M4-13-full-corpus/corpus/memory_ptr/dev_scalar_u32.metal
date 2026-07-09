#include <metal_stdlib>
using namespace metal;
// Baseline: 32-bit scalar device load + store.
kernel void k(device uint* out [[buffer(0)]],
              device const uint* in [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
    out[i] = in[i] + 7u;
}
