#include <metal_stdlib>
using namespace metal;
kernel void k(device ulong* o [[buffer(0)]], device const ulong* a [[buffer(1)]]) {
  double x = as_type<double>(a[0]); double y = as_type<double>(a[1]); o[0] = as_type<ulong>(x + y); }
