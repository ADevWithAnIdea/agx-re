// EXP-0141 synthesis carrier. OWN MSL, authored for this experiment.
//
// Purpose: establish (a) the buffer binding out=buffer(0) / mem=buffer(1) and
// (b) an `_agc.main` region long enough to splice a whole hand-assembled AGX
// program over at offset 0. This kernel's OWN arithmetic is never executed by
// any synthesis case -- every such case replaces the entire body.
//
// Shape deliberately LOW-REGISTER-PRESSURE: EXP-0099 PROGRESS.md Milestone 3
// and EXP-0101 both record that a higher-pressure carrier silently zeroes
// spliced device_load results. Re-derived fresh by baseline.py before every
// capture (CARRIER_LEN / SLOT_OUT / SLOT_MEM are never assumed).
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
