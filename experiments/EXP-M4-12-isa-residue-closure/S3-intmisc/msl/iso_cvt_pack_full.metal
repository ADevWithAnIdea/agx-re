#include <metal_stdlib>
using namespace metal;
kernel void k_iso(device uint* o[[buffer(0)]], device const float2* a[[buffer(1)]], device const uint* p[[buffer(2)]], uint i[[thread_position_in_grid]]){
  uint packed = pack_float_to_unorm2x16(a[i]) + pack_float_to_snorm2x16(a[i]);
  float2 u = unpack_unorm2x16_to_float(p[i]) + unpack_snorm2x16_to_float(p[i]);
  o[i] = packed + as_type<uint>(u.x + u.y);
}
