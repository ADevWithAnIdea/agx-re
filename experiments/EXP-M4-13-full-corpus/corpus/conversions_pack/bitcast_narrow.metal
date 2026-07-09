// conversions_pack: 16-bit and 8-bit as_type<> bitcasts.
// Isolates half<->ushort, short<->half (16b), char<->uchar (8b) reinterpret.
#include <metal_stdlib>
using namespace metal;
kernel void bitcast_narrow(device ushort* o [[buffer(0)]],
                           device const half* ha [[buffer(1)]],
                           device const short* sa [[buffer(2)]],
                           uint i [[thread_position_in_grid]]) {
    half  h = ha[i];
    short s = sa[i];
    ushort a = as_type<ushort>(h);       // f16 -> u16 reinterpret
    half   b = as_type<half>(s);         // i16 -> f16 reinterpret
    ushort c = as_type<ushort>(s);       // i16 -> u16 reinterpret (trivial)
    uchar  d = as_type<uchar>(char(s));  // i8  -> u8  reinterpret (trivial)
    o[i] = a ^ as_type<ushort>(b) ^ c ^ ushort(d);
}
