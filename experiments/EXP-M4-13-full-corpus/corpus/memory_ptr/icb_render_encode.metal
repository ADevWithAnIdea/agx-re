#include <metal_stdlib>
#include <metal_command_buffer>
using namespace metal;
// GPU-side encoding into an indirect command buffer (render_command). The ICB
// handle is delivered inside an argument-buffer container struct (the required
// MSL idiom). Exercises command_buffer / render_command address handling.
struct ICBContainer { command_buffer cmd [[id(0)]]; };
struct VParams { uint firstVertex; uint vertexCount; };
kernel void k(device ICBContainer& icbc [[buffer(0)]],
              device const VParams* params [[buffer(1)]],
              device const float* verts [[buffer(2)]],
              uint i [[thread_position_in_grid]]) {
    render_command c(icbc.cmd, i);
    c.set_vertex_buffer(verts, 0);
    c.draw_primitives(primitive_type::triangle,
                      params[i].firstVertex, params[i].vertexCount, 1, 0);
}
