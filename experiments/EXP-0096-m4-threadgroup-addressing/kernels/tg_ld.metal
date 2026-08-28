#include <metal_stdlib>
using namespace metal;

// EXP-0096 threadgroup-space device_load probe (mirrors the EXP-0082
// device_load methodology, applied to the threadgroup address space instead
// of device memory). Single-thread dispatch (grid=1, tg=1). A 2048-word
// (8 KiB) threadgroup array is populated from device input `a[]` by a
// compiler-unrolled loop (four threadgroup device_store instructions at
// idx_off 0/1/2/3, confirmed at authoring/compile time -- none of them is our
// probe); after a barrier, EXACTLY ONE threadgroup device_load reads
// tile[j] with j = i0 + i1 (ALU-computed from idxbuf, mirroring EXP-0082's
// canonical indexed form). That load -- the only threadgroup-space
// device_load anywhere in this kernel -- is the probe whose address fields
// (idx_off / elem_size / index_reg) the harness splices.
kernel void k(device uint* out          [[buffer(0)]],
              device uint* out2         [[buffer(1)]],
              const device uint* a      [[buffer(2)]],
              const device uint* idxbuf [[buffer(3)]]) {
    threadgroup uint tile[2048];
    for (uint w = 0; w < 2048u; w++) {
        tile[w] = a[w];
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint i0 = idxbuf[0];
    uint i1 = idxbuf[1];
    uint j  = i0 + i1;
    out[0]  = tile[j];
    uint i2 = idxbuf[2];
    uint i3 = idxbuf[3];
    out2[0] = i2 + (i3 << 8) + j;
}
