// cf_pred.metal -- EXP-0115 item 3: icmp_pred.dst_pred / if_push_pred.pred
// mechanism probe target. Own-authored MSL, a 4-level nested divergent-return
// if-chain (same shape as EXP-0104's ifnest_004), reproduced here as our own
// independent source. The compiled bytes give a stable, known offset pair:
// icmp_pred (outermost compare) immediately followed by if_push (the
// mask-stack push it feeds) -- the splice targets for the dst_pred / pred
// field matrix. No Apple code read.
#include <metal_stdlib>
using namespace metal;

kernel void predtest_004(device int* o [[buffer(0)]],
                          device const int* a [[buffer(1)]],
                          uint i [[thread_position_in_grid]]) {
    int v = a[i];
    if (v > 1) {
    if (v > 2) {
    if (v > 3) {
    if (v > 4) {
    int acc = 0;
    for (int k = 0; k < v; k++) { acc += v; }
    o[i] = acc;
    } else {
    o[i] = -(1000 + 4);
    return;
    }
    } else {
    o[i] = -(1000 + 3);
    return;
    }
    } else {
    o[i] = -(1000 + 2);
    return;
    }
    } else {
    o[i] = -(1000 + 1);
    return;
    }
}
