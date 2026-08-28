// EXP-0145 carrier C8 -- AUTHORED BY US (clean-room OWN-SHADER).
// packed half2 fma: emits the LOW-half 0x10 half_alu_ext8 AND the HIGH-half
// 0x?8 h_alu_hi -- the only shape found that provokes the high-half form.
#include <metal_stdlib>
using namespace metal;
kernel void k(device half2* out       [[buffer(0)]],
              device const half2* a   [[buffer(1)]],
              device const half2* b   [[buffer(2)]],
              device const half2* c   [[buffer(3)]],
              uint g [[thread_position_in_grid]]) { out[g] = fma(a[g], b[g], c[g]); }
