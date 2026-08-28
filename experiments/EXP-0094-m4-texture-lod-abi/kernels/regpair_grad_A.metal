// EXP-0094 regpair_grad_A.metal -- own MSL, v2 (tid-offset-routed to force
// genuine per-invocation residency; see analysis/gen_regpressure.py v3 header).
// Minimal differential-compilation pair (A side) for isolating the
// gradient-operand register block: two independent gradient register-quads
// (dxA,dyA) and (dxB,dyB), each read from `params[tid.x + K]` (tid.x is
// always 0 in our 1-thread dispatch, but is NOT a compile-time constant, so
// the compiler cannot hoist the reads to the preamble). This variant feeds
// the A quad to gradient2d(); regpair_grad_B.metal is byte-identical source
// except which quad feeds gradient2d() and which feeds the sink.
#include <metal_stdlib>
using namespace metal;

kernel void kmain(texture2d<float> tex [[texture(0)]],
                   sampler s [[sampler(0)]],
                   constant float *params [[buffer(0)]],
                   device float *out [[buffer(1)]],
                   uint2 tid [[thread_position_in_grid]]) {
    float2 dxA = float2(params[tid.x + 0], params[tid.x + 1]);
    float2 dyA = float2(params[tid.x + 2], params[tid.x + 3]);
    float2 dxB = float2(params[tid.x + 4], params[tid.x + 5]);
    float2 dyB = float2(params[tid.x + 6], params[tid.x + 7]);
    float v = tex.sample(s, float2(0.5, 0.5), gradient2d(dxA, dyA)).r;
    out[0] = v;
    out[1] = dxB.x + dxB.y + dyB.x + dyB.y;
}
