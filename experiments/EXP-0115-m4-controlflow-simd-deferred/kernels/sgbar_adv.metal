// sgbar_adv.metal -- EXP-0115 item 7: adversarial simdgroup_barrier shapes,
// searching for ANY execution context where the compiler emits a nonzero
// instruction for simdgroup_barrier (EXP-0104 found byte-identical compiles
// with/without it for the plain single-call case at tg=32). Own-authored
// MSL, no Apple code read.
//
// Each "_bar" kernel has a "_nobar" twin that is byte-for-byte identical
// EXCEPT for the presence of the simdgroup_barrier call(s), so a structural
// (compile-only) diff isolates exactly what the barrier call costs, if
// anything, in each adversarial shape:
//   - loop:     barrier called INSIDE a genuinely per-lane-DIVERGENT-trip-count
//               loop, so different lanes call it a different NUMBER of times
//               (a spec-questionable but hardware-observable shape).
//   - ifdiv:    barrier called by only SOME lanes (divergent call presence,
//               not just divergent count).
//   - highreg:  barrier amid heavy register pressure (many live locals).
//   - double:   two consecutive barriers with different memory classes.
//   - nested:   barrier at CF nesting depth 8 (inside 8 nested divergent ifs).
#include <metal_stdlib>
using namespace metal;

// ---- loop: divergent per-lane call COUNT -----------------------------------
kernel void sgbar_loop_bar(device int* o [[buffer(0)]],
                            device const int* a [[buffer(1)]],
                            uint i [[thread_position_in_grid]]) {
    int v = a[i];
    int acc = 0;
    for (int k = 0; k < v; k++) {
        acc += k;
        simdgroup_barrier(mem_flags::mem_device);
    }
    o[i] = acc;
}
kernel void sgbar_loop_nobar(device int* o [[buffer(0)]],
                              device const int* a [[buffer(1)]],
                              uint i [[thread_position_in_grid]]) {
    int v = a[i];
    int acc = 0;
    for (int k = 0; k < v; k++) {
        acc += k;
    }
    o[i] = acc;
}

// ---- ifdiv: divergent call PRESENCE ----------------------------------------
kernel void sgbar_ifdiv_bar(device int* o [[buffer(0)]],
                             device const int* a [[buffer(1)]],
                             uint i [[thread_position_in_grid]]) {
    int v = a[i];
    if (v % 2 == 0) {
        simdgroup_barrier(mem_flags::mem_device);
    }
    o[i] = v * 2;
}
kernel void sgbar_ifdiv_nobar(device int* o [[buffer(0)]],
                               device const int* a [[buffer(1)]],
                               uint i [[thread_position_in_grid]]) {
    int v = a[i];
    if (v % 2 == 0) {
    }
    o[i] = v * 2;
}

// ---- highreg: heavy register pressure around the barrier ------------------
kernel void sgbar_highreg_bar(device int* o [[buffer(0)]],
                               device const int* a [[buffer(1)]],
                               uint i [[thread_position_in_grid]]) {
    int v = a[i];
    int r0=v+1,r1=v+2,r2=v+3,r3=v+4,r4=v+5,r5=v+6,r6=v+7,r7=v+8;
    int r8=v*2,r9=v*3,r10=v*4,r11=v*5,r12=v*6,r13=v*7,r14=v*8,r15=v*9;
    simdgroup_barrier(mem_flags::mem_device);
    int s = r0+r1+r2+r3+r4+r5+r6+r7+r8+r9+r10+r11+r12+r13+r14+r15;
    o[i] = s;
}
kernel void sgbar_highreg_nobar(device int* o [[buffer(0)]],
                                 device const int* a [[buffer(1)]],
                                 uint i [[thread_position_in_grid]]) {
    int v = a[i];
    int r0=v+1,r1=v+2,r2=v+3,r3=v+4,r4=v+5,r5=v+6,r6=v+7,r7=v+8;
    int r8=v*2,r9=v*3,r10=v*4,r11=v*5,r12=v*6,r13=v*7,r14=v*8,r15=v*9;
    int s = r0+r1+r2+r3+r4+r5+r6+r7+r8+r9+r10+r11+r12+r13+r14+r15;
    o[i] = s;
}

// ---- double: two consecutive barriers, different memory classes -----------
kernel void sgbar_double_bar(device int* o [[buffer(0)]],
                              device const int* a [[buffer(1)]],
                              uint i [[thread_position_in_grid]]) {
    int v = a[i] * 2;
    simdgroup_barrier(mem_flags::mem_device);
    simdgroup_barrier(mem_flags::mem_threadgroup);
    o[i] = v;
}
kernel void sgbar_double_nobar(device int* o [[buffer(0)]],
                                device const int* a [[buffer(1)]],
                                uint i [[thread_position_in_grid]]) {
    int v = a[i] * 2;
    o[i] = v;
}

// ---- nested: barrier at CF nesting depth 8 ---------------------------------
kernel void sgbar_nested_bar(device int* o [[buffer(0)]],
                              device const int* a [[buffer(1)]],
                              uint i [[thread_position_in_grid]]) {
    int v = a[i];
    if (v > 1) { if (v > 2) { if (v > 3) { if (v > 4) {
    if (v > 5) { if (v > 6) { if (v > 7) { if (v > 8) {
    simdgroup_barrier(mem_flags::mem_device);
    o[i] = v * 2;
    } else { o[i] = -8; return; } } else { o[i] = -7; return; }
    } else { o[i] = -6; return; } } else { o[i] = -5; return; }
    } else { o[i] = -4; return; } } else { o[i] = -3; return; }
    } else { o[i] = -2; return; } } else { o[i] = -1; return; }
}
kernel void sgbar_nested_nobar(device int* o [[buffer(0)]],
                                device const int* a [[buffer(1)]],
                                uint i [[thread_position_in_grid]]) {
    int v = a[i];
    if (v > 1) { if (v > 2) { if (v > 3) { if (v > 4) {
    if (v > 5) { if (v > 6) { if (v > 7) { if (v > 8) {
    o[i] = v * 2;
    } else { o[i] = -8; return; } } else { o[i] = -7; return; }
    } else { o[i] = -6; return; } } else { o[i] = -5; return; }
    } else { o[i] = -4; return; } } else { o[i] = -3; return; }
    } else { o[i] = -2; return; } } else { o[i] = -1; return; }
}
