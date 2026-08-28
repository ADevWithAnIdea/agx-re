// EXP-0135 mesh_indirect.metal — OWN-SHADER object-less mesh pipeline for the
// indirect-draw (Group I) sweep, plus the tiny compute kernel that writes the
// MTLDispatchThreadgroupsIndirectArguments-shaped (3x uint32) record consumed
// by -drawMeshThreadgroupsWithIndirectBuffer:indirectBufferOffset:... (public
// Metal API, MTLRenderCommandEncoder.h). No object function: per
// MTLMeshRenderPipelineDescriptor.h, "If this is nil ... the draw command
// determines how many threadgroups of the mesh stage to run" -- so the
// indirect buffer's X directly controls the mesh threadgroup count with no
// object-stage amplification in between, isolating the indirect mechanism's
// own boundary behavior from AMP_COUNT (tested separately in mesh_sweep.metal).
//
// Clean-room: OUR OWN MSL only, public runtime compile API.

#include <metal_stdlib>
#include <metal_mesh>
using namespace metal;

struct VOut {
    float4 position [[position]];
    float4 color;
};
struct POut {
    float3 pnormal [[flat]];
};

using tri_mesh = metal::mesh<VOut, POut, 3, 1, metal::topology::triangle>;

[[mesh, max_total_threads_per_threadgroup(3)]]
void mesh_main_noobj(tri_mesh out, uint lane [[thread_index_in_threadgroup]],
                      uint tgid [[threadgroup_position_in_grid]]) {
    if (lane == 0)
        out.set_primitive_count(1);
    float2 off = float2(float(tgid % 8u) * 0.22f - 0.85f,
                         float((tgid / 8u) % 8u) * 0.22f - 0.85f);
    float2 P[3] = { float2(-0.08, -0.08), float2(0.08, -0.08), float2(0.0, 0.08) };
    VOut v;
    v.position = float4(P[lane] + off, 0.0, 1.0);
    v.color = float4(0.0, 1.0, 0.0, 1.0);
    out.set_vertex(lane, v);
    out.set_index(lane, uchar(lane));
    if (lane == 0) {
        POut po;
        po.pnormal = float3(0.0, 0.0, 1.0);
        out.set_primitive(0, po);
    }
}

fragment float4 frag_main_noobj(VOut in [[stage_in]]) {
    return in.color;
}

// Writes a caller-supplied (X,Y,Z) into a buffer shaped exactly like the
// public MTLDispatchThreadgroupsIndirectArguments struct (3x uint32), with a
// caller-controlled byte offset -- lets the harness place the record at an
// arbitrary offset to test -indirectBufferOffset: alignment behavior
// (mirrors EXP-0098/0124's compute-indirect-dispatch methodology, now applied
// to the mesh indirect-draw grammar).
kernel void indirect_writer(device uchar *buf [[buffer(0)]],
                             constant uint3 &xyz [[buffer(1)]],
                             constant uint &byteOffset [[buffer(2)]]) {
    device uint *p = (device uint *)(buf + byteOffset);
    p[0] = xyz.x;
    p[1] = xyz.y;
    p[2] = xyz.z;
}
