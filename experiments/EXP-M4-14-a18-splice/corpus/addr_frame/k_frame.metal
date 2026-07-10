#include <metal_stdlib>
using namespace metal;
// non-inlined visible callee that itself calls another -> non-leaf frame
__attribute__((visible)) float leafmul(float x, float y) { return x * y; }
__attribute__((visible)) float nonleaf(float x, float y) {
    float t = leafmul(x, y);        // inner CALL -> clobbers link reg
    return t + leafmul(y, x);       // second inner CALL
}
kernel void k(device const float* a [[buffer(0)]],
              device const float* b [[buffer(1)]],
              device float* o [[buffer(2)]],
              uint i [[thread_position_in_grid]]) {
    o[i] = nonleaf(a[i], b[i]);
}
