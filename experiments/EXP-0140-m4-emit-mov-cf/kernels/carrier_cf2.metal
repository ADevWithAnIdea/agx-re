// EXP-0140 CF carrier.  IDENTICAL to EXP-0112's kernels/carrier_cf.metal
// (itself matched to EXP-0090's carrier_p3.metal buffer shape) except for a
// tail of extra arithmetic on `acc` ALONE, which lengthens `_agc.main` enough
// to hold this experiment's integrity-sentinel prologue in front of the reused
// skeleton.  The padding deliberately adds NO new buffer reference: EXP-0128's
// item (d) was confounded exactly because its padding added `a[]` reads, which
// shifted the compiler's base_slot/argument-table mapping.  base_slot values
// are re-derived from THIS kernel's own compile by harness/baseline.py and fed
// into the skeleton -- never assumed.
//
// This kernel's own arithmetic is never executed: every case splices the whole
// `_agc.main`.  It exists only to fix buffer(0)=out / buffer(1)=a / buffer(2)=n
// and to make the region long enough.
#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              device float* a [[buffer(1)]],
              device int* n [[buffer(2)]],
              uint tid [[thread_position_in_grid]]) {
    float acc = a[tid];
    int cnt = n[tid];
    for (int i = 0; i < cnt; i++) {
        acc = acc + 1.5f;
    }
    float r;
    if (acc > 100.0f) {
        r = acc * 2.0f;
    } else {
        r = acc - 3.0f;
    }
    r = r * 1.0000001f + 0.5f;
    r = r * 1.0000002f + 0.25f;
    r = r * 1.0000003f + 0.125f;
    r = r * 1.0000004f + 0.0625f;
    r = r * 1.0000005f + 0.03125f;
    r = r * 1.0000006f + 0.015625f;
    out[tid] = r;
}
