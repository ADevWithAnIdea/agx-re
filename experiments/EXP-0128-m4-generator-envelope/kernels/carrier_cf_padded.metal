// EXP-0128 carrier kernel for the CF-EXT family (item d: control-flow
// displacement generator). SAME buffer declaration order, SAME two
// buffer reads (a[tid], n[tid]) as EXP-0112/EXP-0090's own carrier_cf.metal
// / carrier_p3.metal -- deliberately NOT adding any new buffer reference,
// because a first attempt at padding this carrier via extra a[]-indexed
// reads was found (this experiment's own pilot phase, disclosed in
// PROGRESS.md) to shift the compiler's base_slot/argument-table mapping
// relative to the un-padded carrier -- reproducing, in a NEW shape, the
// exact base_slot trap cf.py's own module docstring already warns about
// (a stable wrong value of 2^26 = 67108864.0, GPUTIME multi-second,
// consistent with `n` being read from a garbage/huge trip count). Padding
// here instead extends the compiled ARITHMETIC on `acc` alone (no new
// buffer touched), which this experiment's own baseline check (below)
// confirms preserves the SAME base_slot assignment (out=0, a=2, n=1) as
// the un-padded carrier.
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
    // padding: extra dead arithmetic on `r`/`acc` alone (no new buffer
    // reference) so the compiled region has spare bytes for spliced
    // CF-EXT variants; never reached by any spliced case (which always
    // installs its own stop()).
    float pad = acc;
    for (int j = 0; j < 4; j++) {
        pad = pad * 1.0000001f + float(j);
    }
    if (pad > 1.0e30f) {
        r = pad;
    }
    out[tid] = r;
}
