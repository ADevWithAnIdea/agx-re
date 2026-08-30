// EXP-0159 FB carrier. Authored by the clean-room RE team.
// One 64-bit register-pair arithmetic instruction, nothing else: EXP-0146 (M4)
// showed this shape compiles to get_sr, device_load, device_load, iadd2,
// device_store, stop. We re-compile and re-locate it on G17P here.
#include <metal_stdlib>
using namespace metal;
kernel void k(device ulong* out [[buffer(0)]],
              device const ulong* a [[buffer(1)]],
              device const ulong* b [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
  out[gid] = a[gid] - b[gid];
}
