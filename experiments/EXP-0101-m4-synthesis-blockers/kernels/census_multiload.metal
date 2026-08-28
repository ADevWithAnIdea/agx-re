// EXP-0101 census kernel #2 -- OWN MSL, authored for this experiment.
// Ten INDEPENDENT loads, each kept live until its own later use (forces
// the register allocator to place each loaded value in a DIFFERENT
// register, rather than reusing r0 ten times as the trivial single-load
// kernel does) -- gives a 10-point (device_load field values) -> (ALU
// consumer field values) correspondence table instead of one. Used by
// analysis/census.py (RESULTS.md H1 "OBSERVED: compiler census", the
// decisive 10/10 extmode=2*consumer_reg match).
#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              device float* mem [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    float v0 = mem[tid+0];
    float v1 = mem[tid+1];
    float v2 = mem[tid+2];
    float v3 = mem[tid+3];
    float v4 = mem[tid+4];
    float v5 = mem[tid+5];
    float v6 = mem[tid+6];
    float v7 = mem[tid+7];
    float v8 = mem[tid+8];
    float v9 = mem[tid+9];
    out[tid+0] = v0 + 1.0;
    out[tid+1] = v1 + 2.0;
    out[tid+2] = v2 + 3.0;
    out[tid+3] = v3 + 4.0;
    out[tid+4] = v4 + 5.0;
    out[tid+5] = v5 + 6.0;
    out[tid+6] = v6 + 7.0;
    out[tid+7] = v7 + 8.0;
    out[tid+8] = v8 + 9.0;
    out[tid+9] = v9 + 10.0;
}
