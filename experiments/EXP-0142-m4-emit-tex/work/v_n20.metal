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
    float v12 = in[b+12];
    float v13 = in[b+13];
    float v14 = in[b+14];
    float v15 = in[b+15];
    float v16 = in[b+16];
    float v17 = in[b+17];
    float v18 = in[b+18];
    float v19 = in[b+19];
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
    out[13] = v12;
    out[14] = v13;
    out[15] = v14;
    out[16] = v15;
    out[17] = v16;
    out[18] = v17;
    out[19] = v18;
    out[20] = v19;
    float4 c = t.sample(s, float2(in[b+62], in[b+63]), level(0.0f));
    out[0] = c.x;
    out[21] = v0;
    out[22] = v1;
    out[23] = v2;
    out[24] = v3;
    out[25] = v4;
    out[26] = v5;
    out[27] = v6;
    out[28] = v7;
    out[29] = v8;
    out[30] = v9;
    out[31] = v10;
    out[32] = v11;
    out[33] = v12;
    out[34] = v13;
    out[35] = v14;
    out[36] = v15;
    out[37] = v16;
    out[38] = v17;
    out[39] = v18;
    out[40] = v19;
    out[41] = c.y; out[42] = c.z; out[43] = c.w;
}
