#include <metal_stdlib>
using namespace metal;
struct S { double d; float f; };
kernel void k(device S* o [[buffer(0)]], device const S* a [[buffer(1)]]) { o[0].d = a[0].d + 1.0; o[0].f = a[0].f; }
