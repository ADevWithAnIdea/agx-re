#include <metal_stdlib>
#include <metal_command_buffer>
using namespace metal;

struct ICBContainerC { command_buffer icb; };

kernel void encode_compute_barrier(constant ICBContainerC &c [[buffer(0)]],
                                    device const float4 *colors [[buffer(1)]],
                                    uint idx [[thread_position_in_grid]])
{
    compute_command cmd(c.icb, idx);
    cmd.set_kernel_buffer(colors, 1);
    cmd.set_barrier();
    cmd.clear_barrier();
    cmd.concurrent_dispatch_threadgroups(uint3(1,1,1), uint3(4,1,1));
}
