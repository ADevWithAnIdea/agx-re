#include <metal_stdlib>
using namespace metal;
kernel void k(device half* o[[buffer(0)]], device const half* a[[buffer(1)]],
              device const uint* lane[[buffer(2)]], uint i[[thread_position_in_grid]]){
    half v=a[i];
    ushort L=(ushort)(lane[i] & 31u);
    o[i]    = simd_shuffle(v, L);              // 16-bit shuffle datum
    o[i+1u] = simd_broadcast(v, 0);
}
