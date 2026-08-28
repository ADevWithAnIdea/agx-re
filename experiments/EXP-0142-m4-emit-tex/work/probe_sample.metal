#include <metal_stdlib>
using namespace metal;

// Exploratory carrier (pre-freeze). 16 distinct float values live across a
// texture sample whose coordinate comes from two of them.
kernel void k_sample(texture2d<float, access::sample> t [[texture(0)]],
                     device const float *in  [[buffer(0)]],
                     device float       *out [[buffer(1)]],
                     uint tid [[thread_position_in_grid]])
{
    constexpr sampler s(coord::pixel, filter::nearest,
                        address::clamp_to_edge, mip_filter::none);
    float v0 = in[0];  float v1 = in[1];  float v2 = in[2];  float v3 = in[3];
    float v4 = in[4];  float v5 = in[5];  float v6 = in[6];  float v7 = in[7];
    float v8 = in[8];  float v9 = in[9];  float v10= in[10]; float v11= in[11];
    float v12= in[12]; float v13= in[13]; float v14= in[14]; float v15= in[15];

    float4 c = t.sample(s, float2(v0, v1), level(0.0f));

    out[0]  = c.x;
    out[1]  = v0;  out[2]  = v1;  out[3]  = v2;  out[4]  = v3;
    out[5]  = v4;  out[6]  = v5;  out[7]  = v6;  out[8]  = v7;
    out[9]  = v8;  out[10] = v9;  out[11] = v10; out[12] = v11;
    out[13] = v12; out[14] = v13; out[15] = v14; out[16] = v15;
    out[17] = c.y; out[18] = c.z; out[19] = c.w;
}
