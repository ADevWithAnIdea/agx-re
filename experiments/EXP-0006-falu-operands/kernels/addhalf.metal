// Half-precision (16-bit) two-source add, to expose the 32/16-bit selection in
// the operand encoding vs the 32-bit add. CLEAN-ROOM: our own MSL.
kernel void k(device half* a [[buffer(0)]],
              device half* b [[buffer(1)]],
              device half* out [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + b[gid];
}
