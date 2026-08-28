// cf_misc.metal -- EXP-0104 authored MSL: predicate-file, divergent-return, branch-reach,
// and additional reducible if/else SHAPE kernels for the CF-* cluster.
// Own-authored MSL only (OWN-SHADER). No Apple binary read or copied.
#include <metal_stdlib>
using namespace metal;

// ---------------------------------------------------------------------------
// predalias -- CF-05/CF-06: two INDEPENDENT, SIMULTANEOUSLY-LIVE divergent
// regions (outer predicate on v, nested inner predicate on b) forcing the
// compiler to keep two predicate values live at once. We then splice one
// icmp_pred's dst_pred nibble to collide with the other's and watch for
// cross-talk (silent-zero / wrong-branch pattern), per the register-move
// silent-zero precedent (docs/isa/register-move-and-liveness.md).
kernel void predalias(device int* o [[buffer(0)]],
                       device int* o2 [[buffer(1)]],
                       device const int* a [[buffer(2)]],
                       device const int* bb [[buffer(3)]],
                       uint i [[thread_position_in_grid]]) {
    // Data-dependent inner LOOPS (not just assignments) force the compiler to
    // emit real icmp_pred + if_push/pop_reconverge branches rather than
    // collapsing everything to a branchless compare-select (per EXP-0010's
    // "loops defeat predication" precedent; a pure-assignment version of this
    // kernel was tried first and compiled entirely to select/isel ops with NO
    // icmp_pred at all -- recorded as a negative finding in RESULTS.md).
    int v = a[i];
    int b = bb[i];
    int r1, r2;
    if (v > 16) {
        if (b > 16) {
            r1 = 0;
            for (int k = 0; k < b; k++) { r1 += 1; }
            r1 += v;
        } else {
            r1 = v;
        }
        r2 = r1 * 2;
    } else {
        r1 = -v;
        if (b > 16) {
            r2 = 0;
            for (int k = 0; k < b; k++) { r2 += 1; }
        } else {
            r2 = -b;
        }
    }
    o[i] = r1;
    o2[i] = r2;
}

// ---------------------------------------------------------------------------
// CF-04: divergent early RETURN vs an ordinary if/else JOIN (no return) --
// structurally diffed at compile time (own-shader-diff), and each also run
// for correctness.
kernel void ret_early(device int* o [[buffer(0)]],
                       device const int* a [[buffer(1)]],
                       uint i [[thread_position_in_grid]]) {
    int v = a[i];
    if (v > 16) { o[i] = 777; return; }
    int acc = 0;
    for (int k = 0; k < v; k++) { acc += v; }
    o[i] = acc;
}

kernel void plain_join(device int* o [[buffer(0)]],
                        device const int* a [[buffer(1)]],
                        uint i [[thread_position_in_grid]]) {
    int v = a[i];
    int acc;
    if (v > 16) { acc = 777; } else {
        acc = 0;
        for (int k = 0; k < v; k++) { acc += v; }
    }
    o[i] = acc;
}

// multi_return -- THREE divergent early-return points at three different
// nesting depths, all converging on the SAME epilogue store, plus a
// fall-through 4th path. Tests "shared epilogue" (CF-04) beyond a single
// return point.
kernel void multi_return(device int* o [[buffer(0)]],
                          device const int* a [[buffer(1)]],
                          uint i [[thread_position_in_grid]]) {
    int v = a[i];
    if (v > 90) { o[i] = 1; return; }
    if (v > 60) {
        if (v > 75) { o[i] = 2; return; }
        o[i] = 3;
        return;
    }
    if (v > 30) { o[i] = 4; return; }
    o[i] = 5;
}

// ---------------------------------------------------------------------------
// branch-reach probe: a single real backward-jump loop (data-dependent trip
// count so it is not unrolled) with a stable, splice-target back-edge. We
// splice the `jump` 48-bit offset field to sweep displacement magnitude.
kernel void reach_loop(device int* o [[buffer(0)]],
                        device const int* a [[buffer(1)]],
                        uint i [[thread_position_in_grid]]) {
    int v = a[i];
    int s = 1;
    for (int k = 0; k < v; k++) { s = s * 3 + 1; }
    o[i] = s;
}

// ---------------------------------------------------------------------------
// CF-01/02: additional reducible if/else SHAPES beyond EXP-0010/RT-1b's
// nested-if/break/continue/early-return corpus -- diamond join, elseif
// chain, and if-nested-inside-else.
kernel void shape_diamond(device int* o [[buffer(0)]],
                           device const int* a [[buffer(1)]],
                           uint i [[thread_position_in_grid]]) {
    // diamond: two divergent paths that both write different values into the
    // SAME variable before a single shared join read (classic reducible CFG
    // diamond -- both branches must correctly reconverge before the shared use).
    int v = a[i];
    int x;
    if (v > 16) {
        x = v * 2;
    } else {
        x = v + 1000;
    }
    o[i] = x + 1;  // shared join use
}

kernel void shape_elseif_chain(device int* o [[buffer(0)]],
                                device const int* a [[buffer(1)]],
                                uint i [[thread_position_in_grid]]) {
    int v = a[i];
    if (v < 4) { o[i] = 100; }
    else if (v < 8) { o[i] = 200; }
    else if (v < 12) { o[i] = 300; }
    else if (v < 16) { o[i] = 400; }
    else if (v < 20) { o[i] = 500; }
    else { o[i] = 600; }
}

kernel void shape_if_in_else(device int* o [[buffer(0)]],
                              device const int* a [[buffer(1)]],
                              device const int* bb [[buffer(2)]],
                              uint i [[thread_position_in_grid]]) {
    int v = a[i];
    int b = bb[i];
    if (v > 16) {
        o[i] = v;
    } else {
        if (b > 16) {
            o[i] = -b;
        } else {
            int acc = 0;
            for (int k = 0; k < b; k++) { acc += 1; }
            o[i] = -1000 - acc;
        }
    }
}

// break/continue combined in a single data-dependent loop (not previously
// exercised together with a divergent condition mid-loop).
kernel void shape_break_continue(device int* o [[buffer(0)]],
                                  device const int* a [[buffer(1)]],
                                  uint i [[thread_position_in_grid]]) {
    int v = a[i];
    int acc = 0;
    for (int k = 0; k < v; k++) {
        if (k == 3) { continue; }
        if (k == 7) { break; }
        acc += k;
    }
    o[i] = acc;
}
