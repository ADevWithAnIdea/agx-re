#include <metal_stdlib>
using namespace metal;
kernel void k_sample(texture2d<float, access::sample> t [[texture(0)]],
                     device const float *in  [[buffer(0)]],
                     device float       *out [[buffer(1)]],
                     uint tid [[thread_position_in_grid]])
{
    constexpr sampler s(coord::pixel, filter::nearest, address::clamp_to_edge, mip_filter::none);
    uint b = tid * 64u;
    float4 c0 = t.sample(s, float2(in[b+0], in[b+1]), level(0.0f));
    out[0] = c0.x; out[1] = c0.y; out[2] = c0.z; out[3] = c0.w;
}
