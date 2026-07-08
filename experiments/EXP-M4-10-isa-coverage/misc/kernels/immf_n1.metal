#include <metal_stdlib>
using namespace metal;
kernel void k(device const float* a [[buffer(0)]],
              device float* o [[buffer(2)]],
              uint i [[thread_position_in_grid]]) {
    o[i] = a[i] + (-1.0f);
}
