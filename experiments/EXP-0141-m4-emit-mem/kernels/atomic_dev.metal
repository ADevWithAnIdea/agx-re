// EXP-0141 device-atomic splice carrier. OWN MSL.
// Four independently-loaded values v0..v3 are all live ACROSS the atomic, so
// that a byte which selects the RMW operand register can be detected by which
// of a[0..3] lands in the counter. a[j] = 1000*j + 7 makes the four candidates
// mutually distinguishable and distinguishable from 0 and from any small
// register/descriptor value.
// dbg[3] is an INTEGRITY SENTINEL written first and unconditionally: under
// concurrent sibling GPU work a command buffer can report STATUS OK having
// executed nothing, and an all-zero readback is otherwise indistinguishable
// from a genuine silent zero (AMENDMENT 1).
#include <metal_stdlib>
using namespace metal;
kernel void k(device atomic_uint* o   [[buffer(0)]],
              device const uint* a    [[buffer(1)]],
              device uint* dbg        [[buffer(2)]],
              uint tid [[thread_position_in_grid]])
{
    dbg[3] = 0xA5A5A5A5u;
    uint v0 = a[0];
    uint v1 = a[1];
    uint v2 = a[2];
    uint v3 = a[3];
    atomic_fetch_add_explicit(o, v0, memory_order_relaxed);
    dbg[0] = v1;
    dbg[1] = v2;
    dbg[2] = v3;
}
