#include <metal_stdlib>
using namespace metal;
kernel void k_sample(texture2d<float, access::sample> t [[texture(0)]],
                     device const float *in  [[buffer(0)]],
                     device float       *out [[buffer(1)]],
                     uint tid [[thread_position_in_grid]])
{
    constexpr sampler s(coord::pixel, filter::nearest, address::clamp_to_edge, mip_filter::none);
    uint b = tid * 64u;
    float v0 = in[b+0];
    float v1 = in[b+1];
    float v2 = in[b+2];
    float v3 = in[b+3];
    out[1] = v0;
    out[2] = v1;
    out[3] = v2;
    out[4] = v3;
    float4 c = t.sample(s, float2(in[b+62], in[b+63]), level(0.0f));
    out[0] = c.x;
    out[5] = v0;
    out[6] = v1;
    out[7] = v2;
    out[8] = v3;
    out[9] = c.y; out[10] = c.z; out[11] = c.w;
}
