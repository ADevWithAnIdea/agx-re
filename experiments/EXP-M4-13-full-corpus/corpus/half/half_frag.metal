// OWN-SHADER. Fragment-stage half math -> surfaces fragment ALU half encodings.
#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; half4 col; half2 uv; };
vertex VOut vMain(uint vid [[vertex_id]]) {
    VOut o;
    float x = (vid == 2) ? 3.0 : -1.0;
    float y = (vid == 1) ? 3.0 : -1.0;
    o.pos = float4(x, y, 0, 1);
    o.col = half4(half(x), half(y), 0.5h, 1.0h);
    o.uv  = half2(half(x)*0.5h + 0.5h, half(y)*0.5h + 0.5h);
    return o;
}
fragment half4 fMain(VOut in [[stage_in]]) {
    half2 uv = in.uv;
    half4 c  = in.col;
    half  t  = sin(uv.x) * cos(uv.y);        // half transcendentals in fragment
    half  s  = sqrt(fabs(uv.x*uv.y) + 0.01h);
    half4 r  = c * t + fma(c, c.wzyx, half4(s)); // packed half4 fragment ALU
    r = clamp(r, half4(0.0h), half4(1.0h));
    return r;
}
