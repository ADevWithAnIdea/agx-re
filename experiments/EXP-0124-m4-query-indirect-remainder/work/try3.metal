#include <metal_stdlib>
#include <metal_command_buffer>
using namespace metal;

struct ICBContainer { command_buffer icb; };

kernel void encode_reset(constant ICBContainer &c [[buffer(0)]],
                          uint idx [[thread_position_in_grid]])
{
    render_command cmd(c.icb, idx);
    cmd.reset();
}

kernel void encode_indexed(constant ICBContainer &c [[buffer(0)]],
                            device const float4 *colors [[buffer(1)]],
                            device const uint  *indices [[buffer(2)]],
                            uint idx [[thread_position_in_grid]])
{
    render_command cmd(c.icb, idx);
    cmd.set_vertex_buffer(colors, 1);
    cmd.draw_indexed_primitives(primitive_type::triangle, 3, indices, 1, 0, 0);
}

kernel void encode_fields(constant ICBContainer &c [[buffer(0)]],
                           device const float4 *colors [[buffer(1)]],
                           device const uint4  *argsBuf [[buffer(2)]],
                           uint idx [[thread_position_in_grid]])
{
    render_command cmd(c.icb, idx);
    cmd.set_vertex_buffer(colors, 1);
    uint4 a = argsBuf[idx];
    // vertexStart, vertexCount, instanceCount, baseInstance
    cmd.draw_primitives(primitive_type::triangle, a.x, a.y, a.z, a.w);
}

struct ICBContainerC { command_buffer icb; };

kernel void encode_compute(constant ICBContainerC &c [[buffer(0)]],
                            uint idx [[thread_position_in_grid]])
{
    compute_command cmd(c.icb, idx);
    cmd.concurrent_dispatch_threadgroups(uint3(1,1,1), uint3(1,1,1));
}
