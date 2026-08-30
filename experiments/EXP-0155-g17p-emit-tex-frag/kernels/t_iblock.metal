// t_iblock.metal -- EXP-0155 carrier T5: a fragment program that READS its own
// colour attachment (tile memory) and writes it back, to provoke the
// imageblock_load / imageblock_store pair.  OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// EXP-0142 recorded that the EXPLICIT-layout `imageblock<T,
// imageblock_layout_explicit>` fragment parameter no longer compiles on this
// GPUCompiler; that compile failure is retained in that experiment's
// raw/prefreeze/.  The programmable-blending route (a [[color(0)]] INPUT) is
// the remaining path that reaches tile memory from an ordinary fragment
// function, and the pre-freeze census showed the RGBA32Float colour store in
// t_sample is already an `imageblock_store`, so the pair is reachable.
//
// LIVENESS: the destination pixel is dst*2 + src, with a NON-ZERO clear colour
// supplied by the harness, so forcing the tile read to zero collapses the pixel
// to `src` alone -- the same litmus-power control EXP-0147 used for tile_read.
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
                       float4 dst [[color(0)]],
                       device const float *in [[buffer(0)]])
{
    float4 src = float4(in[8], in[9], in[10], in[6] * in[7]);
    return dst * 2.0f + src;
}
