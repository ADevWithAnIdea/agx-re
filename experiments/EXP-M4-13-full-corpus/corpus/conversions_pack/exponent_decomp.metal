// conversions_pack: exponent/mantissa decomposition ops (rgb9e5-style building blocks).
// Isolates frexp, ldexp, modf, ilogb — exponent extraction / scale converts.
// (logb is not an MSL intrinsic — see pack_r11g11b10/rgb9e5 negatives.)
#include <metal_stdlib>
using namespace metal;
kernel void exponent_decomp(device float* o [[buffer(0)]],
                            device const float* fa [[buffer(1)]],
                            uint i [[thread_position_in_grid]]) {
    float f = fa[i];
    int ex;
    float m  = frexp(f, ex);     // split mantissa [0.5,1) and exponent
    float lg = ldexp(m, ex + 1); // reconstruct m * 2^(ex+1)
    int   il = ilogb(f);         // integer exponent
    float ip;
    float fp = modf(f, ip);      // integer / fractional split
    o[i] = m + lg + float(il) + fp + ip;
}
