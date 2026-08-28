#include <metal_stdlib>
using namespace metal;

kernel void kread_n4(texture2d<uint, access::read> t0 [[texture(0)]],
                    texture2d<uint, access::read> t1 [[texture(1)]],
                    texture2d<uint, access::read> t2 [[texture(2)]],
                    texture2d<uint, access::read> t3 [[texture(3)]],
                    device uint *o [[buffer(0)]],
                    uint i [[thread_position_in_grid]]) {
    uint2 c = uint2(0,0);
    uint v0 = t0.read(c).x;
    uint v1 = t1.read(c).x;
    uint v2 = t2.read(c).x;
    uint v3 = t3.read(c).x;
    o[0] = v0; o[1] = v1; o[2] = v2; o[3] = v3;
}
