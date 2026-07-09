#include <metal_stdlib>
using namespace metal;
kernel void k(device half2* out [[buffer(0)]],
              const device half2* a [[buffer(1)]],
              const device half2* b [[buffer(2)]],
              uint i [[thread_position_in_grid]]) {
    out[i] = a[i] + b[i];
}
