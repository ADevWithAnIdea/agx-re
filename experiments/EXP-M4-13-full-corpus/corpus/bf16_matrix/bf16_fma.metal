#include <metal_stdlib>
using namespace metal;
// bfloat fused multiply-add and mad — isolate the bf16 FMA opcode(s).
kernel void kmain(device bfloat* o [[buffer(0)]],
                  device const bfloat* a [[buffer(1)]],
                  device const bfloat* b [[buffer(2)]],
                  device const bfloat* c [[buffer(3)]],
                  uint i [[thread_position_in_grid]]) {
    bfloat x = a[i], y = b[i], z = c[i];
    // NOTE: fma(bfloat,...) has no bfloat overload -> it promotes to float; cast back.
    bfloat r0 = bfloat(fma(x, y, z));
    bfloat r1 = x * y + z;      // operator*/+ DO have bfloat overloads (mad-shaped)
    o[i] = r0 + r1;
}
