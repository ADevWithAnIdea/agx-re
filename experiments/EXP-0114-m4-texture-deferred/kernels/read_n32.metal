#include <metal_stdlib>
using namespace metal;

kernel void kread_n32(
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
    texture2d<uint, access::read> t16 [[texture(16)]],
    texture2d<uint, access::read> t17 [[texture(17)]],
    texture2d<uint, access::read> t18 [[texture(18)]],
    texture2d<uint, access::read> t19 [[texture(19)]],
    texture2d<uint, access::read> t20 [[texture(20)]],
    texture2d<uint, access::read> t21 [[texture(21)]],
    texture2d<uint, access::read> t22 [[texture(22)]],
    texture2d<uint, access::read> t23 [[texture(23)]],
    texture2d<uint, access::read> t24 [[texture(24)]],
    texture2d<uint, access::read> t25 [[texture(25)]],
    texture2d<uint, access::read> t26 [[texture(26)]],
    texture2d<uint, access::read> t27 [[texture(27)]],
    texture2d<uint, access::read> t28 [[texture(28)]],
    texture2d<uint, access::read> t29 [[texture(29)]],
    texture2d<uint, access::read> t30 [[texture(30)]],
    texture2d<uint, access::read> t31 [[texture(31)]],
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
    acc += t16.read(c).x * 17u;
    acc += t17.read(c).x * 18u;
    acc += t18.read(c).x * 19u;
    acc += t19.read(c).x * 20u;
    acc += t20.read(c).x * 21u;
    acc += t21.read(c).x * 22u;
    acc += t22.read(c).x * 23u;
    acc += t23.read(c).x * 24u;
    acc += t24.read(c).x * 25u;
    acc += t25.read(c).x * 26u;
    acc += t26.read(c).x * 27u;
    acc += t27.read(c).x * 28u;
    acc += t28.read(c).x * 29u;
    acc += t29.read(c).x * 30u;
    acc += t30.read(c).x * 31u;
    acc += t31.read(c).x * 32u;
    o[0] = acc;
}
