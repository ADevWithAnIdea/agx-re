// k_tileread.metal -- EXP-0163 PROGRAMMABLE-BLENDING (tile read) carrier.
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY.  db.json documents frag_tile_setup.access as "0x06 store-setup vs 0x08
// tile-read", and the two EXP-0155 carriers (`fts@iter0`, `fts@iter1`) both sit
// around a plain colour STORE -- neither program ever reads the tile, so only
// one of the two documented access modes was ever present and a selector
// between them had nothing to select.  A [[color(0)]] fragment INPUT makes Metal
// emit the tile-read path, so both modes are live in one program.
//
// The render pass clears to a distinctive non-zero colour, so the value the tile
// read returns is known to the host and a suppressed / redirected read is
// numerically obvious in the output.
#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 pos [[position]];
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
    o.v0  = 1.0f    + f;
    o.v1  = 10.0f   + f * f;
    o.v2  = 100.0f  - 3.0f * f;
    o.v3  = 1000.0f + 5.0f * f * f - 2.0f * f;
    return o;
}

fragment float4 f_main(VOut in [[stage_in]],
                       float4 dst [[color(0)]])
{
    // Both operands matter: a lost tile read drops `dst`, a lost interpolation
    // drops the varyings, and the two are numerically separable.
    return float4(dst.x * 8.0f + in.v0,
                  dst.y * 8.0f + in.v1,
                  dst.z * 8.0f + in.v2,
                  dst.w * 8.0f + in.v3);
}
