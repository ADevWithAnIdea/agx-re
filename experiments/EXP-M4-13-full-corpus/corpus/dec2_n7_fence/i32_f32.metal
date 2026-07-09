#include <metal_stdlib>
using namespace metal;
kernel void cvt(device float* o [[buffer(0)]],
                device const int* ib [[buffer(1)]],
                uint i [[thread_position_in_grid]]) {
    int a = ib[i];
    o[i] = float(a);
}
