#include <metal_stdlib>
using namespace metal;
kernel void cvt(device uint* o [[buffer(0)]],
                device const float* ib [[buffer(1)]],
                uint i [[thread_position_in_grid]]) {
    float a = ib[i];
    o[i] = uint(a);
}
