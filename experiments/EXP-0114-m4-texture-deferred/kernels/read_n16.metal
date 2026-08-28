#include <metal_stdlib>
using namespace metal;

kernel void kread_n16(
    texture2d<uint, access::read> t0 [[texture(0)]],
    texture2d<uint, access::read> t1 [[texture(1)]],
    texture2d<uint, access::read> t2 [[texture(2)]],
    texture2d<uint, access::read> t3 [[texture(3)]],
    texture2d<uint, access::read> t4 [[texture(4)]],
    texture2d<uint, access::read> t5 [[texture(5)]],
    texture2d<uint, access::read> t6 [[texture(6)]],
    texture2d<uint, access::read> t7 [[texture(7)]],
    texture2d<uint, access::read> t8 [[texture(8)]],
    texture2d<uint, access::read> t9 [[texture(9)]],
    texture2d<uint, access::read> t10 [[texture(10)]],
    texture2d<uint, access::read> t11 [[texture(11)]],
    texture2d<uint, access::read> t12 [[texture(12)]],
    texture2d<uint, access::read> t13 [[texture(13)]],
    texture2d<uint, access::read> t14 [[texture(14)]],
    texture2d<uint, access::read> t15 [[texture(15)]],
    device uint *o [[buffer(0)]], uint i [[thread_position_in_grid]])
{
    uint2 c = uint2(0,0);
    uint acc = 0;
    acc += t0.read(c).x * 1u;
    acc += t1.read(c).x * 2u;
    acc += t2.read(c).x * 3u;
    acc += t3.read(c).x * 4u;
    acc += t4.read(c).x * 5u;
    acc += t5.read(c).x * 6u;
    acc += t6.read(c).x * 7u;
    acc += t7.read(c).x * 8u;
    acc += t8.read(c).x * 9u;
    acc += t9.read(c).x * 10u;
    acc += t10.read(c).x * 11u;
    acc += t11.read(c).x * 12u;
    acc += t12.read(c).x * 13u;
    acc += t13.read(c).x * 14u;
    acc += t14.read(c).x * 15u;
    acc += t15.read(c).x * 16u;
    o[0] = acc;
}
