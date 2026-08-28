#include <metal_stdlib>
using namespace metal;

kernel void k_tb_read_r8(texture_buffer<float, access::read> t [[texture(0)]], constant uint& idx [[buffer(1)]], device float4* o [[buffer(0)]]) {
  o[0] = t.read(idx);
}
kernel void k_tb_write_r8(texture_buffer<float, access::write> t [[texture(0)]], constant uint& idx [[buffer(1)]]) {
  t.write(float4(1,0,0,0), idx);
}
kernel void k_tb_readwrite_r32uint_atomic(texture_buffer<uint, access::read_write> t [[texture(0)]], constant uint& idx [[buffer(1)]], device uint* o [[buffer(0)]]) {
  uint prev = atomic_fetch_add_explicit((device atomic_uint*)nullptr + 0, 1u, memory_order_relaxed);
  o[0] = prev;
}
kernel void k_tb_size(texture_buffer<float, access::read> t [[texture(0)]], device uint* o [[buffer(0)]]) {
  o[0] = t.get_width();
}
kernel void k_tb_read_rgb32(texture_buffer<float, access::read> t [[texture(0)]], device float4* o [[buffer(0)]]) {
  o[0] = t.read(0u);
}
