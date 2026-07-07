// EXP-0035 part 3: the DYNAMIC LIBRARY provider (separately compiled unit).
// CLEAN-ROOM: OUR OWN MSL. Exports [[visible]] symbols for a consumer to call.
#include <metal_stdlib>
using namespace metal;

[[visible]] float dl_scale(float a, float b) { return a * b + 0.5f; }
