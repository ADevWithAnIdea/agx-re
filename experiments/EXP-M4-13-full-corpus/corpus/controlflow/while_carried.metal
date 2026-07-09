#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    uint v=a[i]; uint steps=0;
    while(v!=1u && steps<1000u){ v = (v&1u)? (3u*v+1u) : (v>>1u); steps++; }
    o[i]=steps;
}
