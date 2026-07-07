#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
  o[i] = i;
}
