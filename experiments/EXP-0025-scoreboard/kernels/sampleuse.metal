#include <metal_stdlib>
using namespace metal;
kernel void k(texture2d<float> tex [[texture(0)]],
              sampler s             [[sampler(0)]],
              device float *out      [[buffer(0)]],
              uint gid [[thread_position_in_grid]]) {
    float4 c = tex.sample(s, float2(0.5f, 0.5f));
    out[gid] = c.x + c.y;   // consume sample result
}
