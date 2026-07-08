#include <metal_stdlib>
using namespace metal;
kernel void k(device const float* a [[buffer(0)]],
              device const float* b [[buffer(1)]],
              device const float* c [[buffer(3)]],
              device float* o       [[buffer(2)]],
              uint i [[thread_position_in_grid]]) {
    float A=a[i], B=b[i], C=c[i]; (void)C;
    o[i] = fma(A,B,C);
}
