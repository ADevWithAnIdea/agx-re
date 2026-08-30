// EXP-0179 census: an out-of-line call from the FRAGMENT stage. P0.8 is a
// VS/FS/CS ABI row, so "can a fragment shader make a call" is directly on it.
// CLEAN-ROOM: our own MSL.
#include <metal_stdlib>
using namespace metal;

struct VOut { float4 pos [[position]]; float2 uv; };

vertex VOut v_main(uint vid [[vertex_id]]) {
    VOut o;
    float2 p = float2((vid == 2) ? 3.0f : -1.0f, (vid == 1) ? 3.0f : -1.0f);
    o.pos = float4(p, 0.0f, 1.0f);
    o.uv = p * 0.5f + 0.5f;
    return o;
}

// C23 noinline helper called from a fragment shader.
__attribute__((noinline))
static float4 f_help(float2 uv, float k) {
    return float4(uv.x * k, uv.y * k, uv.x + uv.y, k);
}
fragment float4 f_main(VOut in [[stage_in]],
                       constant float& k [[buffer(0)]]) {
    return f_help(in.uv, k);
}
