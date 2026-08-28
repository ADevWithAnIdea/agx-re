#include <metal_stdlib>
using namespace metal;

kernel void kread_n2(texture2d<uint, access::read> t0 [[texture(0)]],
                    texture2d<uint, access::read> t1 [[texture(1)]],
                    device uint *o [[buffer(0)]],
                    uint i [[thread_position_in_grid]]) {
    uint2 c = uint2(0,0);
    o[0] = t0.read(c).x + t1.read(c).x;
}
