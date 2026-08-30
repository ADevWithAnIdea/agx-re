#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]], device const float* cin [[buffer(1)]],
              texture2d<float> tex [[texture(0)]], sampler smp [[sampler(0)]],
              uint gid [[thread_position_in_grid]]) {
  out[gid] = tex.sample(smp, float2(cin[0], cin[1]), level(cin[2] + out[gid]*0.0f)).x;
}
