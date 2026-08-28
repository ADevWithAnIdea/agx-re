#include <metal_stdlib>
using namespace metal;
// OPT-07: can Apple9 directly read a varying/input whose slot is selected dynamically per
// lane? Builds on EXP-0111 FS-10 (4 candidates -> icmp_pred+sel over fixed-slot `iter`/
// `iter_flat` reads). This kernel widens the candidate set to 8 (v0 flat + v1..v7 smooth) to
// see whether a wider select tree changes the compiler's strategy (e.g. triggers a genuinely
// different, register-sourced `iter` variant once linear-scan cost grows). idx is derived from
// [[position]] (px % 8), i.e. a RUNTIME, non-compile-time-foldable, per-fragment index.
// Oracle: out == 200 + idx for idx in [0,7].
struct VOut {
    float4 pos [[position]];
    float v0 [[flat]];
    float v1; float v2; float v3; float v4; float v5; float v6; float v7;
};
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0);
    o.v0 = 200.0; o.v1 = 201.0; o.v2 = 202.0; o.v3 = 203.0;
    o.v4 = 204.0; o.v5 = 205.0; o.v6 = 206.0; o.v7 = 207.0;
    return o;
}
fragment float4 f_main(VOut in [[stage_in]], device uint *buf [[buffer(0)]],
                        constant uint2 &dims [[buffer(1)]]) {
    uint px = (uint)in.pos.x, py = (uint)in.pos.y;
    uint idx = py * dims.x + px;
    float arr[8] = { in.v0, in.v1, in.v2, in.v3, in.v4, in.v5, in.v6, in.v7 };
    uint sel = px % 8u;   // runtime, position-derived index
    buf[idx] = as_type<uint>(arr[sel]);
    return float4(0,0,0,1);
}
// Static-index control (same 8 declared varyings, compile-time-fixed index) -- isolates
// whether the compiler's `iter` shape itself (not the select tree) changes with candidate
// count, independent of dynamic indexing.
fragment float4 f_main_static(VOut in [[stage_in]], device uint *buf [[buffer(0)]],
                               constant uint2 &dims [[buffer(1)]]) {
    uint px = (uint)in.pos.x, py = (uint)in.pos.y;
    uint idx = py * dims.x + px;
    float arr[8] = { in.v0, in.v1, in.v2, in.v3, in.v4, in.v5, in.v6, in.v7 };
    buf[idx] = as_type<uint>(arr[5]);
    return float4(0,0,0,1);
}
