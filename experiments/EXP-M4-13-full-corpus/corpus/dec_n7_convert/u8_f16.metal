#include <metal_stdlib>
using namespace metal;
kernel void cvt(device half* o [[buffer(0)]],
                device const uchar* ib [[buffer(1)]],
                uint i [[thread_position_in_grid]]) {
    uchar a = ib[i];
    o[i] = half(a);
}
