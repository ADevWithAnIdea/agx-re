// EXP-0126 H1 fragment-stage carrier. OWN MSL, authored for this experiment.
//
// Vertex stage: fixed full-screen triangle from vertex_id alone (no buffers) --
// standard clip-space trick, three vertices covering the whole viewport.
//
// Fragment stage: deliberately mirrors EXP-0089/EXP-0119's "adjacent" MODE-B
// two-reader pattern (a single shared value read by two SEPARATE downstream ALU
// ops, defeating CSE of the ops themselves while keeping ONE read of the shared
// source): v = a[0]; x1 = v + 10.0; x2 = v + 20.0. The compiler is expected to
// emit two falu2i-family instructions both reading v's register -- x1's producer
// is the "earlier reader" whose srcA_reg top-bit field this experiment splices
// (MODE B, exactly as EXP-0089 did for if_boundary/adjacent/etc, just in the
// fragment stage instead of compute). Output is written as a color so it can be
// read back via the existing pixel-readback path (BGRA8Unorm, 8-bit/channel) --
// values are pre-scaled by the ALU itself (divide by 64.0) so the two
// discriminable outcomes at each probe point (30.0 vs 0.0 for addressing;
// 50.0 vs 20.0 for retention) land at well-separated, quantization-safe unorm
// levels (0.46875 vs 0.0; 0.78125 vs 0.3125 -- all >0.15 apart, far beyond
// 1/255 ~= 0.004 unorm step noise).
#include <metal_stdlib>
using namespace metal;

struct VOut { float4 position [[position]]; };

vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 pos[3] = { float2(-1.0, -1.0), float2(3.0, -1.0), float2(-1.0, 3.0) };
    VOut o;
    o.position = float4(pos[vid], 0.0, 1.0);
    return o;
}

fragment float4 f_main(VOut in [[stage_in]],
                        device float* a [[buffer(0)]]) {
    float v = a[0];
    float x1 = v + a[1];   // "earlier reader" -- own-result/addressing probe
    float x2 = v + a[2];   // "later reader" -- retention probe
    return float4(x1 / 64.0, x2 / 64.0, 0.0, 1.0);
}
