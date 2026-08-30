// r_fcpmrt.metal -- EXP-0168 FRAGMENT carrier for `frag_color_pack.dst`, the
// FOUR-RENDER-TARGET, REGISTER-SOURCE shape.
//
// Serves TWO carriers that differ in ONE pipeline parameter:
//     r_fcp4  -- BGRA8Unorm (color_format 80), 4 RTs   -- packing REQUIRED
//     r_fcpf  -- RGBA32Float (color_format 125), 4 RTs -- packing may be ABSENT
//
// WHY FOUR TARGETS.  `frag_color_pack.dst` (byte+3) is a destination GPR
// selector; the dimension it controls is which register feeds the tilebuffer
// store.  With one render target there are two pack ops and a handful of live
// colour registers, so most redirections land on a register whose contents are
// indistinguishable from the original and the field reads inert-ish (EXP-0155:
// 32 of 208 moved, unstable across runs).  With FOUR targets there are sixteen
// live colour values in sixteen distinct registers, so redirecting one pack's
// destination onto another pack's register produces a DECODABLE cross-
// contamination -- the wrong channel shows a value that names the register it
// actually came from.  The set of live colour registers genuinely differs
// between r_fcp1 and r_fcp4; that is what makes them two carriers.
//
// WHY ALSO RGBA32Float.  A 32-bit float attachment needs no format conversion,
// so the compiler may emit NO `frag_color_pack` at all.  If the census finds
// zero occurrences in r_fcpf, that is a first-class structural result about
// when the instruction exists -- recorded, not treated as a failed build.
//
// SOURCE VALUES ARE RUNTIME-SOURCED (constant buffer), not literals, so they
// cannot be folded into the pack's immediate operand and the packs must read
// registers.  This is the deliberate complement of r_fcp1's literal sources: the
// `src_present_mask` byte db.json documents as "0xd0 = register source /
// 0x50 = immediate source" is exactly this distinction, so the pair spans it.
//
// The sixteen values are supplied by the harness as k/255 for sixteen distinct
// k, so under BGRA8Unorm each read-back byte equals its k exactly and names its
// own channel.  Values are identical at all three vertices, so interpolation is
// exact everywhere in the primitive.
//
// CLEAN-ROOM: OWN-SHADER.  No Apple binary is disassembled.
#include <metal_stdlib>
using namespace metal;

struct VOut16 {
    float4 pos [[position]];
    float4 a; float4 b; float4 c; float4 d;
};

struct FOut4 {
    float4 c0 [[color(0)]];
    float4 c1 [[color(1)]];
    float4 c2 [[color(2)]];
    float4 c3 [[color(3)]];
};

vertex VOut16 v_main(uint vid [[vertex_id]], constant float4 *u [[buffer(0)]])
{
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut16 o;
    o.pos = float4(p * 2.0f - 1.0f, 0.0f, 1.0f);
    o.a = u[0];
    o.b = u[1];
    o.c = u[2];
    o.d = u[3];
    return o;
}

fragment FOut4 f_main(VOut16 in [[stage_in]])
{
    FOut4 o;
    o.c0 = in.a;
    o.c1 = in.b;
    o.c2 = in.c;
    o.c3 = in.d;
    return o;
}
