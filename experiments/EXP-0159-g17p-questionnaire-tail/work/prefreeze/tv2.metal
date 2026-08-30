#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]], device const float* cin [[buffer(1)]],
              texture2d<float> tex [[texture(0)]], sampler smp [[sampler(0)]],
              uint gid [[thread_position_in_grid]]) {
  float2 uv = float2(cin[0], cin[1]);
  out[gid] = tex.sample(smp, uv, level(cin[2] + float(gid) * 0.0f)).x;
}
