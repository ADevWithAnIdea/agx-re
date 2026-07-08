#include <metal_stdlib>
using namespace metal;
kernel void k(device const int* a [[buffer(0)]],
              device int* o [[buffer(2)]],
              uint i [[thread_position_in_grid]]) {
    o[i] = a[i] + (2);
}
