// EXP-0200 compute carriers for the 2-BYTE compact-word holes (AUTHORED BY US;
// OWN-SHADER).
//
// PURPOSE. `n1_word` (01 00), `n2_compact2` (02 00) and `n3_word` (03 02) are
// fieldless 2-byte tokens. `validation.json` labels each `_instruction` as
// `tokenization-only`: "needed to make the instruction length and framing come
// out right, and round-trips exactly; its semantics are unknown". Their whole
// hardware claim is therefore a LENGTH claim, and no experiment has ever asked
// the hardware what length it actually consumes at those encodings.
//
// This file supplies carriers whose compiled `_agc.main` contains such 2-byte
// tokens ON THE EXECUTED PATH, with a NON-ZERO host-computed oracle, so that a
// 2-byte HOLE can be re-filled with a word WE synthesize and the hardware asked
// whether the successor instruction is still decoded at hole+2.
//
// WHY THESE CONSTRUCTS. `db.json` records where each word is emitted (from the
// own-MSL corpus, EXP-M4-13 R5/R7):
//   n1_word      -- between full ops before jump / convert / frame_marker /
//                   falu / fspecial / store / icmp  -> `k_w_sel`, `k_w_cf`
//   n2_compact2  -- transcendental / half / atan kernels                -> `k_w_half`, `k_w_trans`
//   n3_word      -- SFU range-reduction / predicate operand marker the
//                   transcendental and select paths emit               -> `k_w_trans`, `k_w_mix`
// The census (analysis/census200.py) decides which holes actually exist; this
// file only has to make them likely.
//
// EVERY ORACLE IS NON-ZERO BY CONSTRUCTION (FIELD-SWEEP-PROTOCOL 3.6): on
// Apple9 a wrong value usually produces a SILENT ZERO, and a zero oracle scores
// that silent zero as a pass.
//
// POISONED READ-BACK + INTEGRITY SENTINEL (protocol 7, instruments 1 and 2).
// `out` is bound as an INPUT pre-filled with POISON(i) = 0xDEADBEEF + i.
// `out[1] = 7.5f` is written FIRST, through a path independent of every hole
// under test (it is a store of a literal, before any of the arithmetic whose
// compiled form contains the holes). `out[2..3]` are never stored to and must
// still read back as poison.
//
// THE OBSERVABLE DOES NOT CO-VARY WITH THE MUTATION (protocol 3a). The mutated
// bytes are an interior compact word; the observable is the value the program
// already computes into out[0]. No part of the read-back path is derived from
// the bytes written.
//
// Inputs: buffer(1) = 4 floats {4.0, 3.0, 2.0, 1.0}, authored by us in
// harness/carriers200.py. They exist to defeat constant folding; every oracle
// below is computed on the HOST from this file plus those constants, never from
// an observed GPU output.
//
// Shape (not values) reused and cited from EXP-0187 kernels/k_rq187.metal and
// EXP-0184 kernels/k_rq184.metal -- our own MSL, same project, same rules.
#include <metal_stdlib>
using namespace metal;

#define W_PROLOGUE                                  \
    if (gid == 0) out[1] = 7.5f;                    \
    float x = in[0];   /* 4.0 */                    \
    float y = in[1];   /* 3.0 */                    \
    float z = in[2];   /* 2.0 */                    \
    float w = in[3];   /* 1.0 */                    \
    (void)z; (void)w;

// transcendental / SFU path: sqrt, rsqrt, exp2, log2, atan, tanh.
// 2 + 8 + 2 + 0.5 + 0 + 0 = 12.5
kernel void k_w_trans(device float *out [[buffer(0)]],
                      const device float *in [[buffer(1)]],
                      uint gid [[thread_position_in_grid]]) {
    W_PROLOGUE
    float r = precise::sqrt(x) + exp2(y) + log2(x) + precise::rsqrt(x);
    r += atan(x - x);
    r += tanh(y - y);
    if (gid == 0) out[0] = r;
}

// select / min-max / ternary path. 10 + 7 + 5 + 100 = 122
kernel void k_w_sel(device float *out [[buffer(0)]],
                    const device float *in [[buffer(1)]],
                    uint gid [[thread_position_in_grid]]) {
    W_PROLOGUE
    float r = (x > y) ? 10.0f : 1.0f;
    r += fmin(x, y) + fmax(x, y);
    r += select(2.0f, 5.0f, x != y);
    int i = int(x);
    r += float(((i & 3) == 0) ? 100 : 20);
    if (gid == 0) out[0] = r;
}

// divergent control flow: continue + break inside a counted loop.
// i=0..3 -> 0+1+2+3 = 6; i=4 == int(x) -> +100 = 106; i=5 -> +5 = 111;
// i=6 -> 6 > 5 -> break.  = 111
kernel void k_w_cf(device float *out [[buffer(0)]],
                   const device float *in [[buffer(1)]],
                   uint gid [[thread_position_in_grid]]) {
    W_PROLOGUE
    float acc = 0.0f;
    int lim = int(x);
    for (int i = 0; i < 8; ++i) {
        if (i == lim) { acc += 100.0f; continue; }
        if (i > 5) { break; }
        acc += float(i);
    }
    if (gid == 0) out[0] = acc;
}

// native half path. 2 + 8 + 12 = 22
kernel void k_w_half(device float *out [[buffer(0)]],
                     const device float *in [[buffer(1)]],
                     uint gid [[thread_position_in_grid]]) {
    W_PROLOGUE
    half hx = half(x), hy = half(y);
    half r = precise::sqrt(hx) + exp2(hy) + hy * hx;
    if (gid == 0) out[0] = float(r);
}

// mixed loads / int compare / branchy select. 4*1 + 3*2 + 2*3 = 16, +2 = 18
kernel void k_w_mix(device float *out [[buffer(0)]],
                    const device float *in [[buffer(1)]],
                    uint gid [[thread_position_in_grid]]) {
    W_PROLOGUE
    float r = 0.0f;
    for (int i = 0; i < 3; ++i) { r += in[i] * float(i + 1); }
    r += (x > y) ? log2(x) : log2(y);
    if (gid == 0) out[0] = r;
}

// barrier / threadgroup-memory path, where `n4_cf_word` is documented to appear
// (before a pop_reconverge / threadgroup_barrier). 4 + 3 + 2 + 1 = 10, *3 = 30
kernel void k_w_bar(device float *out [[buffer(0)]],
                    const device float *in [[buffer(1)]],
                    uint gid [[thread_position_in_grid]],
                    uint tid [[thread_position_in_threadgroup]]) {
    W_PROLOGUE
    threadgroup float sh[4];
    sh[tid & 3u] = x + y + z + w;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    float r = sh[0] * 3.0f;
    if (x > y) { r += 0.0f; } else { r -= 1000.0f; }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    if (gid == 0) out[0] = r;
}
