#include <metal_stdlib>
using namespace metal;
// Clean-room fragment-stage float-ALU op-select probes. Isolates whether the
// fragment-only opsel 0b111 (byte+2 0x2f/0x3f) is a MULTIPLY and whether it is
// tied to perspective interpolation (varyings) vs plain uniform arithmetic.
// OUR OWN MSL (EXP-M4-13 R2, n9 family).

struct VOut { float4 pos [[position]]; float4 c; float2 uv; };

vertex VOut v_main(uint vid [[vertex_id]],
                   device const float4* p [[buffer(0)]],
                   device const float4* col [[buffer(1)]]) {
    VOut o; o.pos = p[vid]; o.c = col[vid]; o.uv = p[vid].xy; return o;
}

// varying * varying  -> expect fragment mul (opsel 0b111) if that op is a mul
fragment float4 f_mulvv(VOut in [[stage_in]]) { return in.c * in.uv.x; }
// varying + varying  -> add
fragment float4 f_addvv(VOut in [[stage_in]]) { return in.c + float4(in.uv, in.uv); }
// UNIFORM * UNIFORM (no varying / no perspective) -> does opsel stay 0b101 (compute-like) or 0b111?
fragment float4 f_muluu(constant float4& u [[buffer(0)]]) { return u * u.x; }
// UNIFORM + UNIFORM
fragment float4 f_adduu(constant float4& u [[buffer(0)]]) { return u + u.x; }
// flat (non-perspective, provoking-vertex) varying passthrough
struct VOutF { float4 pos [[position]]; float4 c [[flat]]; };
vertex VOutF vf_main(uint vid [[vertex_id]], device const float4* p [[buffer(0)]],
                     device const float4* col [[buffer(1)]]) {
    VOutF o; o.pos = p[vid]; o.c = col[vid]; return o;
}
fragment float4 f_flat(VOutF in [[stage_in]]) { return in.c; }
// center_no_perspective varying passthrough (linear, no rcp_w multiply)
struct VOutN { float4 pos [[position]]; float4 c [[center_no_perspective]]; };
vertex VOutN vn_main(uint vid [[vertex_id]], device const float4* p [[buffer(0)]],
                     device const float4* col [[buffer(1)]]) {
    VOutN o; o.pos = p[vid]; o.c = col[vid]; return o;
}
fragment float4 f_nopersp(VOutN in [[stage_in]]) { return in.c; }
// perspective varying passthrough (default) -> the rcp_w finalize multiply
fragment float4 f_persp(VOut in [[stage_in]]) { return in.c; }
