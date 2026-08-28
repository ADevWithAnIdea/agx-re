// EXP-0098 Bundle H -- "h_sync" / "h_fields" families. Authored MSL only
// (OWN-SHADER). A compute kernel writes the vertex records, index records
// (indexed variant), and the MTLDraw[Indexed]PrimitivesIndirectArguments
// record that a following render draw consumes -- never CPU `contents`
// writes for the record bytes themselves.
//
// v_verify / f_noop are the verification pipeline: the vertex stage's ONLY
// job is to record, via a device-buffer side effect, exactly which
// [[vertex_id]] it was invoked with and what raw uint4 it read from buffer(0)
// at the moment of execution. This decouples verification from rasterization
// entirely (no color-attachment readback needed) and doubles as the
// synchronization detector: a stale (pre-write sentinel) read means the
// render vertex stage observed data older than the producing compute
// dispatch's writes, despite program-order submission.

#include <metal_stdlib>
using namespace metal;

struct DrawArgs {                 // matches MTLDrawPrimitivesIndirectArguments
    uint vertexCount;
    uint instanceCount;
    uint vertexStart;
    uint baseInstance;
};

struct DrawIndexedArgs {          // matches MTLDrawIndexedPrimitivesIndirectArguments
    uint indexCount;
    uint instanceCount;
    uint indexStart;
    int  baseVertex;
    uint baseInstance;
};

struct ChainParams {
    uint n;             // number of vertex records to write == grid size
    uint magicBase;
    uint vertexCount;
    uint instanceCount;
    uint vertexStart;
    uint baseInstance;
    uint spinIters;     // artificial per-thread work to lengthen the producer
                         // dispatch's real GPU execution time (race-window
                         // calibration); folded into vtxOut.w so the compiler
                         // cannot dead-code-eliminate the loop. Does not affect
                         // the .x correctness check.
};

// Non-indexed producer. buffer(0)=vtxOut (uint4/elem), buffer(1)=argsOut,
// buffer(2)=params.
kernel void producer_chain(device uint4 *vtxOut [[buffer(0)]],
                            device DrawArgs *argsOut [[buffer(1)]],
                            constant ChainParams &p [[buffer(2)]],
                            uint gid [[thread_position_in_grid]]) {
    if (gid < p.n) {
        uint acc = gid;
        for (uint i = 0; i < p.spinIters; ++i) acc = acc * 1664525u + 1013904223u;
        vtxOut[gid] = uint4(p.magicBase + gid, gid, 0xA5A5A5A5u, acc);
    }
    if (gid == 0) {
        argsOut->vertexCount = p.vertexCount;
        argsOut->instanceCount = p.instanceCount;
        argsOut->vertexStart = p.vertexStart;
        argsOut->baseInstance = p.baseInstance;
    }
}

struct ChainParamsIndexed {
    uint n;             // number of index/vertex records to write == grid size
    uint magicBase;
    uint idxBase;        // value added to each written index (supports the
                          // negative-baseVertex-safe test: indices start >0)
    uint indexCount;
    uint instanceCount;
    uint indexStart;
    int  baseVertex;
    uint baseInstance;
    uint restartAt;      // position (< n) to overwrite with the restart
                          // sentinel instead of a normal index; 0xFFFFFFFF = none
    uint spinIters;      // see ChainParams.spinIters
};

// Indexed producer, 32-bit index buffer. buffer(0)=vtxOut, buffer(1)=idxOut
// (uint32/elem), buffer(2)=argsOut, buffer(3)=params.
kernel void producer_chain_indexed32(device uint4 *vtxOut [[buffer(0)]],
                                      device uint *idxOut [[buffer(1)]],
                                      device DrawIndexedArgs *argsOut [[buffer(2)]],
                                      constant ChainParamsIndexed &p [[buffer(3)]],
                                      uint gid [[thread_position_in_grid]]) {
    if (gid < p.n) {
        uint acc = gid;
        for (uint i = 0; i < p.spinIters; ++i) acc = acc * 1664525u + 1013904223u;
        vtxOut[gid] = uint4(p.magicBase + gid, gid, 0xA5A5A5A5u, acc);
        idxOut[gid] = (gid == p.restartAt) ? 0xFFFFFFFFu : (p.idxBase + gid);
    }
    if (gid == 0) {
        argsOut->indexCount = p.indexCount;
        argsOut->instanceCount = p.instanceCount;
        argsOut->indexStart = p.indexStart;
        argsOut->baseVertex = p.baseVertex;
        argsOut->baseInstance = p.baseInstance;
    }
}

// Indexed producer, 16-bit index buffer. buffer(1)=idxOut (ushort/elem).
kernel void producer_chain_indexed16(device uint4 *vtxOut [[buffer(0)]],
                                      device ushort *idxOut [[buffer(1)]],
                                      device DrawIndexedArgs *argsOut [[buffer(2)]],
                                      constant ChainParamsIndexed &p [[buffer(3)]],
                                      uint gid [[thread_position_in_grid]]) {
    if (gid < p.n) {
        vtxOut[gid] = uint4(p.magicBase + gid, gid, 0xA5A5A5A5u, 0u);
        idxOut[gid] = (gid == p.restartAt) ? (ushort)0xFFFFu : (ushort)(p.idxBase + gid);
    }
    if (gid == 0) {
        argsOut->indexCount = p.indexCount;
        argsOut->instanceCount = p.instanceCount;
        argsOut->indexStart = p.indexStart;
        argsOut->baseVertex = p.baseVertex;
        argsOut->baseInstance = p.baseInstance;
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
