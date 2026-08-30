// EXP-0145 carrier -- AUTHORED BY US (clean-room OWN-SHADER).
// `sent` is the INTEGRITY SENTINEL: a constant store on a path that does not
// depend on the instruction under test, so a poisoned (0xDEADBEEF) read-back
// distinguishes "the op produced 0" from "the program never ran".
#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]], device const float* a [[buffer(1)]],
              device const float* b [[buffer(2)]], device uint* sent [[buffer(4)]],
              uint g [[thread_position_in_grid]]) {
    simdgroup_float8x8 A, B, C;
    simdgroup_load(A, a, 8);
    simdgroup_load(B, b, 8);
    simdgroup_multiply(C, A, B);
    simdgroup_store(C, out, 8);
    sent[g] = 0xA5A5A5A5u;
}
