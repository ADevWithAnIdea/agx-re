// simd_misc.metal -- EXP-0104 authored MSL: SIMD-* cluster probes (width, ballot,
// shuffle index range, prefix-scan under divergence, quad xor mapping,
// simdgroup_barrier). Own-authored MSL only (OWN-SHADER). No Apple binary read.
#include <metal_stdlib>
using namespace metal;

// ---------------------------------------------------------------------------
// SIMD-01: subgroup width report at every lane, incl. a PARTIAL final
// simdgroup (threadgroup size not a multiple of 32).
kernel void width_report(device int* lane_id [[buffer(0)]],
                          device int* tps [[buffer(1)]],
                          device int* sgid [[buffer(2)]],
                          device int* tiig [[buffer(3)]],
                          uint i [[thread_position_in_grid]],
                          uint lid [[thread_index_in_simdgroup]],
                          uint tw [[threads_per_simdgroup]],
                          uint sg [[simdgroup_index_in_threadgroup]],
                          uint tiig_ [[thread_index_in_threadgroup]]) {
    lane_id[i] = (int)lid;
    tps[i] = (int)tw;
    sgid[i] = (int)sg;
    tiig[i] = (int)tiig_;
}

// ---------------------------------------------------------------------------
// SIMD-02: ballot bit-to-lane mapping under GENUINE divergence derived from
// thread_position_in_grid (predicate = a data-dependent per-lane condition,
// not a uniform compile-time constant).
kernel void ballot_map(device int* lo [[buffer(0)]],
                        device const int* mode [[buffer(1)]],
                        uint i [[thread_position_in_grid]],
                        uint lid [[thread_index_in_simdgroup]]) {
    int m = mode[0];
    bool pred;
    if (m == 0) { pred = (i % 3 == 0); }
    else if (m == 1) { pred = (i % 7 < 2); }
    else { pred = (i >= 5 && i < 19); }
    simd_vote v = simd_ballot(pred);
    uint64_t mask = (uint64_t)v;
    lo[i] = (int)(mask & 0xffffffffu);
}

// ---------------------------------------------------------------------------
// SIMD-03: dynamic (runtime, per-lane) shuffle index sweep -- the index comes
// from a buffer so the compiler cannot constant-fold or reject it at compile
// time; the hardware alone decides out-of-[0,32) behavior.
kernel void shuffle_dyn(device int* out [[buffer(0)]],
                         device const int* idxbuf [[buffer(1)]],
                         uint i [[thread_position_in_grid]]) {
    int v = (int)i;  // data = own lane id
    ushort idx = (ushort)idxbuf[i];
    out[i] = simd_shuffle(v, idx);
}

kernel void shuffle_xor_dyn(device int* out [[buffer(0)]],
                             device const int* maskbuf [[buffer(1)]],
                             uint i [[thread_position_in_grid]]) {
    int v = (int)i;
    ushort m = (ushort)maskbuf[i];
    out[i] = simd_shuffle_xor(v, m);
}

kernel void quad_shuffle_dyn(device int* out [[buffer(0)]],
                              device const int* idxbuf [[buffer(1)]],
                              uint i [[thread_position_in_grid]]) {
    int v = (int)i;
    ushort idx = (ushort)idxbuf[i];
    out[i] = quad_shuffle(v, idx);
}

// ---------------------------------------------------------------------------
// SIMD-04: inclusive/exclusive prefix-scan and reduce with a subset of lanes
// masked OFF by real per-lane divergence (parity of thread_position_in_grid).
kernel void scan_divergent(device int* excl [[buffer(0)]],
                            device int* incl [[buffer(1)]],
                            device int* red [[buffer(2)]],
                            uint i [[thread_position_in_grid]]) {
    if (i % 2 == 0) {
        excl[i] = (int)simd_prefix_exclusive_sum(1);
        incl[i] = (int)simd_prefix_inclusive_sum(1);
        red[i] = (int)simd_sum(1);
    } else {
        excl[i] = -1;
        incl[i] = -1;
        red[i] = -1;
    }
}

// ---------------------------------------------------------------------------
// SIMD-05 (compute half -- linear lane-numbering / xor-mask semantics; the
// 2D horizontal/vertical/diagonal geometric mapping is tested separately in
// a fragment kernel, frag_misc.metal).
kernel void quad_xor_map(device int* xor1 [[buffer(0)]],
                          device int* xor2 [[buffer(1)]],
                          device int* xor3 [[buffer(2)]],
                          device int* up1 [[buffer(3)]],
                          device int* down1 [[buffer(4)]],
                          uint i [[thread_position_in_grid]]) {
    int v = (int)i;
    xor1[i] = quad_shuffle_xor(v, 1);
    xor2[i] = quad_shuffle_xor(v, 2);
    xor3[i] = quad_shuffle_xor(v, 3);
    up1[i]  = quad_shuffle_up(v, 1);
    down1[i]= quad_shuffle_down(v, 1);
}

// ---------------------------------------------------------------------------
// SIMD-06: simdgroup_barrier structural / convergence probes.
kernel void sgbar_none(device int* o [[buffer(0)]],
                        device const int* a [[buffer(1)]],
                        uint i [[thread_position_in_grid]]) {
    o[i] = a[i] * 2;
}
kernel void sgbar_memnone(device int* o [[buffer(0)]],
                           device const int* a [[buffer(1)]],
                           uint i [[thread_position_in_grid]]) {
    int v = a[i] * 2;
    simdgroup_barrier(mem_flags::mem_none);
    o[i] = v;
}
kernel void sgbar_memtg(device int* o [[buffer(0)]],
                         device const int* a [[buffer(1)]],
                         uint i [[thread_position_in_grid]]) {
    int v = a[i] * 2;
    simdgroup_barrier(mem_flags::mem_threadgroup);
    o[i] = v;
}
kernel void sgbar_memdev(device int* o [[buffer(0)]],
                          device const int* a [[buffer(1)]],
                          uint i [[thread_position_in_grid]]) {
    int v = a[i] * 2;
    simdgroup_barrier(mem_flags::mem_device);
    o[i] = v;
}

// simdgroup_barrier CONVERGENCE correctness: per-lane variable-length delay
// (derived from thread_position_in_grid, genuinely divergent), a
// simdgroup_barrier, then a cross-lane read of another lane's DEVICE-memory
// scratch slot (device buffer used instead of [[threadgroup(0)]] because the
// read-only agxrun.m testbed does not expose
// setThreadgroupMemoryLength: -- see PRE_REGISTRATION Note-A; this mirrors
// EXP-0093's own tgdiv_dev device-memory convergence design). scratch[] is
// pre-filled with a sentinel by the host so a stale/unconverged read is
// unambiguous. Mirrors EXP-0093's tgdiv2 but scoped to ONE simdgroup
// (tg == simd width == 32) using simdgroup_barrier instead of
// threadgroup_barrier.
kernel void sgbar_conv(device int* o [[buffer(0)]],
                        device int* scratch [[buffer(1)]],
                        uint i [[thread_position_in_grid]],
                        uint lid [[thread_index_in_threadgroup]]) {
    int delay = (int)(lid + 1) * 37;
    int acc = 0;
    for (int k = 0; k < delay; k++) { acc += 1; }
    scratch[lid] = acc + (int)lid;
    simdgroup_barrier(mem_flags::mem_device);
    uint partner = 31u - lid;
    o[i] = scratch[partner];
}

kernel void sgbar_conv_none(device int* o [[buffer(0)]],
                             device int* scratch [[buffer(1)]],
                             uint i [[thread_position_in_grid]],
                             uint lid [[thread_index_in_threadgroup]]) {
    int delay = (int)(lid + 1) * 37;
    int acc = 0;
    for (int k = 0; k < delay; k++) { acc += 1; }
    scratch[lid] = acc + (int)lid;
    // no barrier at all -- expected race control
    uint partner = 31u - lid;
    o[i] = scratch[partner];
}
