#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid], 0, 1); return o;
}
// pred false only at the discarding pixel (0,0); if that lane's contribution
// still counts (helper-lane-included), simd_all should read FALSE for survivors
// (since one "active" lane -- the demoted one -- has pred=false); if excluded,
// TRUE.
fragment float4 f_all_baseline(VOut in [[stage_in]]) {
    int x = (int)in.pos.x, y = (int)in.pos.y;
    bool pred = !(x == 0 && y == 0);
    bool r = simd_all(pred);
    return float4(r ? 1.0 : 0.0, 0.0, 0.0, 1.0);
}
fragment float4 f_all_onediscard(VOut in [[stage_in]]) {
    int x = (int)in.pos.x, y = (int)in.pos.y;
    bool pred = !(x == 0 && y == 0);
    if (x == 0 && y == 0) { discard_fragment(); }
    bool r = simd_all(pred);
    return float4(r ? 1.0 : 0.0, 0.0, 0.0, 1.0);
}
// pred true ONLY at discarding pixel; if included, simd_any should read TRUE
// for survivors; if excluded, FALSE.
fragment float4 f_any_onediscard(VOut in [[stage_in]]) {
    int x = (int)in.pos.x, y = (int)in.pos.y;
    bool pred = (x == 0 && y == 0);
    if (x == 0 && y == 0) { discard_fragment(); }
    bool r = simd_any(pred);
    return float4(r ? 1.0 : 0.0, 0.0, 0.0, 1.0);
}
