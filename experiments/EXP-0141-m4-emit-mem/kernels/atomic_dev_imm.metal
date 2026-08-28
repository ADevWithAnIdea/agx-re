// EXP-0141 device-atomic (immediate/ALU-operand form) splice carrier. OWN MSL.
// The literal operand selects db.json's `atomic_rmw` (byte+1 == 0x11) form.
#include <metal_stdlib>
using namespace metal;
kernel void k(device atomic_uint* o   [[buffer(0)]],
              device const uint* a    [[buffer(1)]],
              device uint* dbg        [[buffer(2)]],
              uint tid [[thread_position_in_grid]])
{
    uint v0 = a[0];
    uint v1 = a[1];
    uint v2 = a[2];
    uint v3 = a[3];
    atomic_fetch_add_explicit(o, 5000u, memory_order_relaxed);
    dbg[0] = v0; dbg[1] = v1; dbg[2] = v2; dbg[3] = v3;
}
