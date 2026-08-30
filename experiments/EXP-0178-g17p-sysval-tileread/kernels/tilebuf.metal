// EXP-0178 tilebuffer-read carriers -- OWN-SHADER MSL authored for this
// experiment. Target 2 is a TARGET CHANGE, not a fresh investigation:
// `f_tile` and `f_mrt` reproduce our own EXP-0147 carriers exactly so that the
// G17P numbers are directly comparable to the M4 numbers they must confirm or
// refute; `f_tile2` and `f_mrt3` are the SECOND, structurally different carriers
// EXP-0164 demanded before any never-moving field can be ruled on.
//
// The driver-safety fact under re-verification (EXP-0147, M4):
//   byte+6 bit 0 is a READ-ENABLE whose EVEN values return a SILENT ZERO rather
//   than faulting, and a wrong `rt_index` does the same. In a BG/EOT program
//   that is a BLACK TILE, not a loud failure.
//
// CO-VARIATION AUDIT (FIELD-SWEEP-PROTOCOL section 3a): the observable is the
// resolved colour attachment, produced by `frag_color_store` /
// `imageblock_store` -- an instruction no arm here ever splices. The fields
// under test all live inside the `tile_read` / `tile_read_mrt` instruction.
// Sweeping `tile_read.dst` moves the READ's destination while the consuming ALU
// still reads the ORIGINAL register, so a correct hardware result is a CHANGED
// pixel, never a constant one; the observable does not co-vary with the field.
//
// The clear colour is the tilebuffer's resident value AND the fixed-function
// integrity sentinel: it is written by hardware on a path that cannot involve
// the fragment program, so a pixel still holding it exactly means nothing was
// drawn (EXP-0141's "STATUS OK, nothing executed"). Every carrier's inputs are
// chosen so the CORRECT value, the SILENT-ZERO value and the CLEAR value differ
// in every component.
//
// CLEAN-ROOM: public Metal API on our own MSL. No Apple binary is disassembled,
// decompiled or introspected.

#include <metal_stdlib>
using namespace metal;

// ------------------------------------------------------------------ vertex --
// Full-screen triangle from an indexed constant array + a uniform, so the
// vertex stage also drives a spatial gradient that proves vertex-stage output
// reaches the observed pixels. (Same shape as our EXP-0147 `v_arr`.)
struct VOutC { float4 pos [[position]]; float4 vc; };
vertex VOutC v_arr(uint vid [[vertex_id]], constant float4 &vp [[buffer(0)]]) {
    float2 p[3] = { float2(-1.0, -1.0), float2(3.0, -1.0), float2(-1.0, 3.0) };
    VOutC o;
    o.pos = float4(p[vid], 0.0, 1.0);
    o.vc  = vp * float(vid + 1);
    return o;
}

// ---------------------------------------------------------- CT1: tile_read --
// One attachment, programmable blending. The genuinely non-foldable ALU
// (`dst*2 + src`, src a runtime uniform) stops the compiler eliding the read
// the way EXP-0130 / EXP-0117 saw for a pure passthrough (`return dst;`
// compiles to 16 bytes containing NEITHER opcode).
fragment float4 f_tile(float4 dst [[color(0)]], constant float4 &src [[buffer(0)]]) {
    return dst * 2.0 + src;
}

// ------------------------------------- CT2: tile_read, second carrier --------
// Structurally different from CT1 in FOUR dimensions at once: attachment COUNT
// (2 vs 1 -- the dimension `rt_index` demonstrably controls), spatial extent
// (4x4 vs 2x2), the arithmetic combining the read value, and the presence of a
// second colour store that does NOT read the tilebuffer.
// Which anchor this compiles to (`67 0e 54` or `67 06 54`) is resolved from the
// compiled bytes before the first gated dispatch and recorded; the arm is
// attributed to the instruction actually found.
struct T2Out { float4 c0 [[color(0)]]; float4 c1 [[color(1)]]; };
fragment T2Out f_tile2(float4 dst [[color(0)]],
                       constant float4 &src [[buffer(0)]]) {
    T2Out o;
    o.c0 = dst * (-3.0) + src * 0.5;
    o.c1 = src * 7.0 - float4(0.125, 0.25, 0.5, 1.0);
    return o;
}

// ------------------------------------------------------ CM1: tile_read_mrt --
// Two colour attachments, both read and both written, each with a DIFFERENT
// combine so a mis-routed render-target index is visible.
struct MRTOut { float4 c0 [[color(0)]]; float4 c1 [[color(1)]]; };
fragment MRTOut f_mrt(float4 d0 [[color(0)]], float4 d1 [[color(1)]],
                      constant float4 &src [[buffer(0)]]) {
    MRTOut o;
    o.c0 = d0 * 2.0 + src;
    o.c1 = d1 * 4.0 - src;
    return o;
}

// -------------------------------- CM2: tile_read_mrt, second carrier --------
// THREE attachments, all read and all written with mutually distinct combines,
// at 2x2 instead of 1x1. Widens exactly the dimension `rt_index` selects: with
// three slots bound, an index that silently zeroes on M4 with one attachment
// has more legal neighbours to be wrong about.
struct MRT3Out { float4 c0 [[color(0)]]; float4 c1 [[color(1)]]; float4 c2 [[color(2)]]; };
fragment MRT3Out f_mrt3(float4 d0 [[color(0)]], float4 d1 [[color(1)]],
                        float4 d2 [[color(2)]], constant float4 &src [[buffer(0)]]) {
    MRT3Out o;
    o.c0 = d0 * 2.0 + src;
    o.c1 = d1 * 4.0 - src;
    o.c2 = d2 * (-0.5) + src * 3.0;
    return o;
}
