// vfetch.metal — EXP-0109 VS attribute-fetch structural probe (OWN-SHADER).
// Four field-type variants of a [[stage_in]] vertex struct, each paired with a
// passthrough fragment. The API-side MTLVertexDescriptor (set by
// harness/vfetch_extract.m) supplies the actual MTLVertexFormat/offset/stride/
// step-function/step-rate; the MSL field type only constrains which *category*
// of format is legal to bind (float-decoding formats need a float-typed field,
// half-decoding formats need half, integer formats need int/uint).
//
// Pattern follows experiments/EXP-0031-sr-abi/harness/attrdump.m (A18, prior
// experiment's own authored tool) generalized to more field-type categories
// and to a step-rate (divisor) parameter carried purely on the API side.

#include <metal_stdlib>
using namespace metal;

struct VOutF {
    float4 position [[position]];
    float4 color;
};

// -- float-decoding formats (Float4, UChar4Normalized, Short4Normalized,
//    Int1010102Normalized all decode into a float4 field) --------------------
struct VInF4 {
    float4 a [[attribute(0)]];
};

vertex VOutF v_f4(VInF4 in [[stage_in]],
                   uint vid [[vertex_id]], uint iid [[instance_id]]) {
    VOutF out;
    float x = float(vid % 4) * 0.5 - 0.75;
    float y = float((vid / 4) % 4) * 0.5 - 0.75;
    out.position = float4(x, y, 0.0, 1.0);
    out.color = in.a + float4(float(iid), 0.0, 0.0, 0.0);
    return out;
}

// -- half-decoding format (Half4) --------------------------------------------
struct VInH4 {
    half4 a [[attribute(0)]];
};

vertex VOutF v_h4(VInH4 in [[stage_in]],
                   uint vid [[vertex_id]], uint iid [[instance_id]]) {
    VOutF out;
    float x = float(vid % 4) * 0.5 - 0.75;
    float y = float((vid / 4) % 4) * 0.5 - 0.75;
    out.position = float4(x, y, 0.0, 1.0);
    out.color = float4(in.a) + float4(float(iid), 0.0, 0.0, 0.0);
    return out;
}

// -- signed-integer format (Int4) --------------------------------------------
struct VInI4 {
    int4 a [[attribute(0)]];
};

vertex VOutF v_i4(VInI4 in [[stage_in]],
                   uint vid [[vertex_id]], uint iid [[instance_id]]) {
    VOutF out;
    float x = float(vid % 4) * 0.5 - 0.75;
    float y = float((vid / 4) % 4) * 0.5 - 0.75;
    out.position = float4(x, y, 0.0, 1.0);
    out.color = float4(in.a) + float4(float(iid), 0.0, 0.0, 0.0);
    return out;
}

// -- unsigned-integer format (UInt4) -----------------------------------------
struct VInU4 {
    uint4 a [[attribute(0)]];
};

vertex VOutF v_u4(VInU4 in [[stage_in]],
                   uint vid [[vertex_id]], uint iid [[instance_id]]) {
    VOutF out;
    float x = float(vid % 4) * 0.5 - 0.75;
    float y = float((vid / 4) % 4) * 0.5 - 0.75;
    out.position = float4(x, y, 0.0, 1.0);
    out.color = float4(in.a) + float4(float(iid), 0.0, 0.0, 0.0);
    return out;
}

fragment float4 f_pass(VOutF in [[stage_in]]) {
    return in.color;
}
