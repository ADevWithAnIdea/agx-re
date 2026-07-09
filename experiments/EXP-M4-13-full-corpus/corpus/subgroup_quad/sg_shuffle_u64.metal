#include <metal_stdlib>
using namespace metal;
kernel void k(device ulong* o[[buffer(0)]], device const ulong* a[[buffer(1)]],
              device const uint* lane[[buffer(2)]], uint i[[thread_position_in_grid]]){
    ulong v=a[i];
    ushort L=(ushort)(lane[i] & 31u);
    o[i]    = simd_shuffle(v, L);              // 64-bit lowering (hi/lo shuffles)
    o[i+1u] = simd_broadcast(v, 5);
}
