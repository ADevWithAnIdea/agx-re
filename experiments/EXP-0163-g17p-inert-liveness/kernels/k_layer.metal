// k_layer.metal -- EXP-0163 LAYERED (texture2d_array) render-target carrier.
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY.  db.json calls frag_color_store byte+2 (`store_mode`) the "tile-store
// addressing MODE (const 0x54, 130/130 corpus)" and byte+8..11 (`slice_addr`)
// "an array/layer slice-address block, const 0x00000000 in single-RT stores and
// carrying the layer/slice address only in ARRAY-TARGET stores".  Every
// EXP-0155 carrier rendered to a plain 2D attachment, so the array-target
// addressing path -- the only documented case where the store addresses
// anything other than the flat tile -- was never emitted at all.
//
// The vertex stage selects the destination slice with
// [[render_target_array_index]]; the harness allocates a 4-slice array
// attachment and reads back EVERY slice, so "wrote the wrong slice" and "wrote
// no slice" are distinguishable read-backs.
#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
    uint   layer [[render_target_array_index]];
    float  v0;
    float  v1;
    float  v2;
    float  v3;
};

vertex VOut v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VOut o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    o.layer = 2u;              // a NON-ZERO slice, so slice_addr must be live
    o.v0  = 1.0f    + f;
    o.v1  = 10.0f   + f * f;
    o.v2  = 100.0f  - 3.0f * f;
    o.v3  = 1000.0f + 5.0f * f * f - 2.0f * f;
    return o;
}

fragment float4 f_main(VOut in [[stage_in]])
{
    return float4(in.v0, in.v1, in.v2, in.v3);
}
