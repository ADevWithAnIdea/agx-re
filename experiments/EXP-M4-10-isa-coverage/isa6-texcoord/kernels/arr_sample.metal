#include <metal_stdlib>
using namespace metal;
kernel void k(texture2d_array<float> t [[texture(0)]], sampler s [[sampler(0)]],
              device float* o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    o[i] = t.sample(s, float2(0.5,0.5), 2).r;
}
