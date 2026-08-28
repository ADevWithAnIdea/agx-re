#include <metal_stdlib>
using namespace metal;

kernel void k_w16(texture2d<uint, access::write> t0 [[texture(0)]], texture2d<uint, access::write> t1 [[texture(1)]], texture2d<uint, access::write> t2 [[texture(2)]], texture2d<uint, access::write> t3 [[texture(3)]], texture2d<uint, access::write> t4 [[texture(4)]], texture2d<uint, access::write> t5 [[texture(5)]], texture2d<uint, access::write> t6 [[texture(6)]], texture2d<uint, access::write> t7 [[texture(7)]], texture2d<uint, access::write> t8 [[texture(8)]], texture2d<uint, access::write> t9 [[texture(9)]], texture2d<uint, access::write> t10 [[texture(10)]], texture2d<uint, access::write> t11 [[texture(11)]], texture2d<uint, access::write> t12 [[texture(12)]], texture2d<uint, access::write> t13 [[texture(13)]], texture2d<uint, access::write> t14 [[texture(14)]], texture2d<uint, access::write> t15 [[texture(15)]]) {
  t0.write(uint4(1,0,0,0), uint2(0,0));
  t1.write(uint4(1,0,0,0), uint2(0,0));
  t2.write(uint4(1,0,0,0), uint2(0,0));
  t3.write(uint4(1,0,0,0), uint2(0,0));
  t4.write(uint4(1,0,0,0), uint2(0,0));
  t5.write(uint4(1,0,0,0), uint2(0,0));
  t6.write(uint4(1,0,0,0), uint2(0,0));
  t7.write(uint4(1,0,0,0), uint2(0,0));
  t8.write(uint4(1,0,0,0), uint2(0,0));
  t9.write(uint4(1,0,0,0), uint2(0,0));
  t10.write(uint4(1,0,0,0), uint2(0,0));
  t11.write(uint4(1,0,0,0), uint2(0,0));
  t12.write(uint4(1,0,0,0), uint2(0,0));
  t13.write(uint4(1,0,0,0), uint2(0,0));
  t14.write(uint4(1,0,0,0), uint2(0,0));
  t15.write(uint4(1,0,0,0), uint2(0,0));
}
