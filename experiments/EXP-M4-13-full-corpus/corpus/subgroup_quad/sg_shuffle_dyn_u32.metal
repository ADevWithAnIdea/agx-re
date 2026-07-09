#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]],
              device const uint* lane[[buffer(2)]], uint i[[thread_position_in_grid]]){
    uint v=a[i];
    ushort L=(ushort)(lane[i] & 31u);          // runtime lane -> general shuffle
    o[i] = simd_shuffle(v, L);
}
