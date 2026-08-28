#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]], device float* a [[buffer(1)]], device float* b [[buffer(2)]], device float* c [[buffer(3)]], uint tid [[thread_position_in_grid]]) {
    bfloat x=bfloat(a[tid]),y=bfloat(b[tid]); bfloat s=x+y; out[tid]=float(s*x);
}
