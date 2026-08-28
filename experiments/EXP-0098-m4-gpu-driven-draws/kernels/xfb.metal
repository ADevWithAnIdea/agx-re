// EXP-0098 Bundle I -- compute-emulated transform-feedback (GLXFB-A01).
// Authored MSL only (OWN-SHADER). Models the OpenGL 4-buffer/4-stream
// transform-feedback capture using global-memory writes plus atomic
// counters, feeding a generated draw -- per the addendum's own instruction,
// this is a minimal experimental program, not production driver code.
//
// xfb_capture: one thread per synthetic input primitive (stands in for a
// VS/GS producer). Each primitive may fan out into up to 4 independent
// streams; each stream reserves space via an atomic cursor and writes ONLY
// if the WHOLE primitive's vertex block fits in the destination buffer's
// declared capacity -- modelling the required "no partial primitive" rule.
// "generated" increments unconditionally (matches GL_PRIMITIVES_GENERATED);
// "written" increments only for primitives that actually landed (matches
// GL_TRANSFORM_FEEDBACK_PRIMITIVES_WRITTEN / stream-specific query).
//
// Arbitrary byte offset/stride (including deliberately misaligned) is
// supported via a byte-wise store loop, modelling GL's arbitrary XFB buffer
// offset/stride contract. Interleaved vs. separate buffer layout is a
// property of which of buf0..buf3 the harness aliases to the same
// allocation, not of this kernel.
//
// xfb_finalize: a second, tiny compute kernel copies one stream's atomically
// accumulated "written" counter into a MTLDrawPrimitivesIndirectArguments
// vertexCount field -- the compute-writes-the-indirect-draw-record pattern
// from Bundle H, reused here for the streamout-generated replay draw
// (glDrawTransformFeedback's semantics: replay exactly the captured count).
//
// v_verify/f_noop: the same verification pipeline as kernels/h_chain.metal
// (re-declared here for source self-containment), confirms the replay draw
// actually issues exactly `written` vertex-stage invocations against the
// captured data.

#include <metal_stdlib>
using namespace metal;

struct XfbParams {
    uint numPrimitives;
    uint vertsPerPrimActive;
    uint vertsPerPrimAlt;
    uint activeMaskMode;   // 0=all 4 streams every primitive
                            // 1=stream0 only (passthrough baseline)
                            // 2=alternate (even prim->{0,1}, odd prim->{2,3})
                            // 3=GS-shaped fan-out (every prim -> stream0 @ vertsPerPrimActive
                            //    AND stream1 @ vertsPerPrimAlt, simultaneously, different counts)
    uint magicBase;
    uint spinIters;         // artificial per-thread sequential-dependency work
                             // to lengthen the capture dispatch's real GPU
                             // execution time (sync-family race-window
                             // calibration; see kernels/h_chain.metal's
                             // identical mechanism). Folded into the written
                             // record so the compiler cannot eliminate it.
};

struct XfbCounters { uint generated; uint reserved; uint written; uint _pad; };  // atomic_uint in-kernel view

kernel void xfb_capture(device uchar *buf0 [[buffer(0)]],
                         device uchar *buf1 [[buffer(1)]],
                         device uchar *buf2 [[buffer(2)]],
                         device uchar *buf3 [[buffer(3)]],
                         device atomic_uint *ctrGenerated [[buffer(4)]],   // [4]
                         device atomic_uint *ctrReserved [[buffer(5)]],    // [4]
                         device atomic_uint *ctrWritten [[buffer(6)]],     // [4]
                         constant XfbParams &p [[buffer(7)]],
                         constant uint4 &strides [[buffer(8)]],    // byteStride per stream
                         constant uint4 &offsets [[buffer(9)]],    // byteOffset per stream
                         constant uint4 &capsVerts [[buffer(10)]], // buffer capacity in vertices, per stream
                         uint gid [[thread_position_in_grid]])
{
    if (gid >= p.numPrimitives) return;
    device uchar *bufs[4] = {buf0, buf1, buf2, buf3};
    uint stride[4] = {strides.x, strides.y, strides.z, strides.w};
    uint offset[4] = {offsets.x, offsets.y, offsets.z, offsets.w};
    uint cap[4]    = {capsVerts.x, capsVerts.y, capsVerts.z, capsVerts.w};

    bool active[4] = {false, false, false, false};
    uint vpp[4]    = {0, 0, 0, 0};
    if (p.activeMaskMode == 0u) {
        active[0] = active[1] = active[2] = active[3] = true;
        vpp[0] = vpp[1] = vpp[2] = vpp[3] = p.vertsPerPrimActive;
    } else if (p.activeMaskMode == 1u) {
        active[0] = true; vpp[0] = p.vertsPerPrimActive;
    } else if (p.activeMaskMode == 2u) {
        if ((gid & 1u) == 0u) { active[0] = active[1] = true; vpp[0] = vpp[1] = p.vertsPerPrimActive; }
        else                  { active[2] = active[3] = true; vpp[2] = vpp[3] = p.vertsPerPrimActive; }
    } else {
        active[0] = true; vpp[0] = p.vertsPerPrimActive;
        active[1] = true; vpp[1] = p.vertsPerPrimAlt;
    }

    uint acc = gid;
    for (uint i = 0; i < p.spinIters; ++i) acc = acc * 1664525u + 1013904223u;

    for (uint s = 0; s < 4; ++s) {
        if (!active[s]) continue;
        atomic_fetch_add_explicit(&ctrGenerated[s], 1u, memory_order_relaxed);
        uint n = vpp[s];
        if (n == 0u) continue;
        uint slot = atomic_fetch_add_explicit(&ctrReserved[s], n, memory_order_relaxed);
        if (slot + n > cap[s]) continue;      // whole primitive dropped -- no partial write
        for (uint v = 0; v < n; ++v) {
            // .w carries the spin-loop accumulator (not `v`): nothing
            // downstream reads xfb_capture's own .z/.w fields for
            // correctness (only .x is staleness-checked, by the replay
            // draw's v_verify and by the raw no-partial-primitive boundary
            // scan, both word-0-only) -- this keeps the spin loop's result
            // genuinely live (undroppable by the optimizer) without
            // affecting any verified field.
            uint4 rec = uint4(p.magicBase + gid * 16u + v, gid, s, acc);
            uint byteAddr = offset[s] + (slot + v) * stride[s];
            device uchar *dst = bufs[s] + byteAddr;
            thread uchar *src = (thread uchar *)&rec;
            for (uint b = 0; b < 16; ++b) dst[b] = src[b];
        }
        atomic_fetch_add_explicit(&ctrWritten[s], n, memory_order_relaxed);
    }
}

struct DrawArgs { uint vertexCount; uint instanceCount; uint vertexStart; uint baseInstance; };

kernel void xfb_finalize(device atomic_uint *ctrWritten [[buffer(0)]],   // [4]
                          device DrawArgs *argsOut [[buffer(1)]],
                          constant uint &replayStream [[buffer(2)]],
                          uint gid [[thread_position_in_grid]]) {
    if (gid == 0) {
        uint w = atomic_load_explicit(&ctrWritten[replayStream], memory_order_relaxed);
        argsOut->vertexCount = w;
        argsOut->instanceCount = 1u;
        argsOut->vertexStart = 0u;
        argsOut->baseInstance = 0u;
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
