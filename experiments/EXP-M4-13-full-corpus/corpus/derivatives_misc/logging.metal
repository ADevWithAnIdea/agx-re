#include <metal_stdlib>
#include <metal_logging>
using namespace metal;
// EXTRAPOLATE (probe): in-shader logging via Metal shader logging (os_log).
// If the compiler accepts os_log in a shader, the HW/driver exposes a logging
// store path worth decoding. A compile failure is a first-class NEGATIVE
// result (feature not exposed via public MSL on this toolchain).
kernel void k(device float* o [[buffer(0)]],
              uint i [[thread_position_in_grid]]) {
    o[i] = float(i) * 0.5f;
    os_log_default.log_info("deriv_misc log %u -> %f", i, o[i]);
}
