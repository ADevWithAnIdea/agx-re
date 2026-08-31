// EXP-0219 anchor probe (AUTHORED BY US for this experiment).
//
// The smallest MSL that makes the public Metal runtime compiler emit ONE
// `imad`. Same one-line shape as EXP-0160's `k_imad` (same project, same
// rules), re-authored here so this experiment is self-contained. The emitted
// instruction's bytes are lifted VERBATIM into a synthesized program
// (harness/imad_helpers.py) so every operand it names is a register WE seeded.
//
// CLEAN-ROOM: OWN-SHADER. We compile OUR OWN source through the public runtime
// API and read the AGX bytes produced from it. No Apple binary is inspected.
#include <metal_stdlib>
using namespace metal;

kernel void k_imad(device const int* a [[buffer(0)]],
                   device const int* b [[buffer(1)]],
                   device int* out [[buffer(2)]],
                   uint g [[thread_position_in_grid]]) {
    out[g] = a[g] * b[g] + 12345;            // imad
}
