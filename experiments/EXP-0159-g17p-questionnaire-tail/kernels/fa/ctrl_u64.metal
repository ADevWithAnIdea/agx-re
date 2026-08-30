#include <metal_stdlib>
using namespace metal;
kernel void k(device ulong* o [[buffer(0)]], device const ulong* a [[buffer(1)]]) { o[0] = a[0] + a[1]; }
