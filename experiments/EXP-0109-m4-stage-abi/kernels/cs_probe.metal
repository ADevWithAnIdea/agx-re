// cs_probe.metal — EXP-0109 CS ABI probe kernels (OWN-SHADER).
// Covers: dynamic threadgroup-memory addressing (harness/compute_probe.m,
// HW-PROBE), and two structural differential-compile probes run through the
// unmodified tools/shdump/shdump.m (compute mode): whether a compute kernel
// with a bound `constant` buffer argument gets a separate
// `_agc.main.constant_program` preamble section (it always does per EXP-0020;
// this re-confirms the *shape* holds on M4 and checks the "no buffer bound"
// case for comparison), and a `noinline` function-call kernel for the
// CALL/RETURN ABI cross-check against EXP-0035 (A18).

#include <metal_stdlib>
using namespace metal;

// ---- dynamic threadgroup memory addressing ----------------------------------
// The SAME compiled kernel is dispatched (harness/compute_probe.m) with
// different `setThreadgroupMemoryLength:atIndex:0` values and correspondingly
// different threadsPerThreadgroup — the modulus is the RUNTIME
// threads_per_threadgroup builtin, never a compile-time constant, so a
// correct wraparound result at every tested size is only possible if the
// [[threadgroup(0)]] region's base is a fixed/compiled address and its
// CAPACITY is a genuine dispatch-time parameter with no compiled dependency.
kernel void cs_tgmem_probe(threadgroup float *buf [[threadgroup(0)]],
                            device float *out [[buffer(0)]],
                            uint lid [[thread_index_in_threadgroup]],
                            uint3 gid [[thread_position_in_grid]],
                            uint3 tg [[threads_per_threadgroup]]) {
    buf[lid] = float(lid) * 10.0f + 1.0f;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint nxt = (lid + 1u) % tg.x;
    out[gid.x] = buf[nxt];
}

// ---- preamble / constant-program structural probes --------------------------
struct Params { float a; float b; uint n; };

// Uses a bound `constant` argument -> expect thread-invariant work (buffer
// base + scalar loads) to live in the constant/uniform preamble (EXP-0020).
kernel void cs_with_constant(constant Params &p [[buffer(0)]],
                              device float *out [[buffer(1)]],
                              uint gid [[thread_position_in_grid]]) {
    out[gid] = float(gid) * p.a + p.b + float(p.n);
}

// No bound arguments at all beyond the output buffer and a thread ID -> the
// comparison case (still expects a preamble section per EXP-0020's model:
// the buffer base pointer itself is thread-invariant uniform state).
kernel void cs_no_constant(device float *out [[buffer(0)]],
                            uint gid [[thread_position_in_grid]]) {
    out[gid] = float(gid) * 2.0f;
}

// ---- CALL/RETURN ABI cross-check (vs. EXP-0035, A18) ------------------------
static float __attribute__((noinline)) callee_fn(float x, float y) {
    return x * y + 1.0f;
}
kernel void cs_call_probe(device float *out [[buffer(0)]],
                            uint gid [[thread_position_in_grid]]) {
    float a = float(gid);
    float b = a + 3.0f;
    out[gid] = callee_fn(a, b) + callee_fn(b, a);
}
