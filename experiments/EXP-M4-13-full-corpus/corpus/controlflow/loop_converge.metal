#include <metal_stdlib>
using namespace metal;
kernel void k(device float* o[[buffer(0)]], device const float* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    float x=a[i]; float prev=0.0f; int it=0;
    for(it=0; it<50; it++){ prev=x; x=0.5f*(x + a[i]/max(x,1e-6f)); if(fabs(x-prev)<1e-5f) break; }
    o[i]=x + float(it);
}
