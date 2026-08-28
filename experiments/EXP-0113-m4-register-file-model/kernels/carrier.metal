// EXP-0113 carrier kernel. OWN MSL. Byte-identical text to
// EXP-0099/EXP-0105's own kernels/carrier.metal (deliberately reused
// shape -- the only carrier this line of experiments has found reliably
// splicable, see EXP-0099 PROGRESS.md "INCIDENT"). This kernel's own
// arithmetic is NEVER executed by any SEED_CHECK/H1_ALIAS/CTRL/H2 case --
// every such case replaces the entire _agc.main body via splice at
// offset 0. It exists only to establish the buffer(0)=out / buffer(1)=mem
// slot binding and an _agc.main region long enough to splice into.
// baseline.py re-derives CARRIER_LEN fresh; a genuine drift is a
// pre-capture stop, not silently absorbed.
#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              device float* mem [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    float a0 = mem[tid+0], a1 = mem[tid+1], a2 = mem[tid+2], a3 = mem[tid+3];
    out[tid+0] = a0 + a1;
    out[tid+1] = a2 - a3;
    out[tid+2] = a0 * a2;
    out[tid+3] = a1 * a3;
}
