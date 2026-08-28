#include <metal_stdlib>
using namespace metal;

// EXP-0127 task 2/3: FS selector redirect probe. One shared vertex function
// (producing an interpolated varying, matching EXP-0042/EXP-0110's
// stage_matrix.metal MatrixOut shape -- calibration in work/ showed a
// fragment function that does NOT consume any [[stage_in]] varying takes a
// different code path that never populates the pool+0x08 selector this
// experiment targets); three fragment functions of DELIBERATELY different
// compiled sizes and DISTINCT, easily distinguished solid outputs, so a
// successful redirect (hardware executes a different FS than the one the
// pipeline bind nominally selected) is unambiguous from the read-back pixel
// alone, independent of any structural byte decode.

struct VOut {
    float4 position [[position]];
    float2 uv;
};

vertex VOut vs_main(uint vertex_id [[vertex_id]],
                    const device float2 *positions [[buffer(0)]],
                    const device float4 *params [[buffer(1)]])
{
    VOut out;
    out.position = float4(positions[vertex_id], 0.0f, 1.0f);
    out.uv = params[1].xy;
    return out;
}

// Small: solid red. `in.uv` is folded in through a RUNTIME (buffer) scale
// (params[0].z), not a compile-time literal -- calibration (work/calib_fs.m,
// see PROGRESS.md) found that an earlier draft using a literal `* 0.0f`
// let the compiler constant-fold the varying read away entirely (provably
// zero regardless of in.uv), which silently produced a fragment function
// that does not consume its [[stage_in]] input and does not populate the
// pool+0x08 selector this experiment targets. A runtime-valued scale cannot
// be constant-folded, so the varying read is genuinely live.
fragment float4 fs_red(VOut in [[stage_in]],
                       const device float4 *params [[buffer(0)]])
{
    return float4(1.0f, 0.0f, 0.0f, 1.0f) * params[0].w + in.uv.xyxy * params[0].z;
}

// Medium: solid green, with enough extra arithmetic to differ in compiled
// size from fs_red (mirrors EXP-0042's small/large FS separation).
fragment float4 fs_green(VOut in [[stage_in]],
                         const device float4 *params [[buffer(0)]])
{
    float4 c = float4(0.0f, 1.0f, 0.0f, 1.0f) + in.uv.xyxy * params[0].z;
    for (uint i = 0; i < 9; ++i)
        c = fma(c, params[0], float4(0.0f, 1.0f, 0.0f, 0.0f));
    return c * params[0].w;
}

// Large: solid blue, larger again than fs_green.
fragment float4 fs_blue(VOut in [[stage_in]],
                        const device float4 *params [[buffer(0)]])
{
    float4 c = float4(0.0f, 0.0f, 1.0f, 1.0f) + in.uv.xyxy * params[0].z;
    for (uint i = 0; i < 21; ++i)
        c = fma(c, params[0], float4(0.0f, 0.0f, 1.0f, 0.0f));
    return c * params[0].w;
}
