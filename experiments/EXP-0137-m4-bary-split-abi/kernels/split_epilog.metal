// split_epilog.metal -- EXP-0129 H2: a genuinely SEPARATE ("noinline"),
// CALL-boundary-crossing programmable-blend EPILOG (OWN-SHADER).
//
// EXP-0109 (S5.1) established that Metal's OWN compiler never produces a
// separate prolog/epilog code OBJECT -- every compiled fragment program is
// exactly ["_agc.main.constant_program", "_agc.main"]. This file constructs,
// by hand, what a DRIVER-implemented split would have to look like GIVEN
// that fact: the "epilog" is an ordinary noinline MSL function (so a driver
// backend emitting AGX bytes directly can, if it wants to, generate the
// epilog's code once and CALL it from many different "main" bodies via the
// CALL/RETURN ABI EXP-0035/EXP-0109/EXP-0117 already decoded -- args in
// r10,r11,..., return in r10). MSL's tile-read mechanism (programmable-
// blend's [[color(n)]] fragment-function INPUT) is only valid on the ENTRY
// function (see split_negctrl.metal's negative control), so the entry point
// reads it and forwards the value into the callee as a plain argument --
// exactly the seam contract RESULTS.md documents.

#include <metal_stdlib>
using namespace metal;

struct BlendParams {
    float4 srcFactor;
    float4 dstFactor;
    uint   mode;   // 0 = Add-shaped (s+d), 1 = Mul-shaped (s*d) -- a real
                   // BRANCH inside the called "epilog", not just straight-
                   // line code, so the CALL-boundary construction also
                   // covers control flow inside a callee.
};

// The "epilog" -- NOT an entry point, ordinary MSL function, marked
// noinline so Metal's compiler cannot fold it back into the caller (defeats
// the whole point of constructing a genuine CALL boundary).
[[clang::noinline]] float4 do_blend_epilog(float4 src, float4 dst, constant BlendParams &p) {
    float4 s = src * p.srcFactor;
    float4 d = dst * p.dstFactor;
    if (p.mode == 0u) {
        return s + d;
    } else {
        return s * d;
    }
}

struct VOutC { float4 position [[position]]; };
vertex VOutC v_split_common(uint vid [[vertex_id]]) {
    // Fullscreen triangle so every pixel in a small render target is covered
    // (no coverage ambiguity to worry about for this ABI-mechanics probe).
    float2 p3[3] = { float2(-1.0,-1.0), float2(3.0,-1.0), float2(-1.0,3.0) };
    VOutC o;
    o.position = float4(p3[vid % 3], 0.0, 1.0);
    return o;
}

// The "main" (entry function): reads the tilebuffer destination via the
// MSL-mandated [[color(0)]] INPUT (only legal on an entry point), reads the
// "shader-computed" source color and blend params from ordinary buffers,
// and hands BOTH off to the noinline epilog -- the seam this experiment
// characterizes.
fragment float4 f_split_epilog(float4 dst [[color(0)]],
                                constant float4 &srcColor [[buffer(0)]],
                                constant BlendParams &bp [[buffer(1)]]) {
    return do_blend_epilog(srcColor, dst, bp);
}
