#include <metal_stdlib>
using namespace metal;
vertex float4 v_main(uint bv [[base_vertex]]) {
    return float4(float(bv), 0.0, 0.0, 1.0);
}
fragment float4 f_main() {
    return float4(1.0, 0.5, 0.25, 1.0);
}
