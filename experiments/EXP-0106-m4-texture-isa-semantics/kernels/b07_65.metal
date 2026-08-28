// EXP-0106 generated file -- DO NOT HAND-EDIT. Regenerate with
// `python3 gen_b07.py` (deterministic, no arguments). OWN-SHADER:
// authored by our own generator, compiled at runtime via
// -[MTLDevice newLibraryWithSource:options:], no Apple binary involved.
#include <metal_stdlib>
using namespace metal;

kernel void k_b07_tex65(device uint* out [[buffer(0)]], texture2d<uint> t0 [[texture(0)]], texture2d<uint> t1 [[texture(1)]], texture2d<uint> t2 [[texture(2)]], texture2d<uint> t3 [[texture(3)]], texture2d<uint> t4 [[texture(4)]], texture2d<uint> t5 [[texture(5)]], texture2d<uint> t6 [[texture(6)]], texture2d<uint> t7 [[texture(7)]], texture2d<uint> t8 [[texture(8)]], texture2d<uint> t9 [[texture(9)]], texture2d<uint> t10 [[texture(10)]], texture2d<uint> t11 [[texture(11)]], texture2d<uint> t12 [[texture(12)]], texture2d<uint> t13 [[texture(13)]], texture2d<uint> t14 [[texture(14)]], texture2d<uint> t15 [[texture(15)]], texture2d<uint> t16 [[texture(16)]], texture2d<uint> t17 [[texture(17)]], texture2d<uint> t18 [[texture(18)]], texture2d<uint> t19 [[texture(19)]], texture2d<uint> t20 [[texture(20)]], texture2d<uint> t21 [[texture(21)]], texture2d<uint> t22 [[texture(22)]], texture2d<uint> t23 [[texture(23)]], texture2d<uint> t24 [[texture(24)]], texture2d<uint> t25 [[texture(25)]], texture2d<uint> t26 [[texture(26)]], texture2d<uint> t27 [[texture(27)]], texture2d<uint> t28 [[texture(28)]], texture2d<uint> t29 [[texture(29)]], texture2d<uint> t30 [[texture(30)]], texture2d<uint> t31 [[texture(31)]], texture2d<uint> t32 [[texture(32)]], texture2d<uint> t33 [[texture(33)]], texture2d<uint> t34 [[texture(34)]], texture2d<uint> t35 [[texture(35)]], texture2d<uint> t36 [[texture(36)]], texture2d<uint> t37 [[texture(37)]], texture2d<uint> t38 [[texture(38)]], texture2d<uint> t39 [[texture(39)]], texture2d<uint> t40 [[texture(40)]], texture2d<uint> t41 [[texture(41)]], texture2d<uint> t42 [[texture(42)]], texture2d<uint> t43 [[texture(43)]], texture2d<uint> t44 [[texture(44)]], texture2d<uint> t45 [[texture(45)]], texture2d<uint> t46 [[texture(46)]], texture2d<uint> t47 [[texture(47)]], texture2d<uint> t48 [[texture(48)]], texture2d<uint> t49 [[texture(49)]], texture2d<uint> t50 [[texture(50)]], texture2d<uint> t51 [[texture(51)]], texture2d<uint> t52 [[texture(52)]], texture2d<uint> t53 [[texture(53)]], texture2d<uint> t54 [[texture(54)]], texture2d<uint> t55 [[texture(55)]], texture2d<uint> t56 [[texture(56)]], texture2d<uint> t57 [[texture(57)]], texture2d<uint> t58 [[texture(58)]], texture2d<uint> t59 [[texture(59)]], texture2d<uint> t60 [[texture(60)]], texture2d<uint> t61 [[texture(61)]], texture2d<uint> t62 [[texture(62)]], texture2d<uint> t63 [[texture(63)]], texture2d<uint> t64 [[texture(64)]]) {
  out[0] = t0.read(uint2(0, 0)).x;
  out[1] = t7.read(uint2(0, 0)).x;
  out[2] = t8.read(uint2(0, 0)).x;
  out[3] = t15.read(uint2(0, 0)).x;
  out[4] = t16.read(uint2(0, 0)).x;
  out[5] = t31.read(uint2(0, 0)).x;
  out[6] = t32.read(uint2(0, 0)).x;
  out[7] = t63.read(uint2(0, 0)).x;
  out[8] = t64.read(uint2(0, 0)).x;
}

