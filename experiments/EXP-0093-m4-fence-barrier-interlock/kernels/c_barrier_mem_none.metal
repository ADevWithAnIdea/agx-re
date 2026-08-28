#include <metal_stdlib>
using namespace metal;
// Compute threadgroup_barrier(mem_none) -- own-compile check that the barrier
// instruction is still emitted (execution convergence) even when no memory class
// is fenced (ATOM-09: is convergence coupled to the fence, or a separable op?).
kernel void k_main(device float *out [[buffer(0)]],
                    threadgroup float *scratch [[threadgroup(0)]],
                    uint tid [[thread_position_in_threadgroup]]) {
    scratch[tid] = float(tid);
    threadgroup_barrier(mem_flags::mem_none);
    out[tid] = scratch[(tid + 1) % 64];
}
