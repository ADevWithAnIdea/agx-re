#include <metal_stdlib>
using namespace metal;
// EXP-0157 (OWN-SHADER) second provocation round for the two descriptors that
// NO own-MSL kernel emits on G17P: `n2_op8` (which EXP-0146 found in fast::sin
// on M4/G16G) and `coord_madf` (EXP-0037's cube/array coordinate-generation
// form). A descriptor that survives two independent rounds of targeted
// provocation on this target has no carrier, and that is a result.
kernel void k_sfu_sinpi(device const float*a[[buffer(0)]],device float*o[[buffer(1)]],uint g[[thread_position_in_grid]]){ o[g]=precise::sinpi(a[g])+precise::cospi(a[g])+precise::tanpi(a[g]); }
kernel void k_sfu_hsin (device const half*a[[buffer(0)]],device half*o[[buffer(1)]],uint g[[thread_position_in_grid]]){ o[g]=fast::sin(a[g])+fast::cos(a[g]); }
kernel void k_sfu_big  (device const float*a[[buffer(0)]],device float*o[[buffer(1)]],uint g[[thread_position_in_grid]]){ float x=a[g]*1024.0f; o[g]=fast::sin(x)+fast::cos(x*3.0f)+fast::tan(x*7.0f); }
kernel void k_sfu_hyp  (device const float*a[[buffer(0)]],device float*o[[buffer(1)]],uint g[[thread_position_in_grid]]){ o[g]=precise::sinh(a[g])+precise::cosh(a[g])+precise::tanh(a[g])+precise::atan(a[g]); }
kernel void k_sfu_mod  (device const float*a[[buffer(0)]],device float*o[[buffer(1)]],uint g[[thread_position_in_grid]]){ float ip; o[g]=modf(a[g],ip)+ip+fract(a[g])+fmod(a[g],3.0f); }
kernel void k_tex_cmp  (depth2d<float> t[[texture(0)]], sampler s[[sampler(0)]], device const float4*c[[buffer(0)]], device float*o[[buffer(1)]], uint g[[thread_position_in_grid]]){ float4 v=c[g]; o[g]=t.sample_compare(s,v.xy,v.z); }
kernel void k_tex_gath (texturecube<float> t[[texture(0)]], sampler s[[sampler(0)]], device const float4*c[[buffer(0)]], device float4*o[[buffer(1)]], uint g[[thread_position_in_grid]]){ float4 v=c[g]; o[g]=t.gather(s,normalize(v.xyz)); }
kernel void k_tex_lod  (texturecube_array<float> t[[texture(0)]], sampler s[[sampler(0)]], device const float4*c[[buffer(0)]], device float4*o[[buffer(1)]], uint g[[thread_position_in_grid]]){ float4 v=c[g]; o[g]=t.sample(s,normalize(v.xyz),uint(v.w),level(v.w*0.25f)); }
kernel void k_tex_grad (texturecube<float> t[[texture(0)]], sampler s[[sampler(0)]], device const float4*c[[buffer(0)]], device float4*o[[buffer(1)]], uint g[[thread_position_in_grid]]){ float4 v=c[g]; float3 d=normalize(v.xyz); o[g]=t.sample(s,d,gradientcube(d*0.01f,d*0.02f)); }
kernel void k_tex_3dw  (texture3d<float,access::read_write> t[[texture(0)]], device const float4*c[[buffer(0)]], device float4*o[[buffer(1)]], uint g[[thread_position_in_grid]]){ float4 v=c[g]; uint3 p=uint3(uint(v.x),uint(v.y),uint(v.z)); o[g]=t.read(p); t.write(v,p); }
