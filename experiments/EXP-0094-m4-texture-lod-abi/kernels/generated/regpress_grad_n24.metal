// EXP-0094 generated register-pressure probe (grad, N=24), v3.
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
    float j4 = params[tid.x + 8];
    float j5 = params[tid.x + 9];
    float j6 = params[tid.x + 10];
    float j7 = params[tid.x + 11];
    float j8 = params[tid.x + 12];
    float j9 = params[tid.x + 13];
    float j10 = params[tid.x + 14];
    float j11 = params[tid.x + 15];
    float j12 = params[tid.x + 16];
    float j13 = params[tid.x + 17];
    float j14 = params[tid.x + 18];
    float j15 = params[tid.x + 19];
    float j16 = params[tid.x + 20];
    float j17 = params[tid.x + 21];
    float j18 = params[tid.x + 22];
    float j19 = params[tid.x + 23];
    float j20 = params[tid.x + 24];
    float j21 = params[tid.x + 25];
    float j22 = params[tid.x + 26];
    float j23 = params[tid.x + 27];
    float sink = j0;
    sink = sink * j1 - j0;
    sink = max(sink, j2) + sink * 0.0001f;
    sink = fma(sink, 1.00004f, j3);
    sink = sink * j4 - j3;
    sink = max(sink, j5) + sink * 0.0001f;
    sink = fma(sink, 1.00007f, j6);
    sink = sink * j7 - j6;
    sink = max(sink, j8) + sink * 0.0001f;
    sink = fma(sink, 1.00003f, j9);
    sink = sink * j10 - j9;
    sink = max(sink, j11) + sink * 0.0001f;
    sink = fma(sink, 1.00006f, j12);
    sink = sink * j13 - j12;
    sink = max(sink, j14) + sink * 0.0001f;
    sink = fma(sink, 1.00002f, j15);
    sink = sink * j16 - j15;
    sink = max(sink, j17) + sink * 0.0001f;
    sink = fma(sink, 1.00005f, j18);
    sink = sink * j19 - j18;
    sink = max(sink, j20) + sink * 0.0001f;
    sink = fma(sink, 1.00001f, j21);
    sink = sink * j22 - j21;
    sink = max(sink, j23) + sink * 0.0001f;
    float2 dx = float2(params[tid.x + 28], params[tid.x + 29]);
    float2 dy = float2(params[tid.x + 30], params[tid.x + 31]);
    float v = tex.sample(s, float2(0.5, 0.5), gradient2d(dx, dy)).r;
    out[0] = v;
    out[1] = sink;
}
