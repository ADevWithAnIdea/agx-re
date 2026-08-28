#include <metal_stdlib>
using namespace metal;
// FS-10: can a dynamically-indexed fragment INPUT be lowered without changing
// interpolation mode? 4 named, distinctly-qualified varyings (v0 flat, v1/v2/v3 smooth,
// values 10..13) copied into a local array and indexed by a RUNTIME (buffer-sourced,
// not compile-time-foldable) index. Oracle: out == 10+idx for idx in [0,3]. Structural
// question (compile_scan): does the compiled fragment main still contain exactly 4
// `iter`/`iter_flat` ops (one per declared varying, unconditional, normal qualifier
// bits), i.e. does the compiler read ALL candidates every time and select afterward,
// rather than needing (or having) a genuine dynamic-slot iter?
struct VOut { float4 pos [[position]]; float v0 [[flat]]; float v1; float v2; float v3; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0);
    o.v0 = 10.0; o.v1 = 11.0; o.v2 = 12.0; o.v3 = 13.0;
    return o;
}
fragment float4 f_main(VOut in [[stage_in]], device uint *buf [[buffer(0)]],
                        constant uint2 &dims [[buffer(1)]]) {
    uint px = (uint)in.pos.x, py = (uint)in.pos.y;
    uint idx = py * dims.x + px;
    float arr[4] = { in.v0, in.v1, in.v2, in.v3 };
    uint sel = px % 4u;   // runtime, position-derived index (not compile-time-foldable)
    buf[idx] = as_type<uint>(arr[sel]);
    return float4(0,0,0,1);
}
