#include <metal_stdlib>
using namespace metal;
kernel void k_write(texture2d<float, access::sample> t [[texture(0)]],
                    texture2d<float, access::write>  w [[texture(1)]],
                    device const float *in  [[buffer(0)]],
                    device float       *out [[buffer(1)]],
                    uint tid [[thread_position_in_grid]])
{
    constexpr sampler s(coord::pixel, filter::nearest, address::clamp_to_edge, mip_filter::none);
    uint b = tid * 64u;
    float4 c0 = float4(in[b+0], in[b+1], in[b+2], in[b+3]);
    float4 c1 = float4(in[b+4], in[b+5], in[b+6], in[b+7]);
    float4 c2 = float4(in[b+8], in[b+9], in[b+10], in[b+11]);
    w.write(c0, uint2(1u, 0u));
    w.write(c1, uint2(3u, 2u));
    w.write(c2, uint2(5u, 4u));
    out[0] = t.sample(s, float2(in[b+12], in[b+13]), level(0.0f)).x;
}
