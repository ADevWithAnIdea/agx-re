// EXP-M5-09: force an out-of-line CALL via a visible_function_table (call ABI 0xef/0xff).
// A [[visible]] function invoked through a visible_function_table cannot be inlined, so the
// compiler must emit the real call/return sequence. CLEAN-ROOM: OUR OWN MSL.
#include <metal_stdlib>
using namespace metal;

// callee is visible => not inlinable when reached indirectly.
[[visible]] uint addk(device const uint *a, uint i) { return a[i] * 3u + 7u; }

kernel void k(device const uint *a [[buffer(0)]],
              device uint *out [[buffer(1)]],
              visible_function_table<uint(device const uint *, uint)> vft [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = vft[0](a, gid);
}
