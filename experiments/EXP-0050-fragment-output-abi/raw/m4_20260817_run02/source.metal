#include <metal_stdlib>
using namespace metal;

struct VOut { float4 pos [[position]]; };

vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p[3] = {float2(-1.0, -1.0), float2(3.0, -1.0), float2(-1.0, 3.0)};
    VOut o;
    o.pos = float4(p[vid], 0.75, 1.0);
    return o;
}

static inline float4 color0() {
    return float4(17.0/255.0, 34.0/255.0, 51.0/255.0, 68.0/255.0);
}
static inline float4 color1() {
    return float4(85.0/255.0, 102.0/255.0, 119.0/255.0, 136.0/255.0);
}
static inline float4 color2() {
    return float4(153.0/255.0, 170.0/255.0, 187.0/255.0, 204.0/255.0);
}

fragment float4 f_c0() { return color0(); }

struct O1 { float4 c1 [[color(1)]]; };
fragment O1 f_c1_only() { O1 o; o.c1 = color1(); return o; }

struct O2 { float4 c2 [[color(2)]]; };
fragment O2 f_c2_only() { O2 o; o.c2 = color2(); return o; }

struct O02 { float4 c0 [[color(0)]]; float4 c2 [[color(2)]]; };
fragment O02 f_c0_c2_decl02() {
    O02 o; o.c0 = color0(); o.c2 = color2(); return o;
}

struct O20 { float4 c2 [[color(2)]]; float4 c0 [[color(0)]]; };
fragment O20 f_c0_c2_decl20() {
    O20 o; o.c0 = color0(); o.c2 = color2(); return o;
}

struct O012 {
    float4 c0 [[color(0)]];
    float4 c1 [[color(1)]];
    float4 c2 [[color(2)]];
};
fragment O012 f_mrt3_decl012() {
    O012 o; o.c0 = color0(); o.c1 = color1(); o.c2 = color2(); return o;
}

struct O210 {
    float4 c2 [[color(2)]];
    float4 c1 [[color(1)]];
    float4 c0 [[color(0)]];
};
fragment O210 f_mrt3_decl210() {
    O210 o; o.c0 = color0(); o.c1 = color1(); o.c2 = color2(); return o;
}

fragment O012 f_mrt3_swap12() {
    O012 o; o.c0 = color0(); o.c1 = color2(); o.c2 = color1(); return o;
}

struct OColorDepth {
    float4 c0 [[color(0)]];
    float depth [[depth(any)]];
};
fragment OColorDepth f_color_depth() {
    OColorDepth o; o.c0 = color0(); o.depth = 0.25; return o;
}

struct ODepthColor {
    float depth [[depth(any)]];
    float4 c0 [[color(0)]];
};
fragment ODepthColor f_depth_color_decl() {
    ODepthColor o; o.c0 = color0(); o.depth = 0.25; return o;
}

struct ODepth { float depth [[depth(any)]]; };
fragment ODepth f_depth_only() { ODepth o; o.depth = 0.625; return o; }

fragment float4 f_color_fixed_depth() { return color0(); }

static inline float4 sample_color(uint sid) {
    return float4(float(sid + 1u) * 0.25, 0.0, 0.0, 1.0);
}
struct OColorMask { float4 c0 [[color(0)]]; uint mask [[sample_mask]]; };
fragment OColorMask f_mask_f(uint sid [[sample_id]]) {
    OColorMask o; o.c0 = sample_color(sid); o.mask = 0xfu; return o;
}
fragment OColorMask f_mask_5(uint sid [[sample_id]]) {
    OColorMask o; o.c0 = sample_color(sid); o.mask = 0x5u; return o;
}
fragment OColorMask f_mask_a(uint sid [[sample_id]]) {
    OColorMask o; o.c0 = sample_color(sid); o.mask = 0xau; return o;
}
fragment OColorMask f_mask_0(uint sid [[sample_id]]) {
    OColorMask o; o.c0 = sample_color(sid); o.mask = 0u; return o;
}
struct OMaskColor { uint mask [[sample_mask]]; float4 c0 [[color(0)]]; };
fragment OMaskColor f_mask_5_declfirst(uint sid [[sample_id]]) {
    OMaskColor o; o.c0 = sample_color(sid); o.mask = 0x5u; return o;
}

fragment float4 f_discard_half(float4 pos [[position]]) {
    if (pos.x < 2.0) discard_fragment();
    return color0();
}

fragment float4 f_atomic_all(device atomic_uint *counter [[buffer(0)]]) {
    atomic_fetch_add_explicit(counter, 1u, memory_order_relaxed);
    return color0();
}

fragment float4 f_atomic_before_discard(float4 pos [[position]],
                                         device atomic_uint *counter [[buffer(0)]]) {
    atomic_fetch_add_explicit(counter, 1u, memory_order_relaxed);
    if (pos.x < 2.0) discard_fragment();
    return color0();
}

fragment float4 f_atomic_after_discard(float4 pos [[position]],
                                        device atomic_uint *counter [[buffer(0)]]) {
    if (pos.x < 2.0) discard_fragment();
    atomic_fetch_add_explicit(counter, 1u, memory_order_relaxed);
    return color0();
}
