#include <metal_stdlib>
#include <metal_command_buffer>
using namespace metal;
// GPU-side encoding of a compute dispatch into an indirect command buffer
// (compute_command), ICB handle delivered via an argument-buffer container.
struct ICBContainer { command_buffer cmd [[id(0)]]; };
kernel void k(device ICBContainer& icbc [[buffer(0)]],
              device const uint* args [[buffer(1)]],
              device float* payload [[buffer(2)]],
              uint i [[thread_position_in_grid]]) {
    compute_command c(icbc.cmd, i);
    c.set_kernel_buffer(payload, 0);
    c.concurrent_dispatch_threadgroups(uint3(args[i], 1, 1), uint3(64, 1, 1));
}
