#include <metal_stdlib>
#include <metal_logging>
using namespace metal;
kernel void k(device uint* o [[buffer(0)]], uint i [[thread_position_in_grid]]) {
  o[i] = i + 0x51ab0000u;
  if (i & 1u) os_log_default.log_info("ODD i=%u m=0x%08x", i, 0x51abcdefu);
  else        os_log_default.log_info("EVEN i=%u m=0x%08x g=%u f=%f", i, 0x51abcdefu, 0xdd00u+i, float(i)+0.25f);
}
