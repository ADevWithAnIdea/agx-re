#include <metal_stdlib>
using namespace metal;

kernel void k_2d_atomic_add_uint(texture2d<uint, access::read_write> t [[texture(0)]], device uint4* o [[buffer(0)]]) {
  o[0] = t.atomic_fetch_add(uint2(0,0), uint4(1,0,0,0));
}
kernel void k_2d_atomic_cmpxchg_uint(texture2d<uint, access::read_write> t [[texture(0)]], device uint4* o [[buffer(0)]]) {
  uint4 expected = uint4(0,0,0,0);
  bool ok = t.atomic_compare_exchange_weak(uint2(0,0), &expected, uint4(7,0,0,0));
  o[0] = uint4(ok ? 1u : 0u, expected.x, 0, 0);
}
kernel void k_1d_atomic_add_uint(texture1d<uint, access::read_write> t [[texture(0)]], device uint4* o [[buffer(0)]]) {
  o[0] = t.atomic_fetch_add(0u, uint4(1,0,0,0));
}
kernel void k_1darr_atomic_add_uint(texture1d_array<uint, access::read_write> t [[texture(0)]], device uint4* o [[buffer(0)]]) {
  o[0] = t.atomic_fetch_add(0u, 0u, uint4(1,0,0,0));
}
kernel void k_2darr_atomic_add_uint(texture2d_array<uint, access::read_write> t [[texture(0)]], device uint4* o [[buffer(0)]]) {
  o[0] = t.atomic_fetch_add(uint2(0,0), 0u, uint4(1,0,0,0));
}
kernel void k_3d_atomic_add_uint(texture3d<uint, access::read_write> t [[texture(0)]], device uint4* o [[buffer(0)]]) {
  o[0] = t.atomic_fetch_add(uint3(0,0,0), uint4(1,0,0,0));
}
kernel void k_cube_atomic_add_uint(texturecube<uint, access::read_write> t [[texture(0)]], device uint4* o [[buffer(0)]]) {
  o[0] = t.atomic_fetch_add(uint2(0,0), 0u, uint4(1,0,0,0));
}
kernel void k_cubearr_atomic_add_uint(texturecube_array<uint, access::read_write> t [[texture(0)]], device uint4* o [[buffer(0)]]) {
  o[0] = t.atomic_fetch_add(uint2(0,0), 0u, 0u, uint4(1,0,0,0));
}
kernel void k_tb_atomic_add_uint(texture_buffer<uint, access::read_write> t [[texture(0)]], device uint4* o [[buffer(0)]]) {
  o[0] = t.atomic_fetch_add(0u, uint4(1,0,0,0));
}
