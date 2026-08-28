#include <metal_stdlib>
using namespace metal;
// OPT-01: does preserving NIR fdiv let Apple9 legalization select two OBSERVABLY DISTINCT
// hardware sequences for relaxed vs precise division? Three functions isolate namespace vs.
// global fast-math flag (EXP-0103 FP-07 precedent):
//   k_div_plain     -- plain `/`. Compiled TWICE by the harness: once with the default
//                       (fast-math ON == relaxed) flag, once with --no-fast-math (precise),
//                       matching EXP-0074's exact precise-division setup.
//   k_div_fast_ns   -- explicit fast::divide(a,b), always compiled with --no-fast-math so a
//                       divergence from k_div_plain(--no-fast-math) isolates the NAMESPACE
//                       choice from the global flag.
//   k_div_precise_ns-- explicit precise::divide(a,b) if it exists in this Metal version
//                       (probed separately by harness/build.sh smoke-compile; if it does not
//                       compile, this function is simply not exercised and that fact is
//                       recorded, not silently assumed).
kernel void k_div_plain(device float* a [[buffer(0)]], device float* b [[buffer(1)]],
                         device float* out [[buffer(2)]], uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] / b[gid];
}
kernel void k_div_fast_ns(device float* a [[buffer(0)]], device float* b [[buffer(1)]],
                           device float* out [[buffer(2)]], uint gid [[thread_position_in_grid]]) {
    out[gid] = fast::divide(a[gid], b[gid]);
}
kernel void k_div_precise_ns(device float* a [[buffer(0)]], device float* b [[buffer(1)]],
                              device float* out [[buffer(2)]], uint gid [[thread_position_in_grid]]) {
    out[gid] = precise::divide(a[gid], b[gid]);
}
