// r_fcp1.metal -- EXP-0168 FRAGMENT carrier for `frag_color_pack.dst`, the
// SINGLE-RENDER-TARGET, LITERAL-SOURCE shape.
//
// Serves TWO carriers that differ in ONE pipeline parameter, which makes them a
// controlled pair in the sense EXP-0163's cent1/cent4 established:
//     r_fcp1   -- BGRA8Unorm, 1 RT, rasterSampleCount 1
//     r_fcp1s  -- BGRA8Unorm, 1 RT, rasterSampleCount 4 + multisample resolve
// (Metal lowers the multisampled fragment build differently, so these are a
// controlled comparison of the same source under one changed pipeline
// parameter, NOT a byte-for-byte splice pair.  EXP-0163's RESULTS.md sec.2 was
// corrected on exactly this point and the correction is honoured here.)
//
// WHAT WAS WRONG WITH THE PRIOR EVIDENCE.  EXP-0164 withheld
// `frag_color_pack.dst` as UNSTABLE: 208 values, "2 carriers", 32 moved, failed
// cross-run agreement.  Its two "carriers" `fcp@pack0` and `fcp@pack1` are TWO
// OCCURRENCES OF THE SAME INSTRUCTION IN ONE PROGRAM -- one source file, one
// attachment format (BGRA8Unorm, color_format 80), one render target, one
// sample.  That is ONE carrier, counted twice.  Two carriers identical in the
// dimension the field controls are one carrier.
//
// THE DIMENSION `dst` CONTROLS is WHICH GPR FEEDS THE TILEBUFFER STORE.  This
// file is the CONTROL end of that dimension: 1 render target, 4 colour
// channels, colour values written as LITERALS so the compiler is free to fold
// them into the pack's own immediate operand (`val`, byte+6) -- which is
// precisely why `val` is a usable liveness control here, as EXP-0155 found.
// r_fcpmrt.metal is the other end: 4 render targets, 16 channels, all
// runtime-sourced so the packs must read registers.
//
// The four channel values are 0.2 / 0.4 / 0.6 / 0.8, which land on the exact
// 8-bit unorm codes 51 / 102 / 153 / 204 with no quantization ambiguity, so the
// read-back byte is an exact oracle.  Values are equal at all three vertices, so
// interpolation is exact over the whole primitive.
//
// Full-screen triangle, so every probe pixel is covered.
//
// CLEAN-ROOM: OWN-SHADER.  No Apple binary is disassembled.
#include <metal_stdlib>
using namespace metal;

struct VOutC4 {
    float4 pos [[position]];
    float c0; float c1; float c2; float c3;
};

vertex VOutC4 v_main(uint vid [[vertex_id]])
{
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOutC4 o;
    o.pos = float4(p * 2.0f - 1.0f, 0.0f, 1.0f);
    o.c0 = 0.2f;
    o.c1 = 0.4f;
    o.c2 = 0.6f;
    o.c3 = 0.8f;
    return o;
}

fragment float4 f_main(VOutC4 in [[stage_in]])
{
    return float4(in.c0, in.c1, in.c2, in.c3);
}
