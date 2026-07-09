#include <metal_stdlib>
using namespace metal;
// force lots of live integer address/index math (like std140 uniform->storage copies)
struct U { uint4 a[8]; };
kernel void k(device uint* out [[buffer(0)]],
              constant U& u [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    uint i0=u.a[0].x+tid, i1=u.a[1].y*3u+i0, i2=u.a[2].z+i1*7u, i3=u.a[3].w+i2;
    uint i4=i0+i1, i5=i2+i3, i6=i4*i5+i0, i7=i5*i6+i1;
    uint i8=i6+i7*2u, i9=i7+i8*4u, ia=i8+i9, ib=i9*i8+i7;
    uint ic=ia+ib*5u, id=ib+ic, ie=ic*id+ia, ig=id+ie*9u;
    out[i0]=i1; out[i2]=i3; out[i4]=i5; out[i6]=i7;
    out[i8]=i9; out[ia]=ib; out[ic]=id; out[ie]=ig;
    out[i1+ie]=i0^ib; out[i3^ic]=i5+id;
}
