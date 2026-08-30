// k_sin.metal -- EXP-0199 SFU carrier: fast::sin over a per-lane argument that
// spans BOTH the small-argument range (|x| <= pi/2) and the range-reduced range
// (|x| > pi/2), because EXP-0146/0157 showed sfu_marker byte+0 flips the SIGN
// only on range-reduced rows.  OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// out[i] = fast::sin(a[i] as float bits)  -- the host supplies the arguments,
// so the oracle varies per lane.

#include <metal_stdlib>
using namespace metal;

kernel void k_sin(device const float *a [[buffer(1)]],
                  device float       *o [[buffer(0)]],
                  uint                i [[thread_position_in_grid]])
{
    o[i] = fast::sin(a[i]);
}
