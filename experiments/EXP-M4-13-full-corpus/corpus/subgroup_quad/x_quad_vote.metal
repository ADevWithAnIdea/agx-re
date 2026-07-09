#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    bool p = a[i] > 10u;
    o[i]    = quad_all(p) ? 1u : 0u;
    o[i+1u] = quad_any(p) ? 1u : 0u;
    quad_vote vb = quad_ballot(p);
    ulong mb = (ulong)(quad_vote::vote_t)vb;
    o[i+2u] = (uint)mb;
}
