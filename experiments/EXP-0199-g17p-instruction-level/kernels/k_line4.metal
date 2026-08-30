// k_line4.metal -- EXP-0199 straight-line compute carrier, SLACK VARIANT 4.
// Identical in shape to k_line.metal (same sentinel-first structure, same
// varying per-lane oracle); the extra arithmetic exists ONLY to change the
// compiled length modulo the container's 8-byte alignment, so that the tail of
// _agc.main is followed by FOUR zero pad bytes instead of two.  That is what
// makes a FOUR-byte insertion possible without touching container metadata --
// required to test whether a 0x60-leader instruction is 2 or 4 bytes on the
// hardware.  OUR OWN MSL.  Clean-room: OWN-SHADER.
//
//   o[i]      = f(a[i], i)   (per-lane distinct)
//   o[64 + i] = 0xA5A50000 + i   (sentinel, stored first)

#include <metal_stdlib>
using namespace metal;

kernel void k_line4(device const uint *a  [[buffer(1)]],
                    device uint       *o  [[buffer(0)]],
                    uint               i  [[thread_position_in_grid]])
{
    o[i + 64u] = 0xA5A50000u + i;
    uint v = a[i] * 3u;
    v += i * 7u;
    v += 11u;
    v = v * 5u;
    o[i] = v;
}
