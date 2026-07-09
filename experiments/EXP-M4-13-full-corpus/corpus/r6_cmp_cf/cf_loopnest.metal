#include <metal_stdlib>
using namespace metal;
kernel void L1(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], device const int* n[[buffer(2)]], uint i[[thread_position_in_grid]]){
    int c=n[i]; int s=0;
    for(int j=0;j<c;j++){ s+=a[j]; }
    o[i]=s;
}
kernel void L2(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], device const int* n[[buffer(2)]], uint i[[thread_position_in_grid]]){
    int c=n[i]; int s=0;
    for(int j=0;j<c;j++){ for(int k=0;k<c;k++){ s+=a[j]*a[k]; } }
    o[i]=s;
}
kernel void L3(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], device const int* n[[buffer(2)]], uint i[[thread_position_in_grid]]){
    int c=n[i]; int s=0;
    for(int j=0;j<c;j++){ for(int k=0;k<c;k++){ for(int m=0;m<c;m++){ s+=a[j]*a[k]*a[m]; } } }
    o[i]=s;
}
