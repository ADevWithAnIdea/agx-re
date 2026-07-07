#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o [[buffer(0)]], uint gid [[thread_position_in_grid]], uint v [[simd_lane_id]]){ o[gid]=v; }
