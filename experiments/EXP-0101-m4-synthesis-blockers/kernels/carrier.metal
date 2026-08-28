// EXP-0101 carrier kernel. OWN MSL, authored by this experiment. Byte-for-byte
// identical in shape to EXP-0099-m4-lifetime-field-model/kernels/carrier.metal
// (itself modeled on EXP-0090's carrier_p2.metal) -- deliberately
// LOW-REGISTER-PRESSURE, which EXP-0099's own PROGRESS.md Milestone 3
// documented as the shape needed for reliable device_load splicing (a more
// elaborate, higher-pressure carrier silently zeroed every device_load
// splice for reasons not fully isolated there). Reused verbatim rather than
// re-deriving a new carrier from scratch, since this experiment's own H1
// (device_load->ALU bridge) and H2 (reg_move) hypotheses are carrier-shape
// orthogonal and re-deriving CARRIER_LEN/SLOT_OUT/SLOT_MEM fresh via
// baseline.py (this experiment's own copy) is what's actually load-bearing,
// not the specific kernel text.
//
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
