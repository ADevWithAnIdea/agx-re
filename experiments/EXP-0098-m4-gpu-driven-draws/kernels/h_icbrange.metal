// EXP-0098 Bundle H -- "h_icbrange" family. A compute kernel writes the
// MTLIndirectCommandBufferExecutionRange {location,length} record that
// executeCommandsInBuffer:indirectBuffer:indirectBufferOffset: consumes to
// select which slice of a CPU-pre-encoded ICB actually executes. This tests
// the device-generated draw-COUNT/range grammar (GLPRE-A02), not the vertex-
// data synchronization question (that is h_chain's job).
//
// The ICB's per-command render program is v_verify/f_noop (kernels/h_chain.metal
// re-declares the identical pair here for source self-containment -- each
// case compiles exactly one file via newLibraryWithSource:).

#include <metal_stdlib>
using namespace metal;

struct Range { uint location; uint length; };   // matches MTLIndirectCommandBufferExecutionRange

kernel void producer_icbrange(device Range *rangeOut [[buffer(0)]],
                               constant Range &p [[buffer(1)]],
                               uint gid [[thread_position_in_grid]]) {
    if (gid == 0) {
        rangeOut[0] = p;
    }
}

struct VOut { float4 pos [[position]]; };
// seen[] index = clamp(iid,0,instanceCap-1)*vertexCap + clamp(vid,0,vertexCap-1).
// instanceCap must cover baseInstance+instanceCount: [[instance_id]] reports the
// ABSOLUTE instance identifier (baseInstance-inclusive), not a 0-based local
// index -- confirmed empirically (build-time finding, see PRE_REGISTRATION.md);
// sizing seen[] to instanceCount alone silently under-allocates whenever
// baseInstance>0.
struct VerifyParams { uint vertexCap; uint instanceCap; };

// Both clamps are a HARNESS safety measure only (never activate on a correct,
// in-bounds path): they prevent an out-of-bounds device-buffer read/write if a
// deliberately-unsynchronized case's stale/garbage data produces a huge raw
// vid/iid, or if a field-legality probe deliberately requests an out-of-range
// value. seen[].z/.w always record the RAW (pre-clamp) vid/iid so a clamp
// event stays visible to analysis.
vertex VOut v_verify(uint vid [[vertex_id]],
                      uint iid [[instance_id]],
                      device const uint4 *vtxIn [[buffer(0)]],
                      device uint4 *seen [[buffer(1)]],
                      constant VerifyParams &vp [[buffer(2)]]) {
    uint vidx = min(vid, vp.vertexCap - 1u);
    uint iidx = min(iid, vp.instanceCap - 1u);
    uint4 src = vtxIn[vidx];
    seen[iidx * vp.vertexCap + vidx] = uint4(src.x, src.y, vid, iid);
    VOut o;
    o.pos = float4(0.0, 0.0, 0.0, 1.0);
    return o;
}

fragment float4 f_noop() {
    return float4(0.0, 0.0, 0.0, 0.0);
}
