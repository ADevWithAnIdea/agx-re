// EXP-O2H tessellation kernels — OUR OWN MSL.
//
// A minimal Metal tessellation pipeline exactly as Metal exposes it on Apple9:
//   1. a COMPUTE kernel writes per-patch tessellation factors into an MTLBuffer
//      (half format: MTL{Triangle,Quad}TessellationFactorsHalf layout), and
//   2. a POST-TESSELLATION VERTEX FUNCTION ([[patch(triangle|quad,N)]]) consumes
//      the generated domain points ([[position_in_patch]]) + patch control points,
//   3. an ordinary fragment shader.
//
// CLEAN-ROOM: OWN-SHADER. Our own source; we only inspect what WE compiled.

#include <metal_stdlib>
using namespace metal;

// ----- tessellation-factor structs (half format) -----
// Layout matches Metal's MTLTriangleTessellationFactorsHalf (8 B) and
// MTLQuadTessellationFactorsHalf (12 B) exactly (edges then inside factors).
struct TriTessFactorsHalf  { half edge[3]; half inside; };
struct QuadTessFactorsHalf { half edge[4]; half insideX; half insideY; };

// ----- compute kernels: write per-patch tessellation factors -----
kernel void tess_factors_tri(device TriTessFactorsHalf *f [[buffer(0)]],
                             constant float &level         [[buffer(1)]],
                             uint pid [[thread_position_in_grid]]) {
    f[pid].edge[0] = half(level);
    f[pid].edge[1] = half(level);
    f[pid].edge[2] = half(level);
    f[pid].inside  = half(level);
}

kernel void tess_factors_quad(device QuadTessFactorsHalf *f [[buffer(0)]],
                              constant float &level          [[buffer(1)]],
                              uint pid [[thread_position_in_grid]]) {
    f[pid].edge[0] = half(level); f[pid].edge[1] = half(level);
    f[pid].edge[2] = half(level); f[pid].edge[3] = half(level);
    f[pid].insideX = half(level); f[pid].insideY = half(level);
}

// ----- post-tessellation vertex function input -----
struct CP      { float4 position [[attribute(0)]]; };
struct PatchIn { patch_control_point<CP> cp; };
struct VOut    { float4 position [[position]]; float4 color; };

// Post-tessellation vertex function for TRIANGLE patches.
// bary = [[position_in_patch]] is float3 (barycentric domain coordinate).
// `bulge` (vertex buffer 1) radially displaces domain points so that the rendered
// silhouette is TESSELLATION-LEVEL DEPENDENT -> proves subdivision on hardware.
[[patch(triangle, 3)]]
vertex VOut tess_vertex_tri(PatchIn in [[stage_in]],
                            float3 bary   [[position_in_patch]],
                            constant float &bulge [[buffer(1)]]) {
    float4 p = in.cp[0].position * bary.x
             + in.cp[1].position * bary.y
             + in.cp[2].position * bary.z;
    float e = bary.x*bary.y + bary.y*bary.z + bary.z*bary.x; // 0 at corners
    float2 dir = normalize(p.xy + float2(1e-6, 1e-6));
    float2 xy  = p.xy + dir * (bulge * e);
    VOut o; o.position = float4(xy, 0, 1); o.color = float4(bary, 1.0); return o;
}

// Post-tessellation vertex function for QUAD patches.
// uv = [[position_in_patch]] is float2 (u,v domain coordinate).
[[patch(quad, 4)]]
vertex VOut tess_vertex_quad(PatchIn in [[stage_in]],
                             float2 uv    [[position_in_patch]],
                             constant float &bulge [[buffer(1)]]) {
    float4 top = mix(in.cp[0].position, in.cp[1].position, uv.x);
    float4 bot = mix(in.cp[3].position, in.cp[2].position, uv.x);
    float4 p   = mix(top, bot, uv.y);
    float e = 4.0 * uv.x*(1.0-uv.x) * uv.y*(1.0-uv.y);        // 0 at corners
    float2 dir = normalize(p.xy + float2(1e-6, 1e-6));
    float2 xy  = p.xy + dir * (bulge * e);
    VOut o; o.position = float4(xy, 0, 1); o.color = float4(uv, 0, 1); return o;
}

fragment float4 tess_frag(VOut in [[stage_in]]) { return in.color; }
