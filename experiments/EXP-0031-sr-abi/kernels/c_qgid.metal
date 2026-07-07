#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]],
              uint v [[quadgroup_index_in_threadgroup]]) {
    out[0] = v;
}
