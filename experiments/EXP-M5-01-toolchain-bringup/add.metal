#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              const device float* a [[buffer(1)]],
              const device float* b [[buffer(2)]],
              uint i [[thread_position_in_grid]]) {
    out[i] = a[i] + b[i];
}
