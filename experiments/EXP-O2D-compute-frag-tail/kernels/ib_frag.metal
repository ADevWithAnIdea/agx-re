#include <metal_stdlib>
using namespace metal;

// Explicit imageblock WRITE from a FRAGMENT shader (vs EXP-0029's implicit MRT
// struct return). Provokes the explicit imageblock write op + slice addressing.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}

struct GB {
    half4 albedo [[color(0)]];
    half4 normal [[color(1)]];
};

// explicit imageblock parameter, per-fragment write
fragment void f_ibwrite(imageblock<GB, imageblock_layout_explicit> img,
                        float4 pos [[position]]) {
    GB v;
    v.albedo = half4(0.5h, 0.25h, 0.125h, 1.0h);
    v.normal = half4(0.0h, 0.0h, 1.0h, 0.0h);
    img.write(v);
}

// explicit imageblock read-modify-write (blend) in a fragment
fragment void f_ibrmw(imageblock<GB, imageblock_layout_explicit> img,
                      float4 pos [[position]]) {
    GB v = img.read();
    v.albedo = v.albedo * 0.5h + half4(0.25h);
    img.write(v);
}
