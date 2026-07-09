// OWN-SHADER. Isolate half4/half3 vector + geometric ops (dot/length/normalize/cross).
#include <metal_stdlib>
using namespace metal;
kernel void k(device half* o[[buffer(0)]], device const half4* a[[buffer(1)]],
              device const half4* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    half4 x=a[i], y=b[i];
    half3 x3 = x.xyz, y3 = y.xyz;
    half r0 = dot(x, y);          // 4-wide half dot -> fma chain
    half r1 = length(x3);         // sqrt(dot)
    half r2 = distance(x3, y3);
    half3 n = normalize(x3);      // rsqrt-based
    half3 c = cross(x3, y3);      // cross product
    half4 s = x*y + x;            // 4-lane packed mad
    o[i] = r0 + r1 + r2 + n.x + c.y + s.w;
}
