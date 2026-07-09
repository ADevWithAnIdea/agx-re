#include <metal_stdlib>
using namespace metal;
// select() with an explicitly-computed bool condition (decouples the compare
// from the select), a per-lane float4 select (vector condition), and a select
// driven by a float classification. Surfaces the pure conditional-move / bitwise
// select opcode distinct from fused compare-select.
kernel void k_select(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                     device const float* b[[buffer(2)]], device const float* c[[buffer(3)]],
                     uint i[[thread_position_in_grid]]) {
    o[i] = select(a[i], b[i], c[i] > 0.0f);
}
kernel void k_select_v4(device float4* o[[buffer(0)]], device const float4* a[[buffer(1)]],
                        device const float4* b[[buffer(2)]], device const float4* c[[buffer(3)]],
                        uint i[[thread_position_in_grid]]) {
    o[i] = select(a[i], b[i], c[i] > float4(0.0f));   // per-lane vector condition
}
kernel void k_select_chain(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                           device const float* b[[buffer(2)]], device const float* c[[buffer(3)]],
                           uint i[[thread_position_in_grid]]) {
    bool p = a[i] > b[i];
    bool q = b[i] > c[i];
    o[i] = (p && q) ? a[i] : (p ? b[i] : c[i]);   // nested selects + bool AND
}
