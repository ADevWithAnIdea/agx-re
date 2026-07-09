#include <metal_stdlib>
using namespace metal;
// Non-uniform / divergent indexing: each lane loads a data-dependent index,
// then gathers from a device buffer at that index (scatter store too).
kernel void k(device const uint* idx [[buffer(0)]],
              device const float* src [[buffer(1)]],
              device float* dst [[buffer(2)]],
              uint i [[thread_position_in_grid]]) {
    uint j = idx[i];
    float v = src[j];
    dst[j] = v + float(i);   // divergent scatter
}
