#include <metal_stdlib>
using namespace metal;
// bfloat4 packed vector arithmetic — do lanes pack into bf16 vector ops?
kernel void kmain(device bfloat4* o [[buffer(0)]],
                  device const bfloat4* a [[buffer(1)]],
                  device const bfloat4* b [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    bfloat4 x = a[i], y = b[i];
    bfloat4 r = x * y + (x - y);
    // fma has no bfloat4 overload at all -> widen to float4, fma, narrow back to bf16x4
    r = bfloat4(fma(float4(x), float4(y), float4(r)));
    o[i] = r;
}
