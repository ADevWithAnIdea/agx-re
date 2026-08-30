// k_srnarrow.metal -- EXP-0172 SCALAR special-register carrier.  OUR OWN MSL.
// Clean-room: OWN-SHADER.
//
// WHY.  The controlled sibling of k_srwide.metal.  Same shape of kernel, same
// output surface, same consumers -- but every special register read here is a
// SCALAR (1-component) SR.  If `get_sr.form` is the datapath/width modifier
// db.json believes it is, flipping it must be observable on at most one of these
// two carriers, and a null on both bounds the claim across the dimension the
// field is supposed to control.  Two carriers identical in that dimension would
// be one carrier (EXP-0164 / iter_at.loc).
#include <metal_stdlib>
using namespace metal;

kernel void k_simd(device uint *out       [[buffer(0)]],
                   device const uint *in  [[buffer(1)]],
                   uint tidg [[thread_position_in_grid]],
                   uint tidt [[thread_index_in_threadgroup]],
                   uint lane [[thread_index_in_simdgroup]],
                   uint sgi  [[simdgroup_index_in_threadgroup]],
                   uint sgn  [[simdgroups_per_threadgroup]],
                   uint tps  [[threads_per_simdgroup]],
                   uint tpt  [[threads_per_threadgroup]])
{
    uint u = in[tidg & 31u];

    device uint *o = out + lane * 16u;
    o[0]  = tidg;  o[1]  = tidt;  o[2]  = lane;  o[3]  = sgi;
    o[4]  = sgn;   o[5]  = tps;   o[6]  = tpt;
    o[7]  = tidg * 3u + tidt;
    o[8]  = lane * 5u + sgi;
    o[9]  = sgn * 7u + tps;
    o[10] = tpt * 11u + lane;
    o[11] = u ^ (tidg * 31u + tidt * 7u + lane * 11u);
    o[12] = u + tps;
    o[13] = u ^ sgn;
    o[14] = tidg + tidt + lane + sgi + sgn + tps + tpt;
    o[15] = (tidg << 8) | (lane << 3) | sgi;
}
