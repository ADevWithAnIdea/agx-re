// conversions_pack: saturating conversions (clamp-then-narrow) and metal::saturate.
// Isolates any convert-with-clamp / saturate modifier vs plain truncating convert.
#include <metal_stdlib>
using namespace metal;
kernel void cvt_saturate(device int* o [[buffer(0)]],
                         device const float* fa [[buffer(1)]],
                         uint i [[thread_position_in_grid]]) {
    float f = fa[i];
    float s = saturate(f);                        // clamp f32 to [0,1]
    uchar  a = uchar(clamp(f, 0.0f, 255.0f));     // saturating -> u8
    char   b = char(clamp(f, -128.0f, 127.0f));   // saturating -> i8
    ushort c = ushort(clamp(f, 0.0f, 65535.0f));  // saturating -> u16
    o[i] = as_type<int>(s) + int(a) + int(b) + int(c);
}
