#include <metal_stdlib>
using namespace metal;
// Swizzle stress: reverse (.wzyx), broadcast (.yyyy), interleave (.xzxz),
// sub-vector extract (.xy/.zw), rotate via constructor, and a write-masked
// swizzle store (out.zw = ...). Exercises register move/shuffle encodings.
kernel void k(device float4* o [[buffer(0)]],
              device const float4* a [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
    float4 x   = a[i];
    float4 rev = x.wzyx;
    float4 bc  = x.yyyy;
    float4 mix = x.xzxz;
    float2 lo  = x.xy;
    float2 hi  = x.zw;
    float4 rot = float4(x.yzw, x.x);
    float4 out = rev + bc + mix + rot + float4(lo, hi);
    out.zw = x.xy;              // masked partial write
    o[i] = out;
}
