// EXP-0092 srprobe: the get_sr splice target for GLIO-A02/A06.
//
// Reads ONE built-in (thread_index_in_simdgroup / simd_lane_id, SR 0x82) into
// register v via a single get_sr, then an INTERVENING, SEPARATE ALU
// instruction (w = v + 1000) consumes it, and a THIRD, separate store writes
// w. This gives the spliced get_sr's result a LATER, separate reader (the
// add), not just an adjacent/same-instruction consumer -- the discipline
// docs/isa/register-move-and-liveness.md requires after EXP-0086 found a
// producer-side bit that corrupts only a later separate instruction's read.
//
// Splicing byte1 (sr_sel) of the get_sr sweeps which special register is
// read; splicing the dst fields (byte0 hi nibble + byte+3 bits5-7) sweeps the
// destination GPR. +1000 lets a genuine zero-valued SR read be told apart
// from total dispatch failure (STATUS != OK) while keeping the readback an
// unambiguous function of the spliced field for any SR whose value is small.
#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]],
              uint gid [[thread_position_in_grid]],
              uint v [[thread_index_in_simdgroup]]) {
    uint w = v + 1000u;
    out[gid] = w;
}
