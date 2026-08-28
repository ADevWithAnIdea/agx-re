// reach.metal -- EXP-0115 item 1: branch-reach boundary map. Own-authored MSL,
// structurally identical to EXP-0104's cf_misc.metal:reach_loop (a single real
// backward-jump loop with a data-dependent trip count so the compiler cannot
// unroll it), reproduced here as our own independent source so this
// experiment does not depend on EXP-0104's kernel file. No Apple code read.
#include <metal_stdlib>
using namespace metal;

kernel void reach_loop(device int* o [[buffer(0)]],
                        device const int* a [[buffer(1)]],
                        uint i [[thread_position_in_grid]]) {
    int v = a[i];
    int s = 1;
    for (int k = 0; k < v; k++) { s = s * 3 + 1; }
    o[i] = s;
}
