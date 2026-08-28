// EXP-0138 MODE-B carrier kernels. OWN MSL.
//
// Each kernel exists to make the compiler emit ONE instance of the family
// under test, surrounded by its own (unmodified) load/store scaffolding, so
// that a single instruction can be spliced in place with the operands still
// coming from real memory the harness controls. The kernel's own arithmetic
// IS executed here (unlike kernels/carrier.metal, which is fully replaced).
//
// Shapes were chosen by this experiment's own pilot phase (work/pilot/):
// the two-output variants that changed the emitted form (k_hsat, k_hadd)
// were rejected in favour of the single-output form that emits the family
// cleanly; k_rsqrtf keeps its second output because the extra loads give the
// `src`-descriptor sweep more than one live register to find.
#include <metal_stdlib>
using namespace metal;

// falu2 (6B `09 01 1c 05 00 c0`) and falu2i (6B `09 c9 14 01 80 c0`)
kernel void k_add(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                  uint t [[thread_position_in_grid]]) { out[t] = a[t+0] + a[t+1]; }
kernel void k_addi(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                   uint t [[thread_position_in_grid]]) { out[t] = a[t+0] + 3.0f; }

// half_alu (6B `10 04 1c 02 00 c0`)
kernel void k_hadd(device half* out [[buffer(0)]], device half* a [[buffer(1)]],
                   uint t [[thread_position_in_grid]]) { out[t] = a[t+0] + a[t+1]; }
// half_alu_ext8 (8B `10 04 1c 02 01 00 00 82`)
kernel void k_hsat(device half* out [[buffer(0)]], device half* a [[buffer(1)]],
                   uint t [[thread_position_in_grid]]) { out[t] = saturate(a[t+0] + a[t+1]); }
// half_alu_fma12 (12B `10 04 1e 05 83 02 00 00 00 80 01 00`)
kernel void k_hfmaabs(device half* out [[buffer(0)]], device half* a [[buffer(1)]],
                      uint t [[thread_position_in_grid]]) { out[t] = fma(fabs(a[t+0]), a[t+1], a[t+2]); }
// copysign (4B `07 c2 88 00`)
kernel void k_copysign(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                       uint t [[thread_position_in_grid]]) { out[t] = copysign(a[t+0], a[t+1]); }
// fspecial (10B `af 01 56 02 02 00 b0 40 00 00`) -- fast-math build; the
// second output adds two more loads so the src-descriptor sweep has more
// than one live register to hit.
kernel void k_rsqrtf(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) {
    out[t]    = rsqrt(a[t+0]);
    out[t+1u] = a[t+1] + a[t+2];
}
// fspecial_est (6B `19 81 25 0b 00 c2`) -- the no-fast-math Newton-Raphson
// seed op; same two-output shape.
kernel void k_rsqrtn(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
                     uint t [[thread_position_in_grid]]) {
    out[t]    = rsqrt(a[t+0]);
    out[t+1u] = a[t+1] + a[t+2];
}
