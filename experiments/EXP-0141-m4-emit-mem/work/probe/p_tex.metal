#include <metal_stdlib>
using namespace metal;
kernel void k(device float* o [[buffer(0)]], device const uint* a [[buffer(1)]],
              texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
              uint tid [[thread_position_in_grid]]) {
    uint v = a[tid];
    float acc = 0.0f;
    if (v > 2u) { acc += t.sample(s, float2(0.25f, 0.75f)).x; }
    else { acc += t.sample(s, float2(0.75f, 0.25f)).y; }
    for (uint i = 0; i < v; ++i) { acc = fma(acc, 1.5f, t.sample(s, float2(float(i)*0.1f, 0.5f)).z); }
    o[tid] = acc;
}
