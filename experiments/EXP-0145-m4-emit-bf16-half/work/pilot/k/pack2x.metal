#include <metal_stdlib>
using namespace metal;
kernel void k(device uint2* out [[buffer(0)]], device const float4* a [[buffer(1)]], uint g [[thread_position_in_grid]]){ float4 v=a[g]; half2 lo=half2(v.xy)+half2(1.0h); half2 hi=half2(v.zw)*half2(2.0h); out[g]=uint2(as_type<uint>(lo),as_type<uint>(hi)); }
