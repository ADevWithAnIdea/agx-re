#include <metal_stdlib>
#include <metal_logging>
using namespace metal;
kernel void k(device uint* o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
  o[i] = i;
  os_log_default.log_info("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA%u", i);
}
