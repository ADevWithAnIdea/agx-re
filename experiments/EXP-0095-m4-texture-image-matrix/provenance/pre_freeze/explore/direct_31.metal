#include <metal_stdlib>
using namespace metal;

kernel void k_direct_31(texture2d<float> t0 [[texture(0)]], texture2d<float> t1 [[texture(1)]], texture2d<float> t2 [[texture(2)]], texture2d<float> t3 [[texture(3)]], texture2d<float> t4 [[texture(4)]], texture2d<float> t5 [[texture(5)]], texture2d<float> t6 [[texture(6)]], texture2d<float> t7 [[texture(7)]], texture2d<float> t8 [[texture(8)]], texture2d<float> t9 [[texture(9)]], texture2d<float> t10 [[texture(10)]], texture2d<float> t11 [[texture(11)]], texture2d<float> t12 [[texture(12)]], texture2d<float> t13 [[texture(13)]], texture2d<float> t14 [[texture(14)]], texture2d<float> t15 [[texture(15)]], texture2d<float> t16 [[texture(16)]], texture2d<float> t17 [[texture(17)]], texture2d<float> t18 [[texture(18)]], texture2d<float> t19 [[texture(19)]], texture2d<float> t20 [[texture(20)]], texture2d<float> t21 [[texture(21)]], texture2d<float> t22 [[texture(22)]], texture2d<float> t23 [[texture(23)]], texture2d<float> t24 [[texture(24)]], texture2d<float> t25 [[texture(25)]], texture2d<float> t26 [[texture(26)]], texture2d<float> t27 [[texture(27)]], texture2d<float> t28 [[texture(28)]], texture2d<float> t29 [[texture(29)]], texture2d<float> t30 [[texture(30)]], constant uint& idx [[buffer(0)]], device float4* o [[buffer(1)]]) {
  float4 r = float4(0);
  if (idx == 0u) r = t0.read(uint2(0,0));
  if (idx == 1u) r = t1.read(uint2(0,0));
  if (idx == 2u) r = t2.read(uint2(0,0));
  if (idx == 3u) r = t3.read(uint2(0,0));
  if (idx == 4u) r = t4.read(uint2(0,0));
  if (idx == 5u) r = t5.read(uint2(0,0));
  if (idx == 6u) r = t6.read(uint2(0,0));
  if (idx == 7u) r = t7.read(uint2(0,0));
  if (idx == 8u) r = t8.read(uint2(0,0));
  if (idx == 9u) r = t9.read(uint2(0,0));
  if (idx == 10u) r = t10.read(uint2(0,0));
  if (idx == 11u) r = t11.read(uint2(0,0));
  if (idx == 12u) r = t12.read(uint2(0,0));
  if (idx == 13u) r = t13.read(uint2(0,0));
  if (idx == 14u) r = t14.read(uint2(0,0));
  if (idx == 15u) r = t15.read(uint2(0,0));
  if (idx == 16u) r = t16.read(uint2(0,0));
  if (idx == 17u) r = t17.read(uint2(0,0));
  if (idx == 18u) r = t18.read(uint2(0,0));
  if (idx == 19u) r = t19.read(uint2(0,0));
  if (idx == 20u) r = t20.read(uint2(0,0));
  if (idx == 21u) r = t21.read(uint2(0,0));
  if (idx == 22u) r = t22.read(uint2(0,0));
  if (idx == 23u) r = t23.read(uint2(0,0));
  if (idx == 24u) r = t24.read(uint2(0,0));
  if (idx == 25u) r = t25.read(uint2(0,0));
  if (idx == 26u) r = t26.read(uint2(0,0));
  if (idx == 27u) r = t27.read(uint2(0,0));
  if (idx == 28u) r = t28.read(uint2(0,0));
  if (idx == 29u) r = t29.read(uint2(0,0));
  if (idx == 30u) r = t30.read(uint2(0,0));
  o[0] = r;
}
