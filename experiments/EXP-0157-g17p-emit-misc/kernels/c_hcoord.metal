// EXP-0145 carrier -- AUTHORED BY US (clean-room OWN-SHADER).
// `sent` is the INTEGRITY SENTINEL: a constant store on a path that does not
// depend on the instruction under test, so a poisoned (0xDEADBEEF) read-back
// distinguishes "the op produced 0" from "the program never ran".
#include <metal_stdlib>
using namespace metal;
kernel void k(device half2* out [[buffer(0)]], device const half2* a [[buffer(1)]],
              device const half2* b [[buffer(2)]], device uint* sent [[buffer(4)]],
              uint g [[thread_position_in_grid]]) {
    half2 x = a[g], y = b[g];
    out[g] = half2(x.x * y.x + x.y, x.y * y.y + x.x);
    sent[g] = 0xA5A5A5A5u;
}
