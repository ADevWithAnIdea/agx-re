// EXP-0037 texture-sample render probe (OWN-SHADER). Bufferless fullscreen tri;
// fragment samples a bound texture and returns it. Used to HW-ground the sampler
// bundle (14B: 05/25/45 80/82/84 0c companion + 0xb0/0x90 10B sampler op) by
// splicing inside the bundle and observing the pixel.
#include <metal_stdlib>
using namespace metal;
struct VOut { float4 pos [[position]]; float2 uv; };
static float2 tri(uint vid){ return float2((vid==2)?3.0:-1.0,(vid==1)?3.0:-1.0); }
vertex VOut v_main(uint vid [[vertex_id]]) {
    VOut o; o.pos=float4(tri(vid),0,1);
    o.uv=float2((vid==2)?1.0:0.0,(vid==1)?1.0:0.0);
    return o;
}
fragment float4 f_tex(VOut in [[stage_in]], texture2d<float> t [[texture(0)]],
                      sampler s [[sampler(0)]]) {
    return t.sample(s, in.uv);
}
