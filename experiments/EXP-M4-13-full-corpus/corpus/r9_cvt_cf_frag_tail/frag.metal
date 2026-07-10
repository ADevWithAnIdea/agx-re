#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    float4 c0;
};

vertex VOut vmain(uint vid [[vertex_id]]) {
    VOut o;
    o.pos = float4(float(vid), 0, 0, 1);
    o.c0  = float4(0.25, 0.5, 0.75, 1.0);
    return o;
}

// single RT, simple store  -> frag_color_store baseline
fragment float4 f_one(VOut in [[stage_in]]) {
    return in.c0;
}

// single RT, source is a computed value (different source reg)
fragment float4 f_calc(VOut in [[stage_in]]) {
    return in.c0 * 2.0 + float4(0.1);
}

// half color output (different data type / format descriptor)
fragment half4 f_half(VOut in [[stage_in]]) {
    return half4(in.c0);
}

// MRT: multiple render targets -> several frag_color_store with different rt_index
struct MRT { float4 a [[color(0)]]; float4 b [[color(1)]]; float4 c [[color(2)]]; };
fragment MRT f_mrt(VOut in [[stage_in]]) {
    MRT o;
    o.a = in.c0;
    o.b = in.c0.yxwz;
    o.c = in.c0 * 0.5;
    return o;
}

// integer render target (uint format)
fragment uint4 f_uint(VOut in [[stage_in]]) {
    return uint4(in.c0 * 255.0);
}

// ---- frag_pos_read provokers: [[position]], [[front_facing]], interpolation modes ----
fragment float4 f_pos(VOut in [[stage_in]]) {
    return in.pos;               // fragment position read
}
fragment float4 f_facing(VOut in [[stage_in]], bool ff [[front_facing]]) {
    return ff ? in.c0 : float4(0);
}
struct VOut2 {
    float4 pos [[position]];
    float4 lin;                          // default (perspective) interp
    float4 noperspective [[center_no_perspective]];
    float4 flatv [[flat]];
    float4 cent [[centroid_perspective]];
};
vertex VOut2 vmain2(uint vid [[vertex_id]]) {
    VOut2 o;
    o.pos = float4(float(vid),0,0,1);
    o.lin = float4(0.1,0.2,0.3,0.4);
    o.noperspective = float4(0.5,0.6,0.7,0.8);
    o.flatv = float4(1,2,3,4);
    o.cent = float4(9,8,7,6);
    return o;
}
fragment float4 f_interp_persp(VOut2 in [[stage_in]]) { return in.lin; }
fragment float4 f_interp_nopersp(VOut2 in [[stage_in]]) { return in.noperspective; }
fragment float4 f_interp_flat(VOut2 in [[stage_in]]) { return in.flatv; }
fragment float4 f_interp_cent(VOut2 in [[stage_in]]) { return in.cent; }
fragment float4 f_samplepos(VOut in [[stage_in]], float2 sp [[point_coord]]) {
    return float4(sp, 0, 1);
}

fragment float f_r(VOut in [[stage_in]]) { return in.c0.x; }
fragment float2 f_rg(VOut in [[stage_in]]) { return in.c0.xy; }
fragment float3 f_rgb(VOut in [[stage_in]]) { return in.c0.xyz; }
