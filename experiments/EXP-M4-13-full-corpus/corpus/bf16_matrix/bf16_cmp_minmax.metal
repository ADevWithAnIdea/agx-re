#include <metal_stdlib>
using namespace metal;
// bfloat compare + select path. NOTE: min/max/abs/floor are ambiguous for bfloat
// (no bfloat overload), so we hand-roll them with bfloat comparisons + ternary select
// and negation — isolating bf16 fcmp + conditional-move + fneg, no float promotion.
kernel void kmain(device bfloat* o [[buffer(0)]],
                  device const bfloat* a [[buffer(1)]],
                  device const bfloat* b [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    bfloat x = a[i], y = b[i];
    bfloat mn = (x < y) ? x : y;
    bfloat mx = (x > y) ? x : y;
    bfloat lo = bfloat(0);
    bfloat c  = (mn < lo) ? lo : ((mn > mx) ? mx : mn);   // clamp(mn, 0, mx)
    bfloat ax = (x < lo) ? -x : x;                        // abs(x)
    bfloat sel = (x >= y) ? mx : mn;
    o[i] = c + ax + sel;
}
