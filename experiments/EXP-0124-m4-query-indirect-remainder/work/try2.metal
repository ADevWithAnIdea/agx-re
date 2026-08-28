#include <metal_stdlib>
#include <metal_command_buffer>
using namespace metal;

struct ICBContainer {
    command_buffer icb;
};

kernel void encode_render(constant ICBContainer &icb_container [[buffer(0)]],
                           device const float4 *colors [[buffer(1)]],
                           uint idx [[thread_position_in_grid]])
{
    render_command cmd(icb_container.icb, idx);
    cmd.set_vertex_buffer(colors, 1);
    cmd.draw_primitives(primitive_type::triangle, 0, 3, 1, 0);
}
