// EXP-0205 REVISION B -- kernels/k_litmus.metal.  AUTHORED BY US (OWN-SHADER).
//
// WHY THIS FILE EXISTS.  `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` section 5,
// Phase 3: "for synchronization, use a real multi-invocation ordering litmus.
// Scalar success cannot assign ordering semantics."  A `cache` field plausibly
// controls memory/coherency behaviour, and revision A's carriers are all ONE
// threadgroup, ONE simdgroup, ONE pass -- they physically cannot express that.
// Zero movement there is `carrier-undecidable` for the ordering dimension, not
// inertness (Gate B).
//
// WHAT THESE CARRIERS ADD, dimension by dimension:
//
//   MULTI-INVOCATION     grid 256 / tg 64 -> 4 threadgroups x 2 simdgroups each,
//                        instead of revision A's single 32-lane simdgroup.
//   CROSS-LANE VISIBILITY the subgroup result goes through THREADGROUP MEMORY
//                        and comes back from a lane in the OTHER simdgroup
//                        (lid XOR-ing across the 32-lane boundary), so a value
//                        that never left its own simdgroup is distinguishable.
//   CROSS-THREADGROUP    a device atomic on buffer(2) that every one of the 256
//                        invocations contributes to; the total is read back, so
//                        "all four threadgroups actually ran and their writes
//                        became visible" is a MEASUREMENT, not an assumption.
//   REPEATED READS       the source codeword is read AGAIN after two barriers
//                        and the atomic -- the point at which a "retain in
//                        register cache" / "future reads undefined" hint would
//                        have to bite if it is one.
//   PROVENANCE           each litmus comes in two variants whose only difference
//                        is HOW the operand was produced: `_ld` seeds it with a
//                        device load, `_alu` computes it from the thread id with
//                        ALU only.  Revision A found `simd_shuffle.cache` LIVE
//                        on a device-load-seeded source, and EXP-0129 found the
//                        same provenance split on a different field, so this is
//                        a named dimension and not a guess.
//
// UNIQUE PER-LANE CODEWORDS (corrections section 5, Phase 3).  Every invocation
// is seeded with a codeword unique across all 256 threads, so lane, width,
// swizzle, sign, register and immediate interpretations of a result cannot
// alias each other: any observed vector names exactly which invocation produced
// each word.
//
// WORD PLAN -- deliberately THREE DISJOINT READBACK PLANS (corrections section
// 6: "at least two disjoint register/readback plans so a hidden write or
// destination alias cannot masquerade as inertness"):
//   out[0..255]    plan 1: the subgroup instruction's own result, per thread
//   out[256..511]  plan 2: that result after a threadgroup-memory round trip
//                          read back from the OTHER simdgroup
//   out[512..767]  plan 3: the SOURCE codeword re-read after both barriers
//   out[768..999]  never written: must stay poison
//   out[1000]      PRE sentinel  = 12345, stored first
//   out[1001]      POST sentinel = 54321, stored last
//   out[1002..1023] never written: must stay poison
//   buffer(2)[0]   device atomic total across all 4 threadgroups

#include <metal_stdlib>
using namespace metal;

constant uint PRE_SENT  = 1000u;
constant uint POST_SENT = 1001u;
constant uint PRE_VAL   = 12345u;
constant uint POST_VAL  = 54321u;
constant uint SHUF_LANE = 5u;
constant uint TG        = 64u;

// The ALU/system-value producer for the `_alu` variants: unique per thread and
// computed with no memory traffic at all, so operand provenance is the ONLY
// thing that differs from the `_ld` variant.
static inline uint alu_codeword(uint tid)
{
    return (0x51C0DE00u + tid * 0x00010001u) ^ (tid << 20);
}

// ---------------------------------------------------------------- ballot, ld
kernel void k_lb_ballot_ld(device uint *out          [[buffer(0)]],
                           const device uint *in     [[buffer(1)]],
                           device atomic_uint *ctr   [[buffer(2)]],
                           uint tid  [[thread_position_in_grid]],
                           uint lid  [[thread_position_in_threadgroup]])
{
    threadgroup uint tgm[TG];
    out[PRE_SENT] = PRE_VAL;
    uint cw = in[tid];
    bool p = ((cw >> 3) & 1u) != 0u;
    uint r = uint((simd_vote::vote_t)simd_ballot(p));
    out[tid] = r;
    tgm[lid] = r ^ cw;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    out[256u + tid] = tgm[(lid + 32u) & (TG - 1u)];
    atomic_fetch_add_explicit(ctr, (r & 0xFFu) + 1u, memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup | mem_flags::mem_device);
    out[512u + tid] = cw;
    out[POST_SENT] = POST_VAL;
}

// --------------------------------------------------------------- ballot, alu
kernel void k_lb_ballot_alu(device uint *out          [[buffer(0)]],
                            const device uint *in     [[buffer(1)]],
                            device atomic_uint *ctr   [[buffer(2)]],
                            uint tid  [[thread_position_in_grid]],
                            uint lid  [[thread_position_in_threadgroup]])
{
    threadgroup uint tgm[TG];
    out[PRE_SENT] = PRE_VAL;
    uint cw = alu_codeword(tid);
    bool p = ((cw >> 3) & 1u) != 0u;
    uint r = uint((simd_vote::vote_t)simd_ballot(p));
    out[tid] = r;
    tgm[lid] = r ^ cw;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    out[256u + tid] = tgm[(lid + 32u) & (TG - 1u)];
    atomic_fetch_add_explicit(ctr, (r & 0xFFu) + 1u, memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup | mem_flags::mem_device);
    out[512u + tid] = cw;
    out[POST_SENT] = POST_VAL;
}

// --------------------------------------------------------------- shuffle, ld
kernel void k_lb_shuffle_ld(device uint *out          [[buffer(0)]],
                            const device uint *in     [[buffer(1)]],
                            device atomic_uint *ctr   [[buffer(2)]],
                            uint tid  [[thread_position_in_grid]],
                            uint lid  [[thread_position_in_threadgroup]])
{
    threadgroup uint tgm[TG];
    out[PRE_SENT] = PRE_VAL;
    uint cw = in[tid];
    uint r = simd_broadcast(cw, SHUF_LANE);
    out[tid] = r;
    tgm[lid] = r ^ cw;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    out[256u + tid] = tgm[(lid + 32u) & (TG - 1u)];
    atomic_fetch_add_explicit(ctr, (r & 0xFFu) + 1u, memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup | mem_flags::mem_device);
    out[512u + tid] = cw;
    out[POST_SENT] = POST_VAL;
}

// -------------------------------------------------------------- shuffle, alu
kernel void k_lb_shuffle_alu(device uint *out          [[buffer(0)]],
                             const device uint *in     [[buffer(1)]],
                             device atomic_uint *ctr   [[buffer(2)]],
                             uint tid  [[thread_position_in_grid]],
                             uint lid  [[thread_position_in_threadgroup]])
{
    threadgroup uint tgm[TG];
    out[PRE_SENT] = PRE_VAL;
    uint cw = alu_codeword(tid);
    uint r = simd_broadcast(cw, SHUF_LANE);
    out[tid] = r;
    tgm[lid] = r ^ cw;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    out[256u + tid] = tgm[(lid + 32u) & (TG - 1u)];
    atomic_fetch_add_explicit(ctr, (r & 0xFFu) + 1u, memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup | mem_flags::mem_device);
    out[512u + tid] = cw;
    out[POST_SENT] = POST_VAL;
}
