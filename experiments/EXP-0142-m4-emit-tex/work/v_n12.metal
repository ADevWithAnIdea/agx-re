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
    float v4 = in[b+4];
    float v5 = in[b+5];
    float v6 = in[b+6];
    float v7 = in[b+7];
    float v8 = in[b+8];
    float v9 = in[b+9];
    float v10 = in[b+10];
    float v11 = in[b+11];
    out[1] = v0;
    out[2] = v1;
    out[3] = v2;
    out[4] = v3;
    out[5] = v4;
    out[6] = v5;
    out[7] = v6;
    out[8] = v7;
    out[9] = v8;
    out[10] = v9;
    out[11] = v10;
    out[12] = v11;
    float4 c = t.sample(s, float2(in[b+62], in[b+63]), level(0.0f));
    out[0] = c.x;
    out[13] = v0;
    out[14] = v1;
    out[15] = v2;
    out[16] = v3;
    out[17] = v4;
    out[18] = v5;
    out[19] = v6;
    out[20] = v7;
    out[21] = v8;
    out[22] = v9;
    out[23] = v10;
    out[24] = v11;
    out[25] = c.y; out[26] = c.z; out[27] = c.w;
}
