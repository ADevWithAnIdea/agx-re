#include <metal_stdlib>
using namespace metal;
// GLFS-A01 (MSAA width sweep) + GLFS-A07 cross-check: per-sample-shaded fragment
// writes color=1.0 only for samples whose bit is set in a runtime sample_mask value
// (from buffer(0)), 0.0 otherwise, AND explicitly writes [[sample_mask]] to that
// same value (so both the fixed-function coverage path and the shader's own
// [[sample_id]]-conditioned color agree). After MSAA resolve (box filter/average),
// resolved.r directly reads back popcount(mask & validbits)/sampleCount -- letting
// the harness measure exact per-sample survival for any authored mask pattern
// without needing a raw per-sample texture readback.
struct FOut { float4 color [[color(0)]]; uint mask [[sample_mask]]; };
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment FOut f_main(uint sid [[sample_id]], constant uint &wantmask [[buffer(0)]]) {
    FOut o;
    bool on = ((wantmask >> sid) & 1u) != 0u;
    o.color = on ? float4(1,1,1,1) : float4(0,0,0,1);
    o.mask = wantmask;
    return o;
}
