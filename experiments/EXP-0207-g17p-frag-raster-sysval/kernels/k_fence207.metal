// k_fence207.metal -- EXP-0207 carriers for dev_scoreboard_fence.scope_flag.
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// EXP-0141 could not promote this field for a stated and correct reason: no
// own-MSL kernel it could compile emitted `80 02 00 xx`, so the instruction had
// to be SYNTHESISED into a load/ALU/store program that "has no scoreboard/
// ordering observable".  Every value was accepted without fault -- which says
// nothing about the field, because nothing in that program could have noticed.
//
// So the thing to build is not another sweep: it is an ORDERING-SENSITIVE
// OBSERVABLE that the compiler itself decorates with the fence.  The db entry
// says the compiler inserts this op around divergent control flow and before
// atomics and calls; each kernel below combines divergence with device atomics
// and a device-scope barrier, and produces a result that is DETERMINISTIC when
// the ordering holds and wrong when it does not.
//
// The arm's detection power is measured, not assumed: neutralising the fence
// itself must change the observable.  If it does not, the carrier has no
// ordering sensitivity, and this field is reported STILL-UNDERPOWERED with that
// null control as the measured proof -- not as inertness.

#include <metal_stdlib>
using namespace metal;

constant uint SENT_BASE = 0x5A5A0000u;

// k_fence_at: divergent atomics then a device-scope barrier then a read of both
// counters.  With grid 64 / threadgroup 64 the post-barrier values are exactly
// (32, 64) for every lane, so the correct answer is a single host-computable
// constant and any lost ordering shows as a different, smaller number.
kernel void k_fence_at(device uint *out [[buffer(0)]],
                       device atomic_uint *at [[buffer(1)]],
                       device uint *sent [[buffer(4)]],
                       uint tid [[thread_position_in_grid]],
                       uint lane [[thread_index_in_simdgroup]])
{
    sent[tid] = SENT_BASE + tid;
    if ((lane & 1u) == 0u) {
        atomic_fetch_add_explicit(&at[0], 1u, memory_order_relaxed);
    } else {
        atomic_fetch_add_explicit(&at[1], 2u, memory_order_relaxed);
    }
    threadgroup_barrier(mem_flags::mem_device);
    uint a0 = atomic_load_explicit(&at[0], memory_order_relaxed);
    uint a1 = atomic_load_explicit(&at[1], memory_order_relaxed);
    out[tid] = a0 * 1000u + a1;
}

// k_fence_rel: a release/acquire handoff.  Lane 0 publishes a payload and then
// releases a flag; every other lane acquires the flag and reads the payload back.
// The correct answer is again a host-computable constant; a broken release makes
// the readers see the pre-publication value.
kernel void k_fence_rel(device uint *out [[buffer(0)]],
                        device atomic_uint *flag [[buffer(1)]],
                        device uint *payload [[buffer(2)]],
                        device uint *sent [[buffer(4)]],
                        uint tid [[thread_position_in_grid]],
                        uint lane [[thread_index_in_simdgroup]])
{
    sent[tid] = SENT_BASE + tid;
    if (lane == 0u) {
        for (uint i = 0; i < 8u; ++i) payload[i] = 0x1234u + i;
        atomic_store_explicit(&flag[0], 1u, memory_order_release);
    }
    threadgroup_barrier(mem_flags::mem_device);
    uint f = atomic_load_explicit(&flag[0], memory_order_acquire);
    uint s = 0u;
    if (f != 0u) { for (uint i = 0; i < 8u; ++i) s += payload[i]; }
    out[tid] = s + f;
}
