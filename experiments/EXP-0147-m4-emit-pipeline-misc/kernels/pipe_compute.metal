// EXP-0147 compute-stage carriers -- OWN-SHADER MSL authored for this
// experiment. CLEAN-ROOM: public newLibraryWithSource: on our own source; no
// Apple binary is introspected.
#include <metal_stdlib>
using namespace metal;

// K-MAD: the matrix_mac (0xcf) carrier. One simdgroup_multiply_accumulate over
// one 32-lane simdgroup = exactly one 0xcf, with A, B and C supplied as runtime
// buffers so the host can compute an exact float32 oracle (A*B + C).
kernel void k_mad_f32(device float *out [[buffer(0)]],
                      const device float *a [[buffer(1)]],
                      const device float *b [[buffer(2)]],
                      const device float *c [[buffer(3)]],
                      uint tid [[thread_position_in_threadgroup]]) {
    simdgroup_float8x8 A, B, C;
    simdgroup_load(A, a, 8);
    simdgroup_load(B, b, 8);
    simdgroup_load(C, c, 8);
    simdgroup_multiply_accumulate(C, A, B, C);
    simdgroup_store(C, out, 8);
}

// K-ATOMIC: the scoreboard_fence carrier. The device atomic RMW plus the
// device+texture memory fence makes the compiler emit the 4-byte pre-atomic
// register/scoreboard fence `07 22 02 00`. The output depends on the atomic's
// return value AND on the input buffer, so a broken ordering or a corrupted
// operand is visible in the read-back.
kernel void k_atomic(device float *out [[buffer(0)]],
                     const device float *a [[buffer(1)]],
                     device atomic_uint *ac [[buffer(2)]],
                     uint tid [[thread_position_in_grid]]) {
    uint v = atomic_fetch_add_explicit(ac, 1u, memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_device | mem_flags::mem_texture);
    // The per-thread value of v depends on arrival order, but over a 32-thread
    // dispatch the SET of returned tickets is exactly {0..31}, so the host
    // oracle is the order-independent multiset of (out[tid] - 2*a[tid]).
    out[tid] = a[tid] * 2.0 + float(v & 7u);
}

// K-TGRW: the compute_fence_scoped carrier. A threadgroup-memory store, a
// threadgroup barrier and a NEIGHBOUR load compile to the 4-byte 0x87
// high-scope fence `87 00 80 04`. The neighbour read is a genuine cross-lane
// RAW hazard, so if the fence/barrier stopped ordering the store against the
// load the read-back would show stale values; the exact host oracle is
// out[gid] = in[(lid+1) % tgsz] + in[gid].
kernel void k_tgrw(device float *out [[buffer(0)]],
                   const device float *in [[buffer(1)]],
                   uint gid [[thread_position_in_grid]],
                   uint lid [[thread_position_in_threadgroup]],
                   uint tgsz [[threads_per_threadgroup]]) {
    threadgroup float scratch[256];
    scratch[lid] = in[gid];
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint nb = (lid + 1u) % tgsz;
    out[gid] = scratch[nb] + scratch[lid];
}
