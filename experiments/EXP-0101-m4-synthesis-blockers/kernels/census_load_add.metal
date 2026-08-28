// EXP-0101 census kernel #1 -- OWN MSL, authored for this experiment.
// The SIMPLEST possible device_load -> float-ALU -> device_store shape:
// one load, one immediate add, one store. Used by analysis/census.py as
// the minimal compiler-emitted anchor for the load-to-ALU differential
// analysis (RESULTS.md H1 "OBSERVED: compiler census").
#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              device float* mem [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    float v = mem[tid];
    out[tid] = v + 10.0;
}
