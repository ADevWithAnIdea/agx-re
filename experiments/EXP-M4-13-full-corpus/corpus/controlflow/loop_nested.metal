#include <metal_stdlib>
using namespace metal;
kernel void k(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], device const int* n[[buffer(2)]], uint i[[thread_position_in_grid]]){
    int cnt=n[i]; int found=-1;
    for(int j=0;j<cnt && found<0;j++){
        for(int k=0;k<cnt;k++){
            if(a[j]==a[k]+1){ found=j*100+k; break; }
        }
    }
    o[i]=found;
}
