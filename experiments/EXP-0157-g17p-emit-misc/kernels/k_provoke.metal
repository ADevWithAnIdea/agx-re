#include <metal_stdlib>
using namespace metal;
// EXP-0157 (OWN-SHADER) provocation set. Five of the dispatched MISC
// descriptors -- n2_op8, coord_madf, h_coord_hi, h_coord_hi_ext,
// mesh_out_src -- appear in NONE of the carriers reused from EXP-0145/0146
// when those are recompiled on G17P. Each kernel below is a targeted attempt
// to make the G17P compiler emit one of them, so the census below is itself a
// result: a descriptor that no own-MSL provocation can produce on this target
// has no carrier, and its fields cannot be swept (FIELD-SWEEP-PROTOCOL 3.2).
// Every kernel writes its result to out[] so that, if the target instruction
// does appear, it is already on a live output path.

// ---- n2_op8: db.json calls it the transcendental SFU RANGE-REDUCTION select
// (byte+1 == 0xc2, byte+2 in {0x19,0x29,0x49,0x59}). EXP-0146 found it in
// fast::sin on M4/G16G; G17P's fast::sin does not emit it. Try the rest of
// the transcendental surface.
kernel void k_sfu_cos (device const float*a[[buffer(0)]],device float*o[[buffer(1)]],uint g[[thread_position_in_grid]]){ o[g]=fast::cos(a[g]); }
kernel void k_sfu_tan (device const float*a[[buffer(0)]],device float*o[[buffer(1)]],uint g[[thread_position_in_grid]]){ o[g]=fast::tan(a[g]); }
kernel void k_sfu_psin(device const float*a[[buffer(0)]],device float*o[[buffer(1)]],uint g[[thread_position_in_grid]]){ o[g]=precise::sin(a[g]); }
kernel void k_sfu_sincos(device const float*a[[buffer(0)]],device float*o[[buffer(1)]],uint g[[thread_position_in_grid]]){ o[g]=fast::sin(a[g])+fast::cos(a[g])+fast::tan(a[g]); }
kernel void k_sfu_exp (device const float*a[[buffer(0)]],device float*o[[buffer(1)]],uint g[[thread_position_in_grid]]){ o[g]=fast::exp(a[g])+fast::log(a[g])+fast::pow(a[g],1.5f); }
kernel void k_sfu_atan(device const float*a[[buffer(0)]],device float*o[[buffer(1)]],uint g[[thread_position_in_grid]]){ o[g]=precise::atan2(a[g],a[g]+1.0f)+precise::asin(fract(a[g]))+precise::acos(fract(a[g])); }
kernel void k_sfu_rsq (device const float*a[[buffer(0)]],device float*o[[buffer(1)]],uint g[[thread_position_in_grid]]){ o[g]=rsqrt(a[g])+precise::sqrt(a[g])+fast::divide(1.0f,a[g]); }

// ---- h_coord_hi / h_coord_hi_ext: 6- and 8-byte HALF ops whose destination
// is the HIGH 16-bit half of a register, op-select 0x26 (2-source mul) /
// 0x2e (fused mul-add). "Emitted by half-precision geometry / interpolation."
kernel void k_h2_fma (device const half2*a[[buffer(0)]],device const half2*b[[buffer(1)]],device half2*o[[buffer(2)]],uint g[[thread_position_in_grid]]){ half2 x=a[g],y=b[g]; o[g]=fma(x,y,x.yx); }
kernel void k_h4_fma (device const half4*a[[buffer(0)]],device const half4*b[[buffer(1)]],device half4*o[[buffer(2)]],uint g[[thread_position_in_grid]]){ half4 x=a[g],y=b[g]; o[g]=fma(x,y.wzyx,x.wzyx)*y.yxwz; }
kernel void k_h2_coord(device const half2*a[[buffer(0)]],device const half2*b[[buffer(1)]],device half2*o[[buffer(2)]],uint g[[thread_position_in_grid]]){
    half2 uv=a[g], sz=b[g]; half2 t=uv*sz+half2(0.5h,0.5h); o[g]=half2(t.y*sz.x+uv.y, t.x*sz.y+uv.x); }
kernel void k_h3_mix (device const half3*a[[buffer(0)]],device const half3*b[[buffer(1)]],device half3*o[[buffer(2)]],uint g[[thread_position_in_grid]]){ half3 x=a[g],y=b[g]; o[g]=mix(x,y,half3(0.25h))*fma(x,y,y.zxy); }

// ---- coord_madf: byte0-LEADER 0x2e, byte+2 == 0x23, 10 bytes. Provenance
// (EXP-0037) is the CUBE / ARRAY normalized-coordinate generation path.
kernel void k_tex_cube (texturecube<float> t[[texture(0)]], sampler s[[sampler(0)]],
                        device const float3*c[[buffer(0)]], device float4*o[[buffer(1)]],
                        uint g[[thread_position_in_grid]]){ o[g]=t.sample(s,normalize(c[g])); }
kernel void k_tex_cubearr(texturecube_array<float> t[[texture(0)]], sampler s[[sampler(0)]],
                          device const float4*c[[buffer(0)]], device float4*o[[buffer(1)]],
                          uint g[[thread_position_in_grid]]){ float4 v=c[g]; o[g]=t.sample(s,normalize(v.xyz),uint(v.w)); }
kernel void k_tex_3d   (texture3d<float> t[[texture(0)]], sampler s[[sampler(0)]],
                        device const float3*c[[buffer(0)]], device float4*o[[buffer(1)]],
                        uint g[[thread_position_in_grid]]){ float3 v=c[g]; o[g]=t.sample(s,v*0.5f+0.5f); }
kernel void k_tex_2darr(texture2d_array<float> t[[texture(0)]], sampler s[[sampler(0)]],
                        device const float4*c[[buffer(0)]], device float4*o[[buffer(1)]],
                        uint g[[thread_position_in_grid]]){ float4 v=c[g]; o[g]=t.sample(s,v.xy*v.zw+v.yx,uint(v.w)); }
