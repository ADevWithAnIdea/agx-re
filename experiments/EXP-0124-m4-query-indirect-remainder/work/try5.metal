#include <metal_stdlib>
#include <metal_command_buffer>
using namespace metal;

struct ICBContainerC {
    command_buffer icb;
    compute_pipeline_state prodPSO;
    compute_pipeline_state consPSO;
};

kernel void icbb_encode2(constant ICBContainerC &c [[buffer(0)]],
                          device uint *slot [[buffer(1)]],
                          device uint *result [[buffer(2)]],
                          constant uint &useBarrier [[buffer(3)]],
                          uint idx [[thread_position_in_grid]])
{
    if (idx == 0) {
        compute_command cmd(c.icb, 0);
        cmd.set_compute_pipeline_state(c.prodPSO);
        cmd.set_kernel_buffer(slot, 0);
        cmd.concurrent_dispatch_threadgroups(uint3(1,1,1), uint3(1,1,1));
    } else {
        compute_command cmd(c.icb, 1);
        cmd.set_compute_pipeline_state(c.consPSO);
        if (useBarrier != 0) cmd.set_barrier();
        cmd.set_kernel_buffer(slot, 0);
        cmd.set_kernel_buffer(result, 1);
        cmd.concurrent_dispatch_threadgroups(uint3(1,1,1), uint3(1,1,1));
    }
}
