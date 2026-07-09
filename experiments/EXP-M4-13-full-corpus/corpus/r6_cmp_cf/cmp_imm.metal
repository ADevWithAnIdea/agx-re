#include <metal_stdlib>
using namespace metal;
// compare a[i] < immediate, real divergent branch. Vary the immediate only.
#define K(NM,C) kernel void NM(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], uint i[[thread_position_in_grid]]){ \
    int acc=0; int v=a[i]; \
    if (v < C) { for(int k=0;k<v;k++) acc += v*k; o[i]=acc; return; } \
    o[i]=7; }
K(lt3,3)
K(lt5,5)
K(lt7,7)
K(lt100,100)
K(lt1000,1000)
// srcA perturbation: compare b[i] (second buffer) instead, forcing a different srcA reg.
kernel void ltB(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], device const int* b[[buffer(2)]], uint i[[thread_position_in_grid]]){
    int acc=0; int u=a[i]; int v=b[i]; (void)u;
    if (v < 5) { for(int k=0;k<v;k++) acc += v*k + u; o[i]=acc; return; }
    o[i]=u;
}
