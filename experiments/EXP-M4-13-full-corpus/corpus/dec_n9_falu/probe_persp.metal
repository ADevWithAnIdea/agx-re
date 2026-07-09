#include <metal_stdlib>
using namespace metal;
// Test whether the 8-byte low3=7 op (byte+2 0x2f) is the perspective-interpolation
// finalize multiply. Perspective varyings should emit it; flat / no-perspective
// (center_no_perspective) varyings should not. Our own MSL.

struct VP { float4 pos [[position]]; float  a; };
struct VF { float4 pos [[position]]; float  a [[flat]]; };
struct VN { float4 pos [[position]]; float  a [[center_no_perspective]]; };

vertex VP v_p(uint vid [[vertex_id]], device const float4* p [[buffer(0)]], device const float* s [[buffer(1)]]) {
    VP o; o.pos = p[vid]; o.a = s[vid]; return o; }
vertex VF v_f(uint vid [[vertex_id]], device const float4* p [[buffer(0)]], device const float* s [[buffer(1)]]) {
    VF o; o.pos = p[vid]; o.a = s[vid]; return o; }
vertex VN v_n(uint vid [[vertex_id]], device const float4* p [[buffer(0)]], device const float* s [[buffer(1)]]) {
    VN o; o.pos = p[vid]; o.a = s[vid]; return o; }

fragment float4 f_p(VP in [[stage_in]]) { return float4(in.a); }
fragment float4 f_f(VF in [[stage_in]]) { return float4(in.a); }
fragment float4 f_n(VN in [[stage_in]]) { return float4(in.a); }
