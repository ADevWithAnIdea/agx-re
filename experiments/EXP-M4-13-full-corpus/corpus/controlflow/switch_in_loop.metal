#include <metal_stdlib>
using namespace metal;
kernel void k(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], device const int* n[[buffer(2)]], uint i[[thread_position_in_grid]]){
    int cnt=n[i]; int s=0; int j=0; bool stop=false;
    for(j=0;j<cnt && !stop;j++){
        switch(a[j]&3){
            case 0: s+=1; break;
            case 1: s-=1; continue;
            case 2: s*=2; break;
            default: stop=true; continue;
        }
        s+=a[j];
    }
    o[i]=s+j;
}
