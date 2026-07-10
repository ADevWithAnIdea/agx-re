#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    simd_vote v=simd_active_threads_mask();
    o[i]=(uint)((simd_vote::vote_t)v);
}
