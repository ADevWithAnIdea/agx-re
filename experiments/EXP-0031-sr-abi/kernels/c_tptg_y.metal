#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]],
              uint3 v [[threads_per_threadgroup]]) {
    out[0] = v.y;
}
