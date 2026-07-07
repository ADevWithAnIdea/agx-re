// EXP-0035 part 3: CONSUMER that calls a symbol from the dynamic library.
// CLEAN-ROOM: OUR OWN MSL. dl_scale is declared extern [[visible]] and resolved
// from the linked MTLDynamicLibrary at pipeline build.
#include <metal_stdlib>
using namespace metal;

// External symbol provided by the dynamic library (declared, not defined here).
[[visible]] float dl_scale(float a, float b);

kernel void use_dylib(device const float*A[[buffer(0)]],device const float*B[[buffer(1)]],
                      device float*O[[buffer(2)]],uint i[[thread_position_in_grid]]){
  O[i] = dl_scale(A[i], B[i]);
}
