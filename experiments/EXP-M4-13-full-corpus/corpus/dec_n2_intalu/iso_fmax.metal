#include <metal_stdlib>
using namespace metal;
kernel void m(device float* o[[buffer(0)]],
              device const float* a[[buffer(1)]],
              device const float* b[[buffer(2)]],
              uint i[[thread_position_in_grid]]) {
    o[i] = max(a[i], b[i]);
}
