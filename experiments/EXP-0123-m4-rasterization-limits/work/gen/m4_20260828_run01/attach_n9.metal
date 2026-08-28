#include <metal_stdlib>
using namespace metal;
struct VOut { float4 position [[position]]; };
struct FOut {
    float4 c0 [[color(0)]];
    float4 c1 [[color(1)]];
    float4 c2 [[color(2)]];
    float4 c3 [[color(3)]];
    float4 c4 [[color(4)]];
    float4 c5 [[color(5)]];
    float4 c6 [[color(6)]];
    float4 c7 [[color(7)]];
};
vertex VOut vs_tri(uint vid [[vertex_id]]) {
    float2 pos[3] = { float2(-2.0,-2.0), float2(2.0,-2.0), float2(0.0,2.0) };
    VOut o; o.position = float4(pos[vid], 0.0, 1.0); return o;
}
fragment FOut fs_multi() {
    FOut o;
    o.c0 = float4(float(0)/8.0, 0.5, 0.5, 1.0);
    o.c1 = float4(float(1)/8.0, 0.5, 0.5, 1.0);
    o.c2 = float4(float(2)/8.0, 0.5, 0.5, 1.0);
    o.c3 = float4(float(3)/8.0, 0.5, 0.5, 1.0);
    o.c4 = float4(float(4)/8.0, 0.5, 0.5, 1.0);
    o.c5 = float4(float(5)/8.0, 0.5, 0.5, 1.0);
    o.c6 = float4(float(6)/8.0, 0.5, 0.5, 1.0);
    o.c7 = float4(float(7)/8.0, 0.5, 0.5, 1.0);
    return o;
}
