#include <metal_stdlib>
using namespace metal;

struct VOut { float4 position [[position]]; };

vertex VOut v_main(uint vid [[vertex_id]]) {
    VOut out;
    float2 p = (vid == 0u) ? float2(-1.0f, -1.0f) :
               ((vid == 1u) ? float2(3.0f, -1.0f) : float2(-1.0f, 3.0f));
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

fragment float4 f_main(VOut in [[stage_in]],
                       device const float *input [[buffer(0)]],
                       constant uint &n [[buffer(1)]]) {
    uint pixel = uint(in.position.y) * 8u + uint(in.position.x);
    float a[24576];
    for (uint i = 0u; i < 24576u; ++i) a[i] = input[((pixel) * 24576u + i) % 4096u];
    for (uint pass = 1u; pass < n; ++pass) {
        float t = input[pass % 4096u];
        for (uint i = 0u; i < 24576u; ++i) a[i] = 0.5f * a[i] + 0.5f * a[(i + 1u) % 24576u] + t * 1e-6f;
    }
    float sum = 0.0f;
    for (uint i = 0u; i < 24576u; ++i) sum += a[i];
    return float4(sum * 0x1p-16f, 0.25f, 0.5f, 1.0f);
}
