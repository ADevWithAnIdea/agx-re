#include <metal_stdlib>
using namespace metal;
// Attempt a DIRECT out-of-line call via [[noinline]] (no function table). If the
// compiler honours it as a real direct call, we see the direct-call/ret ABI.
__attribute__((noinline)) static uint helper(uint x){ return x * 3u + 1u; }
kernel void k(device uint* out[[buffer(0)]],
              device const uint* a[[buffer(1)]],
              uint gid[[thread_position_in_grid]]){
    out[gid] = helper(a[gid]);
}
