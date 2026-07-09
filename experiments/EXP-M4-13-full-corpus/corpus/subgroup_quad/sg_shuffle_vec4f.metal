#include <metal_stdlib>
using namespace metal;
kernel void k(device float4* o[[buffer(0)]], device const float4* a[[buffer(1)]],
              device const uint* lane[[buffer(2)]], uint i[[thread_position_in_grid]]){
    float4 v=a[i];
    ushort L=(ushort)(lane[i] & 31u);
    o[i] = simd_shuffle(v, L);                 // vector datum -> 4x lowered shuffles
}
