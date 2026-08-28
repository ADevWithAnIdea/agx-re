// samplemask.metal -- EXP-0117 [[sample_mask]] finite-width probe (OWN-SHADER).
//
// A uniform (non-per-sample-forced) fragment shader that writes a
// buffer-driven [[sample_mask]] value; the harness sweeps the raw mask
// value against MSAA sample counts N=1,2,4 and reads back the resolved
// color fraction, which for a hardware box-filter resolve is an exact
// popcount(mask & validbits)/N readout technique (established by EXP-0091/
// EXP-0111). This isolates the FINITE bit-width of the mask: which bits
// are load-bearing for a given N, and what happens to bits beyond N.

#include <metal_stdlib>
using namespace metal;

vertex float4 v_full(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    return float4(p[vid % 3], 0.0, 1.0);
}

struct FOut { float4 color [[color(0)]]; uint mask [[sample_mask]]; };
fragment FOut f_samplemask_probe(constant uint &requested [[buffer(0)]]) {
    FOut o;
    o.color = float4(1,1,1,1);
    o.mask = requested;
    return o;
}
