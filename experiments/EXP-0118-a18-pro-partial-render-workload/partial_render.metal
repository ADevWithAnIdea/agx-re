// SPDX-License-Identifier: MIT
#include <metal_stdlib>

using namespace metal;

constant uint attachment_count = 8;

struct VertexOut {
    float4 position [[position]];
    float4 varying0;
    float4 varying1;
    float4 varying2;
    float4 varying3;
    float4 varying4;
    float4 varying5;
    float4 varying6;
    float4 varying7;
};

struct FragmentOut {
    float4 color0 [[color(0)]];
    float4 color1 [[color(1)]];
    float4 color2 [[color(2)]];
    float4 color3 [[color(3)]];
    float4 color4 [[color(4)]];
    float4 color5 [[color(5)]];
    float4 color6 [[color(6)]];
    float4 color7 [[color(7)]];
};

vertex VertexOut partial_vertex(
    uint id [[vertex_id]],
    constant uint4 &dimensions [[buffer(0)]],
    device const float4 *varyings [[buffer(1)]])
{
    const float2 corners[3] = {
        float2(0.05, 0.05),
        float2(0.95, 0.05),
        float2(0.50, 0.95),
    };
    const uint triangle = id / 3;
    const uint pixel = triangle % (dimensions.x * dimensions.y);
    const uint2 distributed_pixel = uint2(pixel % dimensions.x,
                                          pixel / dimensions.x);
    // Concentrating primitives in one tile is the relevant stress case for a
    // tiled vertex-buffer overflow; a large input allocation alone is not
    // evidence that the partial-render path is exercised.
    const float2 center = float2(dimensions.x, dimensions.y) * 0.5;
    const float2 concentrated_pixel = center +
        (corners[id % 3] - 0.5) * 2.0;
    const float2 point = dimensions.z != 0 ? concentrated_pixel :
        float2(distributed_pixel) + corners[id % 3];
    const uint base = id * attachment_count;

    VertexOut out;
    out.position = float4(
        point.x * (2.0 / float(dimensions.x)) - 1.0,
        1.0 - point.y * (2.0 / float(dimensions.y)),
        0.0, 1.0);
    if (dimensions.z >= 2) {
        const float value = dimensions.z == 3 ?
            1.0 / float(dimensions.w) :
            float((triangle & 15) + 1) / 255.0;
        out.varying0 = float4(value);
        out.varying1 = float4(value * 2.0);
        out.varying2 = float4(value * 3.0);
        out.varying3 = float4(value * 4.0);
        out.varying4 = float4(value * 5.0);
        out.varying5 = float4(value * 6.0);
        out.varying6 = float4(value * 7.0);
        out.varying7 = float4(value * 8.0);
    } else {
        out.varying0 = varyings[base + 0];
        out.varying1 = varyings[base + 1];
        out.varying2 = varyings[base + 2];
        out.varying3 = varyings[base + 3];
        out.varying4 = varyings[base + 4];
        out.varying5 = varyings[base + 5];
        out.varying6 = varyings[base + 6];
        out.varying7 = varyings[base + 7];
    }
    return out;
}

fragment FragmentOut partial_fragment(VertexOut in [[stage_in]])
{
    FragmentOut out;
    out.color0 = in.varying0;
    out.color1 = in.varying1;
    out.color2 = in.varying2;
    out.color3 = in.varying3;
    out.color4 = in.varying4;
    out.color5 = in.varying5;
    out.color6 = in.varying6;
    out.color7 = in.varying7;
    return out;
}
