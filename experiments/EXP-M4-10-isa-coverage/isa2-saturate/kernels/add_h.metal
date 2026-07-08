#include <metal_stdlib>
using namespace metal;
kernel void k(device const half* a [[buffer(0)]],
              device const half* b [[buffer(1)]],
              device half* o        [[buffer(2)]],
              uint i [[thread_position_in_grid]]) {
    o[i] = a[i] + b[i];
}
