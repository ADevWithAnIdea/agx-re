#include <metal_stdlib>
using namespace metal;

// out[i] = a[i] * b[i]  — reference kernel: the "ground truth" compiler output
// for multiply, to compare against splicing add's op-select 1c->1d.
kernel void k(device const float *a [[buffer(0)]],
              device const float *b [[buffer(1)]],
              device float *out [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] * b[gid];
}
