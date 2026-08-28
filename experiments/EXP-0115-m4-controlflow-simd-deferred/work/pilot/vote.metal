#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid], 0, 1); return o;
}
fragment float4 f_ballot_baseline(VOut in [[stage_in]]) {
    uint64_t m = (uint64_t)simd_active_threads_mask();
    uint pc = popcount((uint)(m & 0xffffffffu));
    return float4(float(pc) / 255.0, 0.0, 0.0, 1.0);
}
fragment float4 f_ballot_onediscard(VOut in [[stage_in]]) {
    int x = (int)in.pos.x, y = (int)in.pos.y;
    if (x == 0 && y == 0) { discard_fragment(); }
    uint64_t m = (uint64_t)simd_active_threads_mask();
    uint pc = popcount((uint)(m & 0xffffffffu));
    return float4(float(pc) / 255.0, 0.0, 0.0, 1.0);
}
// control: divergent RETURN (no discard) at the same pixel -- does it ALSO jump popcount by 8?
fragment float4 f_ballot_onereturn(VOut in [[stage_in]]) {
    int x = (int)in.pos.x, y = (int)in.pos.y;
    if (x == 0 && y == 0) { return float4(0,1,0,1); }
    uint64_t m = (uint64_t)simd_active_threads_mask();
    uint pc = popcount((uint)(m & 0xffffffffu));
    return float4(float(pc) / 255.0, 0.0, 0.0, 1.0);
}
