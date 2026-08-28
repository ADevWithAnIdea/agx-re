#include <metal_stdlib>
using namespace metal;

// depth2d_array
kernel void k_d2darr_compare(depth2d_array<float> t [[texture(0)]], sampler s [[sampler(0)]], device float* o [[buffer(0)]]) {
  o[0] = t.sample_compare(s, float2(0.5,0.5), 0u, 0.5);
}
kernel void k_d2darr_compare_level(depth2d_array<float> t [[texture(0)]], sampler s [[sampler(0)]], device float* o [[buffer(0)]]) {
  o[0] = t.sample_compare(s, float2(0.5,0.5), 0u, 0.5, level(0.0));
}
kernel void k_d2darr_compare_bias(depth2d_array<float> t [[texture(0)]], sampler s [[sampler(0)]], device float* o [[buffer(0)]]) {
  o[0] = t.sample_compare(s, float2(0.5,0.5), 0u, 0.5, bias(0.5));
}
kernel void k_d2darr_compare_grad(depth2d_array<float> t [[texture(0)]], sampler s [[sampler(0)]], device float* o [[buffer(0)]]) {
  o[0] = t.sample_compare(s, float2(0.5,0.5), 0u, 0.5, gradient2d(float2(0.01,0), float2(0,0.01)));
}
kernel void k_d2darr_compare_offset(depth2d_array<float> t [[texture(0)]], sampler s [[sampler(0)]], device float* o [[buffer(0)]]) {
  o[0] = t.sample_compare(s, float2(0.5,0.5), 0u, 0.5, level(0.0), int2(1,0));
}
kernel void k_d2darr_gather_compare(depth2d_array<float> t [[texture(0)]], sampler s [[sampler(0)]], device float4* o [[buffer(0)]]) {
  o[0] = t.gather_compare(s, float2(0.5,0.5), 0u, 0.5);
}
// depthcube
kernel void k_dcube_compare(depthcube<float> t [[texture(0)]], sampler s [[sampler(0)]], device float* o [[buffer(0)]]) {
  o[0] = t.sample_compare(s, float3(1,0,0), 0.5);
}
kernel void k_dcube_gather_compare(depthcube<float> t [[texture(0)]], sampler s [[sampler(0)]], device float4* o [[buffer(0)]]) {
  o[0] = t.gather_compare(s, float3(1,0,0), 0.5);
}
// depthcube_array
kernel void k_dcubearr_compare(depthcube_array<float> t [[texture(0)]], sampler s [[sampler(0)]], device float* o [[buffer(0)]]) {
  o[0] = t.sample_compare(s, float3(1,0,0), 0u, 0.5);
}
kernel void k_dcubearr_compare_level(depthcube_array<float> t [[texture(0)]], sampler s [[sampler(0)]], device float* o [[buffer(0)]]) {
  o[0] = t.sample_compare(s, float3(1,0,0), 0u, 0.5, level(0.0));
}
kernel void k_dcubearr_compare_bias(depthcube_array<float> t [[texture(0)]], sampler s [[sampler(0)]], device float* o [[buffer(0)]]) {
  o[0] = t.sample_compare(s, float3(1,0,0), 0u, 0.5, bias(0.5));
}
kernel void k_dcubearr_gather_compare(depthcube_array<float> t [[texture(0)]], sampler s [[sampler(0)]], device float4* o [[buffer(0)]]) {
  o[0] = t.gather_compare(s, float3(1,0,0), 0u, 0.5);
}
// non-shadow ordinary sample/gather for same dims, to compare footprints/LOD
kernel void k_2darr_sample(texture2d_array<float> t [[texture(0)]], sampler s [[sampler(0)]], device float4* o [[buffer(0)]]) {
  o[0] = t.sample(s, float2(0.5,0.5), 0u);
}
kernel void k_2darr_gather(texture2d_array<float> t [[texture(0)]], sampler s [[sampler(0)]], device float4* o [[buffer(0)]]) {
  o[0] = t.gather(s, float2(0.5,0.5), 0u);
}
kernel void k_cubearr_sample(texturecube_array<float> t [[texture(0)]], sampler s [[sampler(0)]], device float4* o [[buffer(0)]]) {
  o[0] = t.sample(s, float3(1,0,0), 0u);
}
kernel void k_cubearr_gather(texturecube_array<float> t [[texture(0)]], sampler s [[sampler(0)]], device float4* o [[buffer(0)]]) {
  o[0] = t.gather(s, float3(1,0,0), 0u);
}
