// EXP-0094 generated register-pressure probe (grad, N=4), v3.
// analysis/gen_regpressure.py -- do not hand-edit. Every params[] read is
// offset by the per-thread SR `tid.x` (always 0 in our 1-thread dispatch, but
// NOT a compile-time constant), so the compiler cannot prove uniformity and
// cannot hoist to the preamble -- see the v3 header note in this file.
#include <metal_stdlib>
using namespace metal;

kernel void kmain(texture2d<float> tex [[texture(0)]],
                   sampler s [[sampler(0)]],
                   constant float *params [[buffer(0)]],
                   device float *out [[buffer(1)]],
                   uint2 tid [[thread_position_in_grid]]) {
    float j0 = params[tid.x + 4];
    float j1 = params[tid.x + 5];
    float j2 = params[tid.x + 6];
    float j3 = params[tid.x + 7];
    float sink = j0;
    sink = sink * j1 - j0;
    sink = max(sink, j2) + sink * 0.0001f;
    sink = fma(sink, 1.00004f, j3);
    float2 dx = float2(params[tid.x + 8], params[tid.x + 9]);
    float2 dy = float2(params[tid.x + 10], params[tid.x + 11]);
    float v = tex.sample(s, float2(0.5, 0.5), gradient2d(dx, dy)).r;
    out[0] = v;
    out[1] = sink;
}
