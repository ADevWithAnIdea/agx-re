#include <metal_stdlib>
using namespace metal;

kernel void k_1d_sample(texture1d<float> t [[texture(0)]], sampler s [[sampler(0)]], device float4* o [[buffer(0)]]) {
  o[0] = t.sample(s, 0.5);
}
kernel void k_1d_read(texture1d<float> t [[texture(0)]], device float4* o [[buffer(0)]]) {
  o[0] = t.read(0u);
}
kernel void k_1d_write(texture1d<float, access::write> t [[texture(0)]]) {
  t.write(float4(1,2,3,4), 0u);
}
kernel void k_1d_size(texture1d<float> t [[texture(0)]], device uint* o [[buffer(0)]]) {
  o[0] = t.get_width();
  o[1] = t.get_num_mip_levels();
}
kernel void k_1darr_sample(texture1d_array<float> t [[texture(0)]], sampler s [[sampler(0)]], device float4* o [[buffer(0)]]) {
  o[0] = t.sample(s, 0.5, 0u);
}
kernel void k_1darr_sample_layer_float(texture1d_array<float> t [[texture(0)]], sampler s [[sampler(0)]], constant float& layer [[buffer(1)]], device float4* o [[buffer(0)]]) {
  o[0] = t.sample(s, 0.5, uint(round(layer)));
}
kernel void k_1darr_read(texture1d_array<float> t [[texture(0)]], device float4* o [[buffer(0)]]) {
  o[0] = t.read(0u, 0u);
}
kernel void k_1darr_write(texture1d_array<float, access::write> t [[texture(0)]]) {
  t.write(float4(1,2,3,4), 0u, 0u);
}
kernel void k_1darr_size(texture1d_array<float> t [[texture(0)]], device uint* o [[buffer(0)]]) {
  o[0] = t.get_width();
  o[1] = t.get_array_size();
}
