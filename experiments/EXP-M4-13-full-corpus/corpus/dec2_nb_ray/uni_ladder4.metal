#include <metal_stdlib>
using namespace metal;
// Fewer uniforms (4) -> shorter ladder; diff vs the 8-uniform version isolates
// the per-slot dst/usrc increment.
struct U { uint a,b,c,d; };
kernel void k(constant U& u [[buffer(0)]],
              device uint* out [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    out[tid*4+0]=u.a; out[tid*4+1]=u.b; out[tid*4+2]=u.c; out[tid*4+3]=u.d;
}
