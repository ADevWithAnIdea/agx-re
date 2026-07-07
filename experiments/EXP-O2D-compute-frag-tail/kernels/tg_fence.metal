#include <metal_stdlib>
using namespace metal;
// Threadgroup-memory kernel so a mem_threadgroup fence is actually emitted; lets us
// read the 0x07 fence byte+3 scope byte for threadgroup vs the device fence.
kernel void tgf_relaxed(device uint* o [[buffer(2)]], threadgroup uint* s [[threadgroup(0)]],
                        uint i [[thread_position_in_grid]], uint li [[thread_position_in_threadgroup]],
                        uint tl [[threads_per_threadgroup]]) {
    s[li] = li;
    atomic_thread_fence(mem_flags::mem_threadgroup, memory_order_relaxed);
    o[i] = s[(li + 1) % tl];
}
kernel void tgf_seqcst(device uint* o [[buffer(2)]], threadgroup uint* s [[threadgroup(0)]],
                       uint i [[thread_position_in_grid]], uint li [[thread_position_in_threadgroup]],
                       uint tl [[threads_per_threadgroup]]) {
    s[li] = li;
    atomic_thread_fence(mem_flags::mem_threadgroup, memory_order_seq_cst);
    o[i] = s[(li + 1) % tl];
}
kernel void tgf_seqcst_tgscope(device uint* o [[buffer(2)]], threadgroup uint* s [[threadgroup(0)]],
                               uint i [[thread_position_in_grid]], uint li [[thread_position_in_threadgroup]],
                               uint tl [[threads_per_threadgroup]]) {
    s[li] = li;
    atomic_thread_fence(mem_flags::mem_threadgroup, memory_order_seq_cst, thread_scope_threadgroup);
    o[i] = s[(li + 1) % tl];
}
