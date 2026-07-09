#include <metal_stdlib>
using namespace metal;
kernel void k(device half* o[[buffer(0)]], device const half* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    half v=a[i];
    o[i]=simd_prefix_inclusive_product(v);
}
