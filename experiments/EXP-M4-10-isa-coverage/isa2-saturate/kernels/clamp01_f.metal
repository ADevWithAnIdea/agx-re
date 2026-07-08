#include <metal_stdlib>
using namespace metal;
kernel void k(device const float* a [[buffer(0)]],
              device const float* b [[buffer(1)]],
              device float* o       [[buffer(2)]],
              uint i [[thread_position_in_grid]]) {
    o[i] = clamp(a[i] + b[i], 0.0f, 1.0f);
}
