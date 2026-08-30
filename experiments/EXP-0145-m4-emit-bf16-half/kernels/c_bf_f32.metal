// EXP-0145 carrier -- AUTHORED BY US (clean-room OWN-SHADER).
// `sent` is the INTEGRITY SENTINEL: a constant store on a path that does not
// depend on the instruction under test, so a poisoned (0xDEADBEEF) read-back
// distinguishes "the op produced 0" from "the program never ran" (the failure
// mode EXP-0140 found behind EXP-0128's mov_imm 'silent zero').
#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
              device float* b [[buffer(2)]], device uint* sent [[buffer(4)]],
              uint g [[thread_position_in_grid]]) {
    bfloat x = bfloat(a[g]);
    bfloat y = bfloat(b[g]);
    out[g] = float(x + y);
    sent[g] = 0xA5A5A5A5u;
}
