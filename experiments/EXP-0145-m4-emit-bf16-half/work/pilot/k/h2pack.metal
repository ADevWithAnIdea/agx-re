#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]], device float* a [[buffer(1)]], device float* b [[buffer(2)]], device float* c [[buffer(3)]], uint tid [[thread_position_in_grid]]) {
    half2 x=half2(a[tid],b[tid]); device half2* o=(device half2*)out; o[tid]=x;
}
