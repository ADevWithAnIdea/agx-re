// blend.metal -- EXP-0117 programmable-blend-epilog probe kernels (OWN-SHADER).
//
// Every function here is authored by us and compiled through the public
// Metal runtime (harness/blend_probe.m). The SOURCE color for the
// fixed-function blend sweep is buffer-driven (not baked into the shader),
// so ONE compiled pipeline per (pixel-format, blend-state) combination
// serves every src/dst COLOR-VALUE case; the harness varies the blend
// STATE (factors/op/mask/constant) via the MTLRenderPipelineColorAttachment-
// Descriptor / MTLRenderCommandEncoder, exactly the fields a driver's own
// epilog generator would need to key off.
//
// f_logic_* are the PROGRAMMABLE-EPILOG path: MSL has no logic-op blend
// mode (Vulkan VK_LOGIC_OP_*), so these hand-implement it via the same
// mechanism EXP-0029 already decoded structurally (tile_read `0x67`
// byte+1==0x0e, a `[[color(n)]]` FRAGMENT-FUNCTION INPUT) -- this is the
// literal shape of "what a future epilog generator must emit" for a blend
// mode the fixed-function-shaped API surface cannot express.

#include <metal_stdlib>
using namespace metal;

// A single triangle deliberately over-covering the whole viewport ("full-
// screen triangle"), so every sampled pixel is inside the primitive and no
// geometric edge/AA interaction confounds the blend-math readback.
vertex float4 v_full(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    return float4(p[vid % 3], 0.0, 1.0);
}

// ---- fixed-function blend sweep: SOURCE color from a buffer -----------------
// No [[color(0)]] INPUT is declared here -- this is also the STRUCTURAL
// control for "does blendingEnabled=YES alone (a pipeline-descriptor
// property, no shader-source change) cause the compiled bytes to gain a
// tile_read op" (harness --mode struct compiles this SAME function with
// blendingEnabled NO vs YES and diffs the extracted bytes).
fragment float4 f_solid(constant float4 &src [[buffer(0)]]) {
    return src;
}

// Dual-source variant, needed to even CONSTRUCT the Source1Color/
// OneMinusSource1Color/Source1Alpha/OneMinusSource1Alpha blend-factor
// tests -- Metal rejects a pipeline selecting an index(1) factor unless the
// fragment shader itself declares an index(1) output (own-compiler
// diagnostic, captured verbatim: "Fragment shader does not write to render
// target color(0), index(1) that is required for blending").
struct DualSrcSolid { float4 c0 [[color(0), index(0)]]; float4 c1 [[color(0), index(1)]]; };
fragment DualSrcSolid f_solid_dualsrc(constant float4 &src0 [[buffer(0)]], constant float4 &src1 [[buffer(1)]]) {
    DualSrcSolid o; o.c0 = src0; o.c1 = src1; return o;
}

// ---- MRT ceiling family (extends EXP-0109 Sec 3.1's 1/2/4 to the full
// MTLRenderPipelineColorAttachmentDescriptorArray range, natt=1..8) --------
struct VOutMrt { float4 position [[position]]; float4 c0; };
vertex VOutMrt v_mrt(uint vid [[vertex_id]]) {
    VOutMrt o;
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    o.position = float4(p[vid % 3], 0.0, 1.0);
    o.c0 = float4(0.7, 0.5, 0.3, 0.9); // arbitrary, non-trivial, distinguishable-by-scale
    return o;
}
struct MRT5 { float4 c0[[color(0)]]; float4 c1[[color(1)]]; float4 c2[[color(2)]]; float4 c3[[color(3)]]; float4 c4[[color(4)]]; };
struct MRT6 { float4 c0[[color(0)]]; float4 c1[[color(1)]]; float4 c2[[color(2)]]; float4 c3[[color(3)]]; float4 c4[[color(4)]]; float4 c5[[color(5)]]; };
struct MRT7 { float4 c0[[color(0)]]; float4 c1[[color(1)]]; float4 c2[[color(2)]]; float4 c3[[color(3)]]; float4 c4[[color(4)]]; float4 c5[[color(5)]]; float4 c6[[color(6)]]; };
struct MRT8 { float4 c0[[color(0)]]; float4 c1[[color(1)]]; float4 c2[[color(2)]]; float4 c3[[color(3)]]; float4 c4[[color(4)]]; float4 c5[[color(5)]]; float4 c6[[color(6)]]; float4 c7[[color(7)]]; };
fragment MRT5 f_mrt5(VOutMrt in [[stage_in]]) { MRT5 o;
    o.c0=in.c0*0.1; o.c1=in.c0*0.2; o.c2=in.c0*0.3; o.c3=in.c0*0.4; o.c4=in.c0*0.5; return o; }
fragment MRT6 f_mrt6(VOutMrt in [[stage_in]]) { MRT6 o;
    o.c0=in.c0*0.1; o.c1=in.c0*0.2; o.c2=in.c0*0.3; o.c3=in.c0*0.4; o.c4=in.c0*0.5; o.c5=in.c0*0.6; return o; }
fragment MRT7 f_mrt7(VOutMrt in [[stage_in]]) { MRT7 o;
    o.c0=in.c0*0.1; o.c1=in.c0*0.2; o.c2=in.c0*0.3; o.c3=in.c0*0.4; o.c4=in.c0*0.5; o.c5=in.c0*0.6; o.c6=in.c0*0.7; return o; }
fragment MRT8 f_mrt8(VOutMrt in [[stage_in]]) { MRT8 o;
    o.c0=in.c0*0.1; o.c1=in.c0*0.2; o.c2=in.c0*0.3; o.c3=in.c0*0.4; o.c4=in.c0*0.5; o.c5=in.c0*0.6; o.c6=in.c0*0.7; o.c7=in.c0*0.8; return o; }

// ---- programmable-blend epilog (logic ops via tile_read) --------------------
// R32Uint attachment: raw-bit semantics, well-defined for bitwise ops.
fragment uint f_logic_and(uint dst [[color(0)]], constant uint &src [[buffer(0)]]) { return src & dst; }
fragment uint f_logic_or (uint dst [[color(0)]], constant uint &src [[buffer(0)]]) { return src | dst; }
fragment uint f_logic_xor(uint dst [[color(0)]], constant uint &src [[buffer(0)]]) { return src ^ dst; }
fragment uint f_logic_inv(uint dst [[color(0)]], constant uint &src [[buffer(0)]]) { return ~dst; } // src unused; INVERT-style
fragment uint f_logic_copy(uint dst [[color(0)]], constant uint &src [[buffer(0)]]) { (void)dst; return src; } // COPY: reads dst syntactically but ignores its value -- structural control

// ---- alpha-to-coverage / alpha-to-one ---------------------------------------
fragment float4 f_alpha_out(constant float4 &src [[buffer(0)]]) { return src; }
