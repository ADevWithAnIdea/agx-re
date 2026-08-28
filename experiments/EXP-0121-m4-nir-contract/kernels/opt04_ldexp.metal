#include <metal_stdlib>
using namespace metal;
// OPT-04: is dynamic-exponent ldexp(x,n) a directly executable Apple9 instruction with fully
// decoded operands? `n` MUST be runtime (buffer-sourced) -- a compile-time-constant exponent
// folds to fmul-by-power-of-two per tools/agx-isa/db.json's existing note and would never
// exercise the dedicated `fldexp` opcode at all.
kernel void k_ldexp_dynamic(device float* x [[buffer(0)]], device int* n [[buffer(1)]],
                             device float* out [[buffer(2)]], uint gid [[thread_position_in_grid]]) {
    out[gid] = ldexp(x[gid], n[gid]);
}
// Structural control: constant exponent (n=3), must NOT contain fldexp (folds to fmul).
kernel void k_ldexp_const3(device float* x [[buffer(0)]], device float* out [[buffer(1)]],
                            uint gid [[thread_position_in_grid]]) {
    out[gid] = ldexp(x[gid], 3);
}
