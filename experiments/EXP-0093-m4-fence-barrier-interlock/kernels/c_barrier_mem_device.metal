#include <metal_stdlib>
using namespace metal;
kernel void k_main(device float *out [[buffer(0)]],
                    threadgroup float *scratch [[threadgroup(0)]],
                    uint tid [[thread_position_in_threadgroup]]) {
    scratch[tid] = float(tid);
    threadgroup_barrier(mem_flags::mem_device);
    out[tid] = scratch[(tid + 1) % 64];
}
