#include <metal_stdlib>
using namespace metal;
// FS-11 negative/structural probe: attempt to write a fragment OUTPUT with a runtime-
// selected render-target index directly (an array of [[color(n)]] outputs indexed by a
// non-constant value). MSL's grammar requires each stage_out member's [[color(n)]]/
// [[color(n) index(m)]] to be an individually-named, compile-time-fixed field -- there
// is no array-of-color-attachments output syntax at all. This kernel therefore is
// EXPECTED to fail to compile (a structural/PUBLIC-API-surface negative result, not a
// hardware test): there is no Metal-exposed syntax to even ATTEMPT a dynamic output
// selector, so the compiler can never be asked to emit one from ordinary MSL source.
struct FOut { float4 colors[2]; };
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment FOut f_main(constant uint &idx [[buffer(0)]]) {
    FOut o;
    o.colors[idx] = float4(1,0,0,1);   // ILLEGAL: colors[] is not attribute-qualified
    return o;
}
