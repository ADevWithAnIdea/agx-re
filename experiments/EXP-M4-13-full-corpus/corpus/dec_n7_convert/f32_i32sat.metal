#include <metal_stdlib>
using namespace metal;
kernel void cvt(device int* o [[buffer(0)]],
                device const float* ib [[buffer(1)]],
                uint i [[thread_position_in_grid]]) {
    float a = ib[i];
    o[i] = int(clamp(a,-2147483648.0,2147483647.0));
}
