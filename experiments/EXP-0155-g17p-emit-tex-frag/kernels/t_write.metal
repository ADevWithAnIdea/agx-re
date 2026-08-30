// t_write.metal -- EXP-0155 carrier T3: THREE independent texture WRITES from
// the fragment stage into an RGBA32Float target the harness resets to a
// sentinel before every render.  OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// NO BRANCH.  The pre-freeze census (raw/prefreeze/census_run1.txt) showed that
// guarding the writes on gl_FragCoord introduced icmp_pred/if_push/jump_cond
// and stopped tools/agx-isa tokenizing the program at all, so tex_write could
// not be LOCATED by the database.  Every fragment now performs the same three
// writes with the same three values to the same three texels, which is
// order-independent and therefore still deterministic.
//
// LIVENESS.  gfrun resets every texel of texture(1) to (-1,-2,-3,-4) before the
// draw and reads the whole texture back afterwards, so for each write:
//   * the target texel holds the written colour   -> the write happened here
//   * the target texel still holds (-1,-2,-3,-4)  -> the write did not happen
//   * a DIFFERENT texel changed                   -> the coordinate moved
// are three distinguishable observations at known addresses, and (0,0)/(7,7)
// are read back as controls that must keep the reset sentinel.  Nothing else in
// the program can touch texture(1).
//
// Colour channel 3 is the integrity sentinel (plain ALU, no texture unit).
#include <metal_stdlib>
using namespace metal;

struct VO { float4 pos [[position]]; };

vertex VO v_main(uint vid [[vertex_id]])
{
    float f = float(vid);
    VO o;
    o.pos = float4((f - 1.0f) * 0.75f, (f * f - f) * 0.5f - 0.375f, 0.0f, 1.0f);
    return o;
}

fragment float4 f_main(VO i [[stage_in]],
                       texture2d<float, access::write> w [[texture(1)]],
                       device const float *in [[buffer(0)]])
{
    float4 c0 = float4(in[ 8], in[ 9], in[10], in[11]);
    float4 c1 = float4(in[12], in[13], in[14], in[15]);
    float4 c2 = float4(in[16], in[17], in[18], in[19]);
    w.write(c0, uint2(1u, 0u));
    w.write(c1, uint2(3u, 2u));
    w.write(c2, uint2(5u, 4u));
    return float4(c0.x, c1.x, c2.x, in[6] * in[7]);
}
