#include <metal_stdlib>
using namespace metal;
kernel void k(device float* o [[buffer(0)]], device const uint* a [[buffer(1)]],
              texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
              device atomic_uint* c [[buffer(2)]], uint tid [[thread_position_in_grid]]) {
    uint v = a[tid]; float acc = 0.0f;
    for (uint i = 0; i < v; ++i) {
        if (i & 1u) { acc += t.sample(s, float2(float(i)*0.05f, 0.5f)).x;
                      atomic_fetch_add_explicit(c, i, memory_order_relaxed); }
        else { acc -= t.read(uint2(i & 7u, 3u)).y; }
    }
    o[tid] = acc;
}
