#include <metal_stdlib>
using namespace metal;

// a + 1.0f. Minimal pair with k07_fadd_imm2 (only the immediate differs):
// localizes where a float immediate is encoded.
kernel void k(device const float *a [[buffer(0)]],
              device float *out [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + 1.0f;
}
