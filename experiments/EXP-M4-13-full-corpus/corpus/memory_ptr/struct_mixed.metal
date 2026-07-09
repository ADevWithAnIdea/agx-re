#include <metal_stdlib>
using namespace metal;
// Mixed-width struct buffer: char/short/int/float/long at interleaved offsets,
// exercising many load widths from one base with immediate byte offsets.
struct Rec {
    char   a;
    short  b;
    int    c;
    float  d;
    long   e;
    uchar  f;
};
kernel void k(device const Rec* in [[buffer(0)]],
              device long* out [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
    Rec r = in[i];
    out[i] = long(r.a) + long(r.b) + long(r.c) + long(r.d) + r.e + long(r.f);
}
