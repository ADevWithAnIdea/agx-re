#include <metal_stdlib>
using namespace metal;
// tile shader (kernel run per-tile in a render pass) that reads/writes the
// imageblock and uses threadgroup memory -> threadgroup-imageblock path
struct IB { half4 color [[color(0)]]; };
kernel void tMain(imageblock<IB, imageblock_layout_implicit> img,
                  ushort2 tpos [[thread_position_in_threadgroup]],
                  ushort2 gsz  [[threads_per_threadgroup]],
                  threadgroup float* scratch [[threadgroup(0)]]) {
    IB d = img.read(tpos);
    uint idx = tpos.y * gsz.x + tpos.x;
    scratch[idx] = d.color.x;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    float s = scratch[idx] + scratch[(idx+1) % (gsz.x*gsz.y)];
    d.color = half4(half(s), d.color.y, d.color.z, 1.0h);
    img.write(d, tpos);
}
