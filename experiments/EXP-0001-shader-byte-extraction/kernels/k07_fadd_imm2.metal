#include <metal_stdlib>
using namespace metal;

// a + 2.0f. Minimal pair with k06_fadd_imm1 (only the immediate differs).
kernel void k(device const float *a [[buffer(0)]],
              device float *out [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + 2.0f;
}
