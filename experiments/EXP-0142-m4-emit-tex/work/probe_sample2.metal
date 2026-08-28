#include <metal_stdlib>
using namespace metal;
kernel void k_sample(texture2d<float, access::sample> t [[texture(0)]],
                     device const float *in  [[buffer(0)]],
                     device float       *out [[buffer(1)]],
                     uint tid [[thread_position_in_grid]])
{
    constexpr sampler s(coord::pixel, filter::nearest, address::clamp_to_edge, mip_filter::none);
    uint b = tid * 32u;
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
    float v20 = in[b+20];
    float v21 = in[b+21];
    float v22 = in[b+22];
    float v23 = in[b+23];
    float4 c = t.sample(s, float2(v0, v1), level(0.0f));
    out[0] = c.x;
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
    out[21] = v20;
    out[22] = v21;
    out[23] = v22;
    out[24] = v23;
    out[25] = c.y; out[26] = c.z; out[27] = c.w;
}
