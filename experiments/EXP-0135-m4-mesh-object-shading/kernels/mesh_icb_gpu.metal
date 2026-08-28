// EXP-0135 mesh_icb_gpu.metal — GPU-authored (compute-kernel-encoded) ICB mesh
// command probe. Follows EXP-0124's icbw_encode_* pattern exactly (its
// harness/kernels/i_common.metal, ICBContainer struct + argument-buffer-bound
// command_buffer + render_command(icb, idx)) applied to the mesh-specific
// render_command::draw_mesh_threadgroups()/draw_mesh_threads() methods, which
// the public MSL toolchain header (metal_command_buffer) declares gated
// behind __HAVE_RENDER_COMMAND_MESH__ -- whether that gate is open for
// Apple9/M4 is exactly what this kernel's compile result answers empirically
// (PUBLIC header inspection only identified that the method NAME exists in
// the language; whether THIS device's compiler accepts it is established
// here by trying to compile and run it, not by reading Apple source).
//
// Clean-room: OUR OWN MSL only, public runtime compile API + public MSL
// stdlib headers (metal_command_buffer, distributed with the Metal
// developer toolchain as the public shading-language surface, analogous to
// any C++ standard-library header -- not Apple binary introspection).

#include <metal_stdlib>
#include <metal_command_buffer>
using namespace metal;

struct ICBContainer { command_buffer icb; };

// One thread encodes one mesh-threadgroup-draw ICB command. `grid` is the
// caller-supplied threadgroupsPerGrid for that command (object-less mesh
// pipeline is the executing/inherited pipeline state -- inheritPipelineState
// = YES on the CPU side, so no set_pipeline_state() call needed here).
kernel void icbw_encode_mesh(constant ICBContainer &c [[buffer(0)]],
                              constant uint3 &grid [[buffer(1)]],
                              uint idx [[thread_position_in_grid]]) {
    render_command cmd(c.icb, idx);
    cmd.draw_mesh_threadgroups(grid, uint3(1, 1, 1), uint3(3, 1, 1));
}
