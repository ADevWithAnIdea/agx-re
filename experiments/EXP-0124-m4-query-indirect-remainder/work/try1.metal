#include <metal_stdlib>
#include <metal_command_buffer>
using namespace metal;

kernel void encode_render(command_buffer cmd_buf [[buffer(0)]],
                           device const float4 *colors [[buffer(1)]],
                           uint idx [[thread_position_in_grid]])
{
    render_command cmd(cmd_buf, idx);
    cmd.set_vertex_buffer(colors, 1);
    cmd.draw_primitives(primitive_type::triangle, 0, 3, 1, 0);
}
