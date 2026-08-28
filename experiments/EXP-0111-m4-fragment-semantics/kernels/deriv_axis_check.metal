#include <metal_stdlib>
using namespace metal;
// FS-04/FS-07 axis-label cross-check: the compile-scan of deriv_scalar_f1..f4 (dfdx-only)
// showed axis byte 0x90 for EVERY case, contradicting docs/isa/encoding-tables.md's
// prior "0x92=dfdx, 0x90=dfdy" labeling (EXP-0016 provenance). This kernel independently
// pins down ground truth with a numeric HW readback: dfdx(pos.x) must equal 1.0 (the
// true per-pixel X step) and dfdx(pos.y) must equal 0.0 (no Y-dependence); dfdy(pos.x)
// must equal 0.0 and dfdy(pos.y) must equal 1.0. Whichever axis byte co-occurs with the
// MSL call that reads back 1.0 for a given oracle pins the correct label.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment float4 f_main(float4 pos [[position]], device uint *buf [[buffer(0)]]) {
    float dfdx_x = dfdx(pos.x);
    float dfdx_y = dfdx(pos.y);
    float dfdy_x = dfdy(pos.x);
    float dfdy_y = dfdy(pos.y);
    buf[0] = as_type<uint>(dfdx_x);
    buf[1] = as_type<uint>(dfdx_y);
    buf[2] = as_type<uint>(dfdy_x);
    buf[3] = as_type<uint>(dfdy_y);
    return float4(0,0,0,1);
}
