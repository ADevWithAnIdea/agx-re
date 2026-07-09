#include <metal_stdlib>
using namespace metal;
// tile kernel: per-sample imageblock read/average/write (custom MSAA resolve)
struct IBc { half4 color [[color(0)]]; };
kernel void tMain(imageblock<IBc, imageblock_layout_implicit> img,
                  ushort2 tpos [[thread_position_in_threadgroup]]) {
    half4 acc = half4(0);
    for (ushort s = 0; s < 4; ++s)
        acc += img.read(tpos, s, imageblock_data_rate::sample).color;
    IBc d; d.color = acc * half(0.25);
    for (ushort s = 0; s < 4; ++s) img.write(d, tpos, s);
}
