// RT-1b memory kernels (OUR OWN MSL). Independent re-proof of the byte+5 index
// register + byte+6 inert + byte+1 space + immediate offset field, with edge
// cases: multi-register index bank, negative index, large offset, threadgroup
// vs device space, and float4/uint4 vector loads.
#include <metal_stdlib>
using namespace metal;

// --- index-register BANK: 4 candidate indices live in registers; out0=a[i0].
// Sweeping the a[i0]-load byte+5 should pick r0/r1/r2/r3 (=i0..i3) as the index.
// a[j] = 0xA000+j is a DIFFERENT ramp than RT-1a's 100*j+3, so a[k] reveals k
// and cannot be confused with a raw small register value.
// gid*4+k indexing keeps the loads PER-THREAD (else uniform loads hoist into the
// constant/uniform program and vanish from _agc.main).
kernel void bank(device uint* out [[buffer(0)]],
                 device uint* out2 [[buffer(1)]],
                 device const uint* a [[buffer(2)]],
                 device const uint* idx [[buffer(3)]],
                 uint gid [[thread_position_in_grid]]) {
    uint i0 = idx[gid*4 + 0], i1 = idx[gid*4 + 1], i2 = idx[gid*4 + 2], i3 = idx[gid*4 + 3];
    out[gid] = a[i0];
    out2[gid] = i1 * 3u + i2 * 5u + i3 * 7u;   // keep i1..i3 live, distinct combine
}

// --- single scalar load a[i]: clean target for the immediate-offset field.
kernel void one(device uint* out [[buffer(0)]],
                device const uint* a [[buffer(1)]],
                device const uint* idx [[buffer(2)]],
                uint gid [[thread_position_in_grid]]) {
    out[gid] = a[idx[gid]];
}

// --- compiler-computed +1 / -1 offsets: expected byte-identical loads (offset
// lives in a preceding ALU op, per the doc). Two kernels to diff.
kernel void plus1(device int* out [[buffer(0)]], device const int* a [[buffer(1)]],
                  uint gid [[thread_position_in_grid]]) { out[gid] = a[gid + 1]; }
kernel void minus1(device int* out [[buffer(0)]], device const int* a [[buffer(1)]],
                   uint gid [[thread_position_in_grid]]) { out[gid] = a[int(gid) - 1]; }

// --- threadgroup copy (space byte+1 = 0x02): tile[lid]=a[gid]; barrier; out=tile[lid].
kernel void tg(device int* out [[buffer(0)]], device const int* a [[buffer(1)]],
               uint gid [[thread_position_in_grid]], uint lid [[thread_position_in_threadgroup]]) {
    threadgroup int tile[64];
    tile[lid] = a[gid];
    threadgroup_barrier(mem_flags::mem_threadgroup);
    out[gid] = tile[lid];
}

// --- plain device copy (space byte+1 = 0x00): baseline to splice space bit into.
kernel void dev(device uint* out [[buffer(0)]], device const uint* a [[buffer(1)]],
                uint gid [[thread_position_in_grid]]) { out[gid] = a[gid]; }

// --- vector loads: one load moves N words; byte+5 is the index reg, not "count".
kernel void v4(device uint4* out [[buffer(0)]], device const uint4* a [[buffer(1)]],
               uint gid [[thread_position_in_grid]]) { out[gid] = a[gid]; }
kernel void v2(device uint2* out [[buffer(0)]], device const uint2* a [[buffer(1)]],
               uint gid [[thread_position_in_grid]]) { out[gid] = a[gid]; }
