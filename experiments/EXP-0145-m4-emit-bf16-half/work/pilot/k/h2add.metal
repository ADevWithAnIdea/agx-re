#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]], device float* a [[buffer(1)]], device float* b [[buffer(2)]], device float* c [[buffer(3)]], uint tid [[thread_position_in_grid]]) {
    half2 x=half2(a[tid],a[tid+1u]),y=half2(b[tid],b[tid+1u]); half2 s=x+y; out[tid]=float(s.x)+float(s.y)*1024.0f;
}
