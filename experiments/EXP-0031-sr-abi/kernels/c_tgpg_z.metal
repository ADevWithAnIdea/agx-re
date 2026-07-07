#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]],
              uint3 v [[threadgroups_per_grid]]) {
    out[0] = v.z;
}
