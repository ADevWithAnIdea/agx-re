// EXP-0112 carrier kernel for the CF family, matching EXP-0090's own
// carrier_p3.metal buffer shape (a real, own-compiled loop+if/else->select
// kernel) exactly, so this experiment's CF programs can reuse EXP-0090's
// own verbatim-reconstructed P3 instruction skeleton -- copied and labelled
// as such (see cf.py), never re-derived here. This kernel's OWN arithmetic
// is never executed (every case splices the whole _agc.main); it exists
// only to fix the buffer(0)=out/buffer(1)=a/buffer(2)=n base_slot bindings
// (re-derived fresh by baseline.py, never assumed -- EXP-0090's own
// finding was that carrier_p3.metal REVERSES buffer(1)/(2) relative to
// carrier_p1/p2.metal, a documented trap for a hand-assembling
// implementer) and to compile to an _agc.main region long enough (P3's own
// anchor is 152 bytes; padded here to comfortably more).
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
    out[tid] = r;
}
