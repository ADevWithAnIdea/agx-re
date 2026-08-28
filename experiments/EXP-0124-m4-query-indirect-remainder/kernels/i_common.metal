// EXP-0124 Group I (P1.7 indirect CDM / writable ICB grammar / barriers / restart)
// kernels. Authored MSL, our own source, compiled via the public newLibraryWithSource:
// runtime path. Apple binary introspection: NONE.

#include <metal_stdlib>
#include <metal_command_buffer>
using namespace metal;

// ---------------------------------------------------------------------------
// i_cdmfmt: indirect-dispatch parameter-memory format. Marker kernel that records
// its own dispatch/grid position, used to prove byte layout and invocation counts.
kernel void i_cdm_writer(device atomic_uint *counter [[buffer(0)]],
                          device uint3 *lastPos [[buffer(1)]],
                          uint3 gid [[thread_position_in_grid]])
{
    atomic_fetch_add_explicit(counter, 1, memory_order_relaxed);
    lastPos[0] = gid;   // racy last-writer-wins marker; only used for small, bounded grids
}

// Kernel that writes a MTLDispatchThreadgroupsIndirectArguments-shaped record
// (3x uint32 threadgroupsPerGrid) with caller-supplied X,Y,Z -- proves the
// public struct's byte order empirically rather than trusting the header alone.
kernel void i_cdm_argwriter(device uint3 *args [[buffer(0)]],
                             constant uint3 &xyz [[buffer(1)]])
{
    args[0] = xyz;
}

// ---------------------------------------------------------------------------
// i_icbwrite: GPU-authored (compute-kernel-encoded) indirect render/compute commands.
struct ICBContainer { command_buffer icb; };

// Render command grammar: N threads each encode one draw_primitives command into
// its own ICB slot, with a per-command color read from `colors[idx]` (a distinct
// 16-byte slice per command -- exercises computed, non-compile-time-constant
// set_vertex_buffer offsets/binds).
kernel void icbw_encode_basic(constant ICBContainer &c [[buffer(0)]],
                               device const float4 *colors [[buffer(1)]],
                               uint idx [[thread_position_in_grid]])
{
    render_command cmd(c.icb, idx);
    cmd.set_vertex_buffer(colors + idx, 1);
    cmd.draw_primitives(primitive_type::triangle, 0, 3, 1, 0);
}

// Encodes one command normally, then resets a caller-specified index (may be the
// same command or a different one) -- proves reset() semantics for a GPU-authored
// record.
kernel void icbw_encode_then_reset(constant ICBContainer &c [[buffer(0)]],
                                    device const float4 *colors [[buffer(1)]],
                                    constant uint &resetIdx [[buffer(2)]],
                                    uint idx [[thread_position_in_grid]])
{
    render_command cmd(c.icb, idx);
    cmd.set_vertex_buffer(colors + idx, 1);
    cmd.draw_primitives(primitive_type::triangle, 0, 3, 1, 0);
    if (idx == resetIdx) {
        render_command rc(c.icb, resetIdx);
        rc.reset();
    }
}

// Field-legality sweep: vertexStart/vertexCount/instanceCount/baseInstance are all
// read from a caller-supplied uint4 record per command (encode-time computed args,
// distinct code path from EXP-0098's CPU-issued-indirect-draw-consumes-compute-
// written-argument-struct pattern).
kernel void icbw_encode_fields(constant ICBContainer &c [[buffer(0)]],
                                device const float4 *colors [[buffer(1)]],
                                device const uint4 *fieldArgs [[buffer(2)]],
                                uint idx [[thread_position_in_grid]])
{
    render_command cmd(c.icb, idx);
    cmd.set_vertex_buffer(colors, 1);
    uint4 a = fieldArgs[idx];
    // a = (vertexStart, vertexCount, instanceCount, baseInstance)
    cmd.draw_primitives(primitive_type::triangle, a.x, a.y, a.z, a.w);
}

// inheritBuffers=YES path: intentionally never calls set_vertex_buffer; the
// executing render encoder is expected to supply the buffer via ordinary
// setVertexBuffer: before executeCommandsInBuffer:.
kernel void icbw_encode_inherit(constant ICBContainer &c [[buffer(0)]],
                                 uint idx [[thread_position_in_grid]])
{
    render_command cmd(c.icb, idx);
    cmd.draw_primitives(primitive_type::triangle, 0, 3, 1, 0);
}

// Indexed-draw grammar.
kernel void icbw_encode_indexed(constant ICBContainer &c [[buffer(0)]],
                                 device const float4 *colors [[buffer(1)]],
                                 device const uint *indices [[buffer(2)]],
                                 uint idx [[thread_position_in_grid]])
{
    render_command cmd(c.icb, idx);
    cmd.set_vertex_buffer(colors + idx, 1);
    cmd.draw_indexed_primitives(primitive_type::triangle, 3, indices, 1, 0, 0);
}

// Out-of-bounds command-index probe: dispatched with MORE threads than the ICB's
// maxCommandCount, so some threads construct a render_command at an index past the
// end of the buffer.
kernel void icbw_encode_oob(constant ICBContainer &c [[buffer(0)]],
                             device const float4 *colors [[buffer(1)]],
                             uint idx [[thread_position_in_grid]])
{
    render_command cmd(c.icb, idx);
    cmd.set_vertex_buffer(colors, 1);
    cmd.draw_primitives(primitive_type::triangle, 0, 3, 1, 0);
}

// Verification render pipeline for all icbw_* cases: color-passthrough.
struct RVOut { float4 pos [[position]]; float4 color; };
vertex RVOut icbw_vertex(uint vid [[vertex_id]], const device float4 *colors [[buffer(1)]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    // [[vertex_id]] is ABSOLUTE (vertexStart-inclusive, matching EXP-0098's
    // established [[instance_id]] finding) -- index modulo 3 so a nonzero
    // vertexStart still selects a valid fullscreen-triangle corner instead of
    // reading past this 3-element local array.
    RVOut o; o.pos = float4(p[vid % 3], 0, 1); o.color = colors[0];
    return o;
}
fragment float4 icbw_fragment(RVOut in [[stage_in]]) { return in.color; }

// ---------------------------------------------------------------------------
// i_icbbarrier: concurrent-dispatch ICB producer/consumer with an optional
// GPU-authored `.set_barrier()` on the consumer command.
// Pipeline state is GPU-authored too (via compute_pipeline_state fields in the
// argument-buffer struct + .set_compute_pipeline_state() in-kernel), NOT mixed
// with a CPU-side -[MTLIndirectComputeCommand setComputePipelineState:] call --
// build-time calibration found that mixing GPU-authored buffer/dispatch fields
// with a CPU-authored pipeline-state field on the SAME command crashed the
// process uncatchably (see PROGRESS.md); an entirely GPU-authored command
// avoids that hazard and is the cleaner "writable command grammar" test anyway.
struct ICBContainerC {
    command_buffer icb;
    compute_pipeline_state prodPSO;
    compute_pipeline_state consPSO;
};

// Fixed, deliberately large sequential-dependency spin (calibrated at build time,
// see PROGRESS.md) so the producer's write to slot[0] is measurably delayed,
// giving a real concurrency window for an unbarriered consumer to race against.
#define ICBB_SPIN_ITERS 4000000u

kernel void icbb_producer(device uint *slot [[buffer(0)]])
{
    uint acc = 12345u;
    for (uint i = 0; i < ICBB_SPIN_ITERS; i++) {
        acc = (acc * 2654435761u) ^ (acc >> 13);
    }
    slot[0] = 42u + (acc & 0u);   // always writes exactly 42; the spin only delays it
}

kernel void icbb_consumer(device const uint *slot [[buffer(0)]],
                           device uint *result [[buffer(1)]])
{
    result[0] = slot[0] * 2u;
}

kernel void icbb_encode(constant ICBContainerC &c [[buffer(0)]],
                         device uint *slot [[buffer(1)]],
                         device uint *result [[buffer(2)]],
                         constant uint &useBarrier [[buffer(3)]],
                         uint idx [[thread_position_in_grid]])
{
    if (idx == 0) {
        compute_command cmd(c.icb, 0);
        cmd.set_compute_pipeline_state(c.prodPSO);
        cmd.set_kernel_buffer(slot, 0);
        cmd.concurrent_dispatch_threadgroups(uint3(1,1,1), uint3(1,1,1));
    } else {
        compute_command cmd(c.icb, 1);
        cmd.set_compute_pipeline_state(c.consPSO);
        if (useBarrier != 0) {
            cmd.set_barrier();
        }
        cmd.set_kernel_buffer(slot, 0);
        cmd.set_kernel_buffer(result, 1);
        cmd.concurrent_dispatch_threadgroups(uint3(1,1,1), uint3(1,1,1));
    }
}

// ---------------------------------------------------------------------------
// i_restart: strip-topology primitive-restart probe (and a point-topology internal
// control reproducing EXP-0098's "sentinel is not special for non-strip topologies"
// finding, from a fresh independent kernel/harness).
struct StripVOut { float4 pos [[position]]; float psize [[point_size]]; float4 color; };

vertex StripVOut v_restart(uint vid [[vertex_id]]) {
    StripVOut o;
    o.psize = 12.0;
    if (vid < 3) {
        // "green" cluster, top-left.
        float2 base = float2(-0.85, -0.85);
        float2 d[3] = { float2(0,0), float2(0.4,0), float2(0,0.4) };
        o.pos = float4(base + d[vid], 0, 1);
        o.color = float4(0,1,0,1);
    } else if (vid < 6) {
        // "blue" cluster, bottom-right.
        float2 base = float2(0.45, 0.45);
        float2 d[3] = { float2(0,0), float2(0.4,0), float2(0,0.4) };
        o.pos = float4(base + d[vid-3], 0, 1);
        o.color = float4(0,0,1,1);
    } else {
        // any larger index (the restart sentinel, if consumed as ordinary data,
        // or any other out-of-cluster index) -- "red" tag, disjoint corner.
        o.pos = float4(0.7, -0.7, 0, 1);
        o.color = float4(1,0,0,1);
    }
    return o;
}
fragment float4 f_restart(StripVOut in [[stage_in]]) { return in.color; }
