#include <metal_stdlib>
using namespace metal;
// bfloat scalar add/sub/mul/div — the base bf16 ALU ops.
kernel void kmain(device bfloat* o [[buffer(0)]],
                  device const bfloat* a [[buffer(1)]],
                  device const bfloat* b [[buffer(2)]],
                  uint i [[thread_position_in_grid]]) {
    bfloat x = a[i];
    bfloat y = b[i];
    bfloat s = x + y;
    bfloat d = x - y;
    bfloat p = x * y;
    bfloat q = x / (y + bfloat(1.0));
    o[i] = ((s + d) * p) - q;
}
