// EXP-0085 — MEM-13 / MEM-14 interlock probes (authored MSL). Clean-room:
// OWN-SHADER. Every kernel places its consuming/producing instruction with
// zero intervening source statements around the memory/atomic operation, so
// the compiler has no textual room to insert anything between producer and
// consumer other than what the hardware requires.
//
// Fixed harness buffer contract (harness/interlock_probe.m):
//   buffer(0) a     — per-lane (or, for il_chain48, per-lane*48) float input,
//                      always small non-negative INTEGER-valued floats so
//                      every legal summation order is bit-exact (no float
//                      non-associativity ambiguity in the expected value).
//   buffer(1) b     — per-lane float input, same property.
//   buffer(2) idx   — per-lane uint gather index (il_gather only).
//   buffer(3) atom  — one atomic_uint counter, pre-zeroed by the harness
//                      (il_atomic_alu / il_atomic_src only).
//   buffer(4) out   — per-lane float output, read back and checked exactly.

#include <metal_stdlib>
using namespace metal;

// MEM-13, pattern 1: load -> immediate ALU consumption, zero slack.
kernel void il_load_alu(device float* a [[buffer(0)]],
                         device float* b [[buffer(1)]],
                         device uint* idx [[buffer(2)]],
                         device atomic_uint* atom [[buffer(3)]],
                         device float* out [[buffer(4)]],
                         uint tid [[thread_position_in_grid]]) {
    out[tid] = a[tid] * 2.0f + 1.0f;
}

// MEM-13, pattern 2: dependent (gather) load -> immediate ALU consumption.
kernel void il_gather(device float* a [[buffer(0)]],
                       device float* b [[buffer(1)]],
                       device uint* idx [[buffer(2)]],
                       device atomic_uint* atom [[buffer(3)]],
                       device float* out [[buffer(4)]],
                       uint tid [[thread_position_in_grid]]) {
    out[tid] = a[idx[tid]] * 3.0f + 2.0f;
}

// MEM-13, pattern 3: atomic RMW result -> immediate ALU consumption.
// Invariant: the recovered {old} multiset across all lanes must be exactly
// {0, 1, ..., N-1} -- a permutation, proving each lane's ALU consumed the
// exact value its atomic returned with no staleness or duplication.
kernel void il_atomic_alu(device float* a [[buffer(0)]],
                           device float* b [[buffer(1)]],
                           device uint* idx [[buffer(2)]],
                           device atomic_uint* atom [[buffer(3)]],
                           device float* out [[buffer(4)]],
                           uint tid [[thread_position_in_grid]]) {
    uint old = atomic_fetch_add_explicit(&atom[0], 1u, memory_order_relaxed);
    out[tid] = float(old) * 2.0f + 1.0f;
}

// MEM-14, pattern 1: ALU-computed value -> immediate store, zero slack.
kernel void il_store_src(device float* a [[buffer(0)]],
                          device float* b [[buffer(1)]],
                          device uint* idx [[buffer(2)]],
                          device atomic_uint* atom [[buffer(3)]],
                          device float* out [[buffer(4)]],
                          uint tid [[thread_position_in_grid]]) {
    out[tid] = a[tid] * b[tid] - a[tid];
}

// MEM-14, pattern 2: ALU-computed operand -> immediate atomic RMW.
// Invariant: final atom[0] == sum over all lanes of (a[i]+b[i]) exactly
// (commutative/associative over exact small integers => order-independent).
kernel void il_atomic_src(device float* a [[buffer(0)]],
                           device float* b [[buffer(1)]],
                           device uint* idx [[buffer(2)]],
                           device atomic_uint* atom [[buffer(3)]],
                           device float* out [[buffer(4)]],
                           uint tid [[thread_position_in_grid]]) {
    uint addend = uint(a[tid] + b[tid]);
    uint old = atomic_fetch_add_explicit(&atom[0], addend, memory_order_relaxed);
    out[tid] = float(old);
}

// MEM-13 adversarial/boundary pattern: 48 independent per-lane loads (high
// register pressure -- deliberately above the 32-wide comfortable window
// EXP-0025 exercised at 20) reduced and consumed with no explicit wait
// anywhere in source. buffer(0) holds N*48 elements, a[tid*48 + k].
// Falsifier: any dispatch (run at high N / high occupancy, see
// PRE_REGISTRATION.md) whose sum is not the exact expected value is a
// constructed interlock violation.
kernel void il_chain48(device float* a [[buffer(0)]],
                        device float* b [[buffer(1)]],
                        device uint* idx [[buffer(2)]],
                        device atomic_uint* atom [[buffer(3)]],
                        device float* out [[buffer(4)]],
                        uint tid [[thread_position_in_grid]]) {
    device float* p = a + (ulong)tid * 48u;
    float s = 0.0f;
    for (uint k = 0; k < 48u; k++) s += p[k];
    out[tid] = s;
}
