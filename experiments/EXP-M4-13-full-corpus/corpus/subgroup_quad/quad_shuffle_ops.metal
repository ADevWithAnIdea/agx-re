#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]],
              device const uint* lane[[buffer(2)]], uint i[[thread_position_in_grid]]){
    uint v=a[i];
    ushort L=(ushort)(lane[i] & 3u);
    o[i]    = quad_broadcast(v, 1);            // constant quad lane
    o[i+1u] = quad_shuffle(v, L);              // dynamic quad shuffle
    o[i+2u] = quad_shuffle_up(v, 1);
    o[i+3u] = quad_shuffle_down(v, 1);
    o[i+4u] = quad_shuffle_xor(v, 2);
}
