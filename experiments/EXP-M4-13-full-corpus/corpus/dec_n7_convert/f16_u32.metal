#include <metal_stdlib>
using namespace metal;
kernel void cvt(device uint* o [[buffer(0)]],
                device const half* ib [[buffer(1)]],
                uint i [[thread_position_in_grid]]) {
    half a = ib[i];
    o[i] = uint(a);
}
