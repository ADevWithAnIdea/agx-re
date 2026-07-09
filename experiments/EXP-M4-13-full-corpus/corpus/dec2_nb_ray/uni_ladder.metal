#include <metal_stdlib>
using namespace metal;
// Uniform-read ladder: copy 8 scalar constant-buffer uniforms straight to
// 8 outputs. Provokes the compact uniform->GPR MOVE (Xb YY 01 08) in a clean
// row so dst=byte0-hi-nibble and usrc=byte1 can be read off directly.
struct U { uint a,b,c,d,e,f,g,h; };
kernel void k(constant U& u [[buffer(0)]],
              device uint* out [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    out[tid*8+0]=u.a; out[tid*8+1]=u.b; out[tid*8+2]=u.c; out[tid*8+3]=u.d;
    out[tid*8+4]=u.e; out[tid*8+5]=u.f; out[tid*8+6]=u.g; out[tid*8+7]=u.h;
}
