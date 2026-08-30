// k_srwide.metal -- EXP-0172 WIDE / POSITION-IN-GRID special-register carrier.
// OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// WHY.  db.json says `get_sr.form` (byte0 bit3) is "a datapath/width modifier
// (set for the position-in-grid SR family) that does not change the SR select".
// EXP-0140 swept it at 2 values on ONE carrier and nothing moved, and EXP-0164
// withheld it for exactly that reason.  If the field really is a datapath WIDTH
// selector, the dimension it controls is the WIDTH of the special register being
// read -- so a null on a carrier that reads only one width proves nothing.
//
// This carrier reads only the MULTI-COMPONENT (uint3) SR family: position in
// grid, position in threadgroup, grid/threadgroup extents and threadgroup
// indices, every component consumed separately so any one component landing
// wrong changes the read-back.  Its sibling k_srnarrow.metal reads only SCALAR
// SRs.  The pair is the controlled comparison `form` needs.
#include <metal_stdlib>
using namespace metal;

kernel void k_simd(device uint *out              [[buffer(0)]],
                   device const uint *in         [[buffer(1)]],
                   uint3 gpos [[thread_position_in_grid]],
                   uint3 tpos [[thread_position_in_threadgroup]],
                   uint3 gsz  [[threads_per_grid]],
                   uint3 tgsz [[threads_per_threadgroup]],
                   uint3 tgid [[threadgroup_position_in_grid]],
                   uint3 ngrp [[threadgroups_per_grid]],
                   uint  lane [[thread_index_in_simdgroup]])
{
    uint u = in[gpos.x & 31u];

    device uint *o = out + lane * 16u;
    o[0]  = gpos.x;  o[1]  = gpos.y;  o[2]  = gpos.z;
    o[3]  = tpos.x;  o[4]  = tpos.y;  o[5]  = tpos.z;
    o[6]  = gsz.x;   o[7]  = gsz.y;   o[8]  = gsz.z;
    o[9]  = tgsz.x;  o[10] = tgsz.y;  o[11] = tgsz.z;
    o[12] = tgid.x + 1000u * ngrp.x;
    o[13] = tgid.y + 1000u * ngrp.y;
    o[14] = u ^ (gpos.x * 31u + tpos.y * 7u + gsz.z * 11u + tgsz.x * 13u);
    o[15] = gpos.x + gsz.x + tgsz.z + ngrp.z;
}
