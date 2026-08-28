// EXP-0099 carrier kernel. OWN MSL. Deliberately kept LOW-REGISTER-PRESSURE
// and structurally close to EXP-0090's own proven-splicable carriers
// (kernels/carrier_p2.metal) -- an earlier, more elaborate version of this
// file (20 live output expressions) compiled and ran correctly UNSPLICED
// but silently failed every hand-built splice (reads landed as 0.0 even
// for a byte-for-byte reproduction of EXP-0090's own HW-VALIDATED
// finding_3 direct-forward pattern, which DID work when run against
// EXP-0090's own carrier_p2.metal in the same subprocess/harness). Root
// cause not fully isolated (see PROGRESS.md); the safe, time-boxed fix is
// to keep this carrier's natural register pressure low, matching the shape
// every prior successful hand-built-program experiment (EXP-0090) used.
// This kernel's own arithmetic is NEVER executed by any case (every case
// replaces the entire _agc.main body via splice); it exists only to
// establish the buffer(0)=out / buffer(1)=mem slot binding and an
// _agc.main region long enough to splice into.
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
