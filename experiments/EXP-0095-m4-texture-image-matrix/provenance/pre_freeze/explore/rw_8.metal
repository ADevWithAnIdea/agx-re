#include <metal_stdlib>
using namespace metal;

kernel void k_rw8(texture_buffer<uint, access::read_write> t0 [[texture(0)]], texture_buffer<uint, access::read_write> t1 [[texture(1)]], texture_buffer<uint, access::read_write> t2 [[texture(2)]], texture_buffer<uint, access::read_write> t3 [[texture(3)]], texture_buffer<uint, access::read_write> t4 [[texture(4)]], texture_buffer<uint, access::read_write> t5 [[texture(5)]], texture_buffer<uint, access::read_write> t6 [[texture(6)]], texture_buffer<uint, access::read_write> t7 [[texture(7)]]) {
  t0.atomic_fetch_add(0u, uint4(1,0,0,0));
  t1.atomic_fetch_add(0u, uint4(1,0,0,0));
  t2.atomic_fetch_add(0u, uint4(1,0,0,0));
  t3.atomic_fetch_add(0u, uint4(1,0,0,0));
  t4.atomic_fetch_add(0u, uint4(1,0,0,0));
  t5.atomic_fetch_add(0u, uint4(1,0,0,0));
  t6.atomic_fetch_add(0u, uint4(1,0,0,0));
  t7.atomic_fetch_add(0u, uint4(1,0,0,0));
}
