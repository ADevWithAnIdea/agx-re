#include <metal_stdlib>
using namespace metal;
kernel void m(device int4* o[[buffer(0)]],device const int4* a[[buffer(1)]],device const int4* b[[buffer(2)]],uint i[[thread_position_in_grid]]){
  int4 x=a[i],y=b[i];
  int4 r;
  r.x=max(x.x,y.x); r.y=max(x.y,y.y); r.z=max(x.z,y.z); r.w=max(x.w,y.w);
  o[i]=r;
}
