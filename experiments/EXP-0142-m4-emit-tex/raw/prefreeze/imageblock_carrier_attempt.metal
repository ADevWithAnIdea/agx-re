#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
struct GB { half4 albedo [[color(0)]]; half4 normal [[color(1)]]; };
fragment void f_main(imageblock<GB, imageblock_layout_explicit> img,
                     float4 pos [[position]],
                     device const float *in [[buffer(0)]]) {
    GB v = img.read();
    v.albedo = v.albedo * half(in[0]) + half4(half(in[1]));
    v.normal = half4(half(in[2]));
    img.write(v);
}
