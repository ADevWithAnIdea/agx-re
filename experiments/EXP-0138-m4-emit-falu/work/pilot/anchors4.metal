// EXP-0138 pilot anchor probes, round 4: hunting falu_srcmod12b / falu2_ext8b
// / falu2_uni carriers. OWN MSL.
#include <metal_stdlib>
using namespace metal;
kernel void p1(device float* o [[buffer(0)]], device float* a [[buffer(1)]], uint t [[thread_position_in_grid]]) { o[t]=saturate(fabs(a[t])+fabs(a[t+1])); }
kernel void p2(device float* o [[buffer(0)]], device float* a [[buffer(1)]], uint t [[thread_position_in_grid]]) { o[t]=-fabs(a[t])*-fabs(a[t+1]); }
kernel void p3(device float* o [[buffer(0)]], device float* a [[buffer(1)]], uint t [[thread_position_in_grid]]) { o[t]=fabs(a[t]-a[t+1]); }
kernel void p4(device float* o [[buffer(0)]], device float* a [[buffer(1)]], uint t [[thread_position_in_grid]]) { o[t]=saturate(fabs(a[t])-fabs(a[t+1])); }
kernel void p5(device float* o [[buffer(0)]], device float* a [[buffer(1)]], uint t [[thread_position_in_grid]]) { o[t]=clamp(fabs(a[t])+a[t+1],0.0f,1.0f); }
kernel void p6(device float* o [[buffer(0)]], device float* a [[buffer(1)]], constant float& u [[buffer(2)]], uint t [[thread_position_in_grid]]) { o[t]=fabs(a[t])+u; }
kernel void p7(device float* o [[buffer(0)]], device float* a [[buffer(1)]], constant float2& u [[buffer(2)]], uint t [[thread_position_in_grid]]) { o[t]=a[t]*u.x+u.y; }
kernel void p8(device float* o [[buffer(0)]], constant float& u [[buffer(2)]], uint t [[thread_position_in_grid]]) { o[t]=u+u; }
kernel void p9(device float* o [[buffer(0)]], device float* a [[buffer(1)]], uint t [[thread_position_in_grid]]) { o[t]=a[t]*a[t+1]+a[t+2]*a[t+3]; }
kernel void pa(device float* o [[buffer(0)]], device float* a [[buffer(1)]], uint t [[thread_position_in_grid]]) { o[t]=fma(a[t],a[t+1],fabs(a[t+2])); }
kernel void pb(device float* o [[buffer(0)]], device float* a [[buffer(1)]], uint t [[thread_position_in_grid]]) { o[t]=saturate(a[t]*a[t+1]); }
kernel void pc(device float* o [[buffer(0)]], device float* a [[buffer(1)]], uint t [[thread_position_in_grid]]) { o[t]=mix(a[t],a[t+1],a[t+2]); }
kernel void pd(device float* o [[buffer(0)]], device float* a [[buffer(1)]], uint t [[thread_position_in_grid]]) { o[t]=fma(-fabs(a[t]),fabs(a[t+1]),-fabs(a[t+2])); }
