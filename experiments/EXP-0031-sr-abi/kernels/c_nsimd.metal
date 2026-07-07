#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]],
              uint v [[simdgroups_per_threadgroup]]) {
    out[0] = v;
}
