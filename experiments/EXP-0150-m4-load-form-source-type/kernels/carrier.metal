// EXP-0150 synthesis carrier. OWN MSL, authored for this experiment.
//
// Purpose: establish (a) the buffer binding out=buffer(0) / mem=buffer(1) and
// (b) an `_agc.main` region long enough to splice a whole hand-assembled AGX
// program over at offset 0. This kernel's OWN arithmetic never executes in any
// case: every case replaces the entire spliced region with a program built
// instruction-by-instruction through tools/agx-isa `isadb.assemble()`.
//
// Shape deliberately LOW-REGISTER-PRESSURE. EXP-0099 (PROGRESS Milestone 3) and
// EXP-0101 both record that a higher-pressure carrier silently zeroes spliced
// `device_load` results, which would forge exactly the negative this experiment
// is trying to measure. The compiled `_agc.main` length is re-derived by the
// harness before every capture and compared to the frozen contract value --
// never assumed.
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
