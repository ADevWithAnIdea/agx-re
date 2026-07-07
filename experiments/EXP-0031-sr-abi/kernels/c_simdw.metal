#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]],
              uint v [[threads_per_simdgroup]]) {
    out[0] = v;
}
