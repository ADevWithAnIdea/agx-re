#include <metal_stdlib>
using namespace metal;
// pure half in/out -> native 0x10 half ALU (no float conversions)
kernel void k_pureadd(device const half* a [[buffer(0)]], device const half* b [[buffer(1)]], device half* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=a[i]+b[i]; }
kernel void k_puremul(device const half* a [[buffer(0)]], device const half* b [[buffer(1)]], device half* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=a[i]*b[i]; }
kernel void k_puresub(device const half* a [[buffer(0)]], device const half* b [[buffer(1)]], device half* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=a[i]-b[i]; }
kernel void k_purefma(device const half* a [[buffer(0)]], device const half* b [[buffer(1)]], device const half* c [[buffer(3)]], device half* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=fma(a[i],b[i],c[i]); }
kernel void k_pureaddsat(device const half* a [[buffer(0)]], device const half* b [[buffer(1)]], device half* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=saturate(a[i]+b[i]); }
kernel void k_puremax(device const half* a [[buffer(0)]], device const half* b [[buffer(1)]], device half* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=max(a[i],b[i]); }
kernel void k_pureneg(device const half* a [[buffer(0)]], device const half* b [[buffer(1)]], device half* o [[buffer(2)]], uint i [[thread_position_in_grid]]) { o[i]=(-a[i])+b[i]; }
