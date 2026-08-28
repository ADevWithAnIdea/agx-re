// EXP-0092 dstprobe: get_sr DESTINATION-register-field boundary probe
// (GLIO-A02 "destination low/high bits across the full legal GPR range").
//
// v = thread_position_in_grid.x (get_sr sr_sel 0xa0) is read into a register,
// then used AS THE ADDRESS to a device_store (out[v] = 1u). The compiler
// wires the SAME physical register into device_store's index_reg field
// (HW-confirmed by direct decode: for the natural compile, get_sr dst == the
// store's index_reg, byte for byte). Splicing get_sr's dst fields (byte0
// high nibble + byte+3 bits[5:8]) AND device_store's index_reg byte to the
// SAME candidate register number keeps both instructions pointed at one
// physical register: this is a genuinely separate, EXPLICIT, LATER
// instruction reading the spliced register (the store's address computation)
// -- not adjacent same-instruction forwarding -- satisfying the later-read
// discipline in docs/isa/register-move-and-liveness.md.
//
// grid=1,tg=1: thread 0 always reads v=0, so a CORRECT round trip at any
// candidate register always writes out[0]=1 and leaves the rest of a large
// zero-initialized output buffer untouched. Any deviation (different slot
// written, no slot written, or a command-buffer fault) is a direct, register-
// encoding-agnostic signal that the candidate register is not viable.
#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]],
              uint v [[thread_position_in_grid]]) {
    out[v] = 1u;
}
