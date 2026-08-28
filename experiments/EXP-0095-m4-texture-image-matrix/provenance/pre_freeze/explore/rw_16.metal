#include <metal_stdlib>
using namespace metal;

kernel void k_rw16(texture_buffer<uint, access::read_write> t0 [[texture(0)]], texture_buffer<uint, access::read_write> t1 [[texture(1)]], texture_buffer<uint, access::read_write> t2 [[texture(2)]], texture_buffer<uint, access::read_write> t3 [[texture(3)]], texture_buffer<uint, access::read_write> t4 [[texture(4)]], texture_buffer<uint, access::read_write> t5 [[texture(5)]], texture_buffer<uint, access::read_write> t6 [[texture(6)]], texture_buffer<uint, access::read_write> t7 [[texture(7)]], texture_buffer<uint, access::read_write> t8 [[texture(8)]], texture_buffer<uint, access::read_write> t9 [[texture(9)]], texture_buffer<uint, access::read_write> t10 [[texture(10)]], texture_buffer<uint, access::read_write> t11 [[texture(11)]], texture_buffer<uint, access::read_write> t12 [[texture(12)]], texture_buffer<uint, access::read_write> t13 [[texture(13)]], texture_buffer<uint, access::read_write> t14 [[texture(14)]], texture_buffer<uint, access::read_write> t15 [[texture(15)]]) {
  t0.atomic_fetch_add(0u, uint4(1,0,0,0));
  t1.atomic_fetch_add(0u, uint4(1,0,0,0));
  t2.atomic_fetch_add(0u, uint4(1,0,0,0));
  t3.atomic_fetch_add(0u, uint4(1,0,0,0));
  t4.atomic_fetch_add(0u, uint4(1,0,0,0));
  t5.atomic_fetch_add(0u, uint4(1,0,0,0));
  t6.atomic_fetch_add(0u, uint4(1,0,0,0));
  t7.atomic_fetch_add(0u, uint4(1,0,0,0));
  t8.atomic_fetch_add(0u, uint4(1,0,0,0));
  t9.atomic_fetch_add(0u, uint4(1,0,0,0));
  t10.atomic_fetch_add(0u, uint4(1,0,0,0));
  t11.atomic_fetch_add(0u, uint4(1,0,0,0));
  t12.atomic_fetch_add(0u, uint4(1,0,0,0));
  t13.atomic_fetch_add(0u, uint4(1,0,0,0));
  t14.atomic_fetch_add(0u, uint4(1,0,0,0));
  t15.atomic_fetch_add(0u, uint4(1,0,0,0));
}
