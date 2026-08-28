#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 position [[position]];
};

// Shared trivial fragment: returns a host-provided uniform colour. Kept
// IDENTICAL across every pipeline in this file so any observed VDM/pool
// selector difference between pipelines is attributable only to the VS
// side (mirrors EXP-0042's stage-matrix separation of VS vs FS fields).
fragment float4 fs_flat(const device float4 *colour [[buffer(1)]])
{
    return colour[0];
}

vertex VOut vs_u0000(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(0 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0001(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(1 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0002(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(2 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0003(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(3 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0004(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(4 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0005(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(5 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0006(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(6 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0007(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(7 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0008(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(8 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0009(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(9 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0010(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(10 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0011(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(11 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0012(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(12 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0013(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(13 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0014(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(14 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0015(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(15 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0016(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(16 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0017(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(17 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0018(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(18 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0019(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(19 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0020(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(20 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0021(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(21 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0022(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(22 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0023(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(23 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0024(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(24 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0025(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(25 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0026(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(26 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0027(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(27 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0028(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(28 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0029(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(29 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0030(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(30 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0031(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(31 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0032(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(32 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0033(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(33 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0034(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(34 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0035(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(35 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0036(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(36 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0037(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(37 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0038(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(38 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0039(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(39 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0040(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(40 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0041(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(41 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0042(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(42 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0043(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(43 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0044(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(44 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0045(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(45 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0046(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(46 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0047(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(47 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0048(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(48 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0049(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(49 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0050(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(50 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0051(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(51 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0052(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(52 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0053(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(53 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0054(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(54 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0055(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(55 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0056(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(56 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0057(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(57 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0058(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(58 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0059(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(59 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0060(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(60 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0061(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(61 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0062(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(62 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0063(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(63 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0064(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(64 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0065(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(65 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0066(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(66 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0067(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(67 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0068(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(68 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0069(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(69 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0070(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(70 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0071(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(71 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0072(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(72 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0073(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(73 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0074(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(74 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0075(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(75 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0076(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(76 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0077(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(77 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0078(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(78 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0079(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(79 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0080(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(80 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0081(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(81 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0082(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(82 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0083(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(83 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0084(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(84 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0085(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(85 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0086(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(86 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0087(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(87 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0088(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(88 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0089(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(89 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0090(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(90 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0091(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(91 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0092(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(92 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0093(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(93 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0094(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(94 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0095(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(95 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0096(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(96 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0097(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(97 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0098(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(98 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0099(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(99 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0100(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(100 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0101(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(101 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0102(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(102 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0103(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(103 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0104(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(104 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0105(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(105 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0106(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(106 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0107(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(107 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0108(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(108 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0109(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(109 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0110(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(110 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0111(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(111 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0112(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(112 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0113(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(113 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0114(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(114 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0115(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(115 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0116(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(116 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0117(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(117 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0118(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(118 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0119(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(119 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0120(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(120 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0121(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(121 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0122(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(122 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0123(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(123 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0124(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(124 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0125(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(125 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0126(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(126 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0127(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(127 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0128(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(128 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0129(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(129 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0130(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(130 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0131(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(131 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0132(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(132 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0133(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(133 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0134(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(134 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0135(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(135 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0136(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(136 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0137(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(137 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0138(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(138 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0139(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(139 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0140(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(140 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0141(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(141 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0142(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(142 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0143(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(143 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0144(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(144 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0145(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(145 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0146(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(146 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0147(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(147 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0148(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(148 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0149(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(149 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0150(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(150 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0151(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(151 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0152(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(152 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0153(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(153 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0154(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(154 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0155(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(155 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0156(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(156 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0157(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(157 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0158(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(158 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0159(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(159 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0160(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(160 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0161(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(161 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0162(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(162 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0163(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(163 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0164(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(164 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0165(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(165 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0166(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(166 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0167(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(167 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0168(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(168 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0169(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(169 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0170(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(170 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0171(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(171 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0172(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(172 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0173(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(173 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0174(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(174 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0175(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(175 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0176(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(176 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0177(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(177 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0178(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(178 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0179(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(179 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0180(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(180 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0181(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(181 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0182(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(182 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0183(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(183 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0184(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(184 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0185(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(185 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0186(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(186 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0187(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(187 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0188(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(188 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0189(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(189 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0190(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(190 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0191(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(191 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0192(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(192 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0193(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(193 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0194(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(194 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0195(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(195 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0196(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(196 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0197(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(197 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0198(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(198 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0199(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(199 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0200(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(200 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0201(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(201 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0202(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(202 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0203(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(203 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0204(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(204 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0205(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(205 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0206(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(206 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0207(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(207 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0208(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(208 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0209(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(209 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0210(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(210 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0211(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(211 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0212(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(212 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0213(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(213 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0214(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(214 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0215(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(215 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0216(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(216 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0217(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(217 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0218(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(218 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0219(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(219 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0220(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(220 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0221(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(221 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0222(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(222 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0223(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(223 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0224(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(224 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0225(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(225 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0226(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(226 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0227(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(227 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0228(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(228 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0229(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(229 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0230(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(230 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0231(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(231 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0232(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(232 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0233(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(233 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0234(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(234 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0235(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(235 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0236(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(236 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0237(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(237 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0238(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(238 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0239(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(239 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0240(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(240 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0241(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(241 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0242(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(242 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0243(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(243 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0244(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(244 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0245(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(245 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0246(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(246 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0247(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(247 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0248(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(248 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0249(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(249 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0250(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(250 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0251(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(251 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0252(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(252 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0253(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(253 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0254(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(254 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0255(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(255 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0256(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(256 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0257(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(257 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0258(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(258 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0259(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(259 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0260(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(260 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0261(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(261 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0262(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(262 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0263(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(263 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0264(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(264 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0265(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(265 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0266(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(266 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0267(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(267 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0268(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(268 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0269(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(269 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0270(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(270 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0271(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(271 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0272(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(272 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0273(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(273 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0274(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(274 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0275(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(275 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0276(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(276 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0277(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(277 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0278(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(278 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0279(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(279 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0280(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(280 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0281(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(281 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0282(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(282 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0283(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(283 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0284(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(284 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0285(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(285 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0286(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(286 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0287(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(287 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0288(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(288 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0289(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(289 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0290(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(290 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0291(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(291 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0292(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(292 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0293(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(293 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0294(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(294 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0295(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(295 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0296(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(296 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0297(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(297 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0298(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(298 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0299(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(299 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0300(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(300 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0301(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(301 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0302(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(302 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0303(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(303 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0304(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(304 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0305(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(305 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0306(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(306 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0307(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(307 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0308(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(308 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0309(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(309 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0310(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(310 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0311(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(311 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0312(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(312 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0313(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(313 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0314(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(314 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0315(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(315 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0316(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(316 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0317(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(317 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0318(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(318 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0319(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(319 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0320(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(320 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0321(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(321 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0322(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(322 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0323(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(323 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0324(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(324 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0325(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(325 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0326(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(326 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0327(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(327 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0328(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(328 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0329(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(329 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0330(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(330 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0331(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(331 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0332(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(332 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0333(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(333 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0334(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(334 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0335(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(335 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0336(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(336 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0337(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(337 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0338(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(338 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0339(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(339 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0340(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(340 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0341(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(341 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0342(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(342 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0343(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(343 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0344(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(344 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0345(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(345 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0346(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(346 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0347(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(347 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0348(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(348 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0349(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(349 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0350(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(350 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0351(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(351 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0352(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(352 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0353(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(353 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0354(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(354 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0355(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(355 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0356(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(356 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0357(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(357 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0358(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(358 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0359(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(359 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0360(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(360 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0361(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(361 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0362(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(362 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0363(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(363 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0364(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(364 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0365(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(365 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0366(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(366 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0367(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(367 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0368(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(368 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0369(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(369 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0370(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(370 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0371(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(371 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0372(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(372 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0373(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(373 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0374(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(374 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0375(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(375 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0376(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(376 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0377(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(377 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0378(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(378 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0379(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(379 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0380(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(380 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0381(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(381 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0382(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(382 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0383(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(383 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0384(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(384 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0385(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(385 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0386(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(386 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0387(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(387 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0388(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(388 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0389(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(389 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0390(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(390 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0391(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(391 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0392(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(392 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0393(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(393 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0394(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(394 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0395(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(395 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0396(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(396 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0397(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(397 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0398(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(398 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0399(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(399 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0400(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(400 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0401(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(401 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0402(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(402 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0403(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(403 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0404(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(404 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0405(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(405 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0406(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(406 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0407(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(407 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0408(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(408 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0409(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(409 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0410(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(410 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0411(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(411 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0412(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(412 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0413(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(413 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0414(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(414 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0415(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(415 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0416(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(416 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0417(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(417 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0418(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(418 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0419(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(419 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0420(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(420 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0421(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(421 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0422(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(422 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0423(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(423 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0424(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(424 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0425(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(425 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0426(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(426 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0427(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(427 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0428(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(428 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0429(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(429 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0430(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(430 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0431(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(431 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0432(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(432 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0433(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(433 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0434(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(434 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0435(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(435 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0436(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(436 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0437(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(437 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0438(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(438 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0439(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(439 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0440(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(440 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0441(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(441 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0442(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(442 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0443(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(443 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0444(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(444 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0445(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(445 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0446(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(446 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0447(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(447 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0448(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(448 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0449(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(449 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0450(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(450 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0451(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(451 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0452(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(452 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0453(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(453 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0454(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(454 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0455(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(455 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0456(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(456 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0457(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(457 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0458(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(458 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0459(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(459 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0460(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(460 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0461(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(461 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0462(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(462 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0463(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(463 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0464(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(464 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0465(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(465 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0466(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(466 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0467(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(467 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0468(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(468 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0469(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(469 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0470(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(470 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0471(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(471 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0472(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(472 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0473(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(473 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0474(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(474 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0475(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(475 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0476(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(476 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0477(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(477 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0478(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(478 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0479(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(479 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0480(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(480 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0481(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(481 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0482(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(482 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0483(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(483 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0484(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(484 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0485(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(485 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0486(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(486 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0487(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(487 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0488(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(488 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0489(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(489 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0490(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(490 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0491(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(491 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0492(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(492 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0493(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(493 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0494(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(494 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0495(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(495 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0496(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(496 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0497(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(497 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0498(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(498 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0499(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(499 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0500(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(500 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0501(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(501 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0502(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(502 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0503(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(503 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0504(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(504 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0505(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(505 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0506(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(506 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0507(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(507 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0508(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(508 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0509(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(509 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0510(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(510 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0511(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(511 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0512(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(512 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0513(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(513 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0514(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(514 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0515(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(515 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0516(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(516 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0517(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(517 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0518(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(518 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0519(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(519 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0520(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(520 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0521(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(521 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0522(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(522 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0523(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(523 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0524(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(524 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0525(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(525 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0526(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(526 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0527(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(527 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0528(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(528 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0529(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(529 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0530(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(530 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0531(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(531 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0532(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(532 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0533(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(533 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0534(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(534 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0535(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(535 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0536(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(536 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0537(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(537 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0538(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(538 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0539(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(539 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0540(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(540 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0541(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(541 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0542(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(542 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0543(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(543 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0544(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(544 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0545(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(545 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0546(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(546 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0547(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(547 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0548(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(548 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0549(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(549 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0550(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(550 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0551(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(551 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0552(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(552 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0553(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(553 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0554(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(554 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0555(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(555 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0556(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(556 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0557(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(557 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0558(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(558 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0559(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(559 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0560(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(560 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0561(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(561 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0562(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(562 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0563(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(563 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0564(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(564 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0565(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(565 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0566(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(566 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0567(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(567 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0568(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(568 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0569(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(569 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0570(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(570 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0571(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(571 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0572(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(572 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0573(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(573 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0574(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(574 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0575(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(575 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0576(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(576 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0577(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(577 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0578(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(578 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0579(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(579 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0580(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(580 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0581(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(581 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0582(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(582 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0583(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(583 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0584(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(584 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0585(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(585 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0586(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(586 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0587(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(587 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0588(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(588 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0589(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(589 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0590(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(590 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0591(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(591 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0592(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(592 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0593(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(593 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0594(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(594 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0595(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(595 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0596(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(596 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0597(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(597 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0598(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(598 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0599(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(599 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0600(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(600 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0601(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(601 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0602(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(602 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0603(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(603 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0604(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(604 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0605(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(605 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0606(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(606 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0607(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(607 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0608(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(608 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0609(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(609 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0610(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(610 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0611(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(611 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0612(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(612 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0613(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(613 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0614(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(614 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0615(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(615 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0616(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(616 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0617(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(617 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0618(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(618 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0619(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(619 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0620(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(620 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0621(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(621 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0622(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(622 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0623(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(623 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0624(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(624 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0625(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(625 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0626(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(626 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0627(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(627 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0628(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(628 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0629(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(629 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0630(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(630 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0631(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(631 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0632(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(632 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0633(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(633 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0634(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(634 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0635(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(635 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0636(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(636 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0637(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(637 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0638(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(638 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0639(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(639 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0640(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(640 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0641(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(641 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0642(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(642 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0643(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(643 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0644(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(644 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0645(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(645 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0646(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(646 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0647(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(647 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0648(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(648 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0649(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(649 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0650(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(650 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0651(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(651 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0652(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(652 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0653(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(653 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0654(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(654 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0655(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(655 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0656(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(656 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0657(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(657 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0658(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(658 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0659(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(659 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0660(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(660 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0661(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(661 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0662(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(662 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0663(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(663 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0664(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(664 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0665(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(665 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0666(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(666 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0667(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(667 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0668(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(668 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0669(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(669 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0670(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(670 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0671(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(671 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0672(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(672 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0673(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(673 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0674(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(674 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0675(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(675 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0676(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(676 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0677(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(677 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0678(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(678 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0679(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(679 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0680(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(680 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0681(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(681 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0682(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(682 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0683(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(683 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0684(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(684 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0685(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(685 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0686(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(686 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0687(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(687 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0688(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(688 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0689(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(689 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0690(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(690 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0691(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(691 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0692(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(692 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0693(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(693 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0694(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(694 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0695(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(695 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0696(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(696 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0697(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(697 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0698(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(698 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0699(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(699 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0700(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(700 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0701(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(701 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0702(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(702 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0703(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(703 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0704(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(704 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0705(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(705 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0706(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(706 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0707(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(707 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0708(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(708 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0709(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(709 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0710(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(710 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0711(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(711 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0712(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(712 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0713(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(713 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0714(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(714 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0715(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(715 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0716(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(716 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0717(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(717 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0718(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(718 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0719(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(719 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0720(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(720 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0721(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(721 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0722(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(722 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0723(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(723 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0724(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(724 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0725(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(725 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0726(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(726 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0727(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(727 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0728(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(728 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0729(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(729 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0730(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(730 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0731(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(731 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0732(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(732 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0733(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(733 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0734(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(734 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0735(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(735 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0736(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(736 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0737(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(737 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0738(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(738 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0739(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(739 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0740(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(740 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0741(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(741 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0742(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(742 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0743(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(743 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0744(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(744 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0745(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(745 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0746(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(746 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0747(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(747 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0748(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(748 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0749(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(749 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0750(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(750 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0751(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(751 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0752(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(752 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0753(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(753 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0754(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(754 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0755(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(755 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0756(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(756 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0757(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(757 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0758(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(758 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0759(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(759 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0760(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(760 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0761(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(761 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0762(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(762 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0763(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(763 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0764(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(764 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0765(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(765 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0766(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(766 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0767(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(767 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0768(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(768 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0769(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(769 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0770(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(770 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0771(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(771 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0772(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(772 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0773(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(773 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0774(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(774 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0775(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(775 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0776(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(776 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0777(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(777 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0778(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(778 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0779(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(779 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0780(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(780 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0781(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(781 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0782(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(782 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0783(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(783 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0784(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(784 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0785(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(785 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0786(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(786 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0787(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(787 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0788(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(788 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0789(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(789 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0790(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(790 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0791(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(791 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0792(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(792 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0793(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(793 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0794(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(794 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0795(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(795 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0796(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(796 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0797(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(797 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0798(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(798 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_u0799(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    float2 p = positions[vertex_id] * float(799 % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}
