#include <metal_stdlib>
using namespace metal;

// EXP-0100 threadgroup-space device_store probe (mirrors EXP-0082's
// device_store methodology for threadgroup space). Single-thread dispatch
// (grid=1, tg=1). A 2048-word (8 KiB) threadgroup array is zero-filled by a
// compiler-unrolled loop (four threadgroup device_store instructions at
// idx_off 0/1/2/3, all BEFORE the first barrier); after the barrier, EXACTLY
// ONE threadgroup device_store (`tile[j] = 0x5A17C0DE`, j = i0 + i1 from
// idxbuf) runs -- the only threadgroup-space store occurring AFTER the first
// threadgroup_barrier, which is how the harness locates it unambiguously
// among the five total threadgroup stores in this kernel. A second barrier
// then orders a compiler-unrolled copy-out loop (`extra[w] = tile[w]`, all
// threadgroup LOADS, never confused with our STORE probe) so the harness can
// read back the whole 8 KiB tile and locate the effective store byte address
// exactly as EXP-0082's st_bank.metal did for device memory.
kernel void k(device uint* out          [[buffer(0)]],
              device uint* extra        [[buffer(1)]],
              const device uint* idxbuf [[buffer(3)]]) {
    threadgroup uint tile[2048];
    for (uint w = 0; w < 2048u; w++) {
        tile[w] = 0u;
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint i0 = idxbuf[0];
    uint i1 = idxbuf[1];
    uint j  = i0 + i1;
    tile[j] = 0x5A17C0DEu;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    for (uint w = 0; w < 2048u; w++) {
        extra[w] = tile[w];
    }
    uint i2 = idxbuf[2];
    uint i3 = idxbuf[3];
    out[0] = i2 + (i3 << 8) + j;
}
