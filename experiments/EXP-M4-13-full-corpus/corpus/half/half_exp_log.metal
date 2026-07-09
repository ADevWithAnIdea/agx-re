// OWN-SHADER. Isolate half exp/log family (exp2/log2 hardware primitives on fp16).
#include <metal_stdlib>
using namespace metal;
kernel void k(device half* o[[buffer(0)]], device const half* a[[buffer(1)]],
              uint i[[thread_position_in_grid]]) {
    half x=a[i];
    half r0 = exp2(x);   // native fp16 exp2
    half r1 = log2(x);   // native fp16 log2
    half r2 = exp(x);    // exp = exp2(x*log2e) lowering
    half r3 = log(x);    // log = log2(x)*ln2 lowering
    half r4 = exp10(x);
    half r5 = log10(x);
    o[i] = r0 + r1 + r2 + r3 + r4 + r5;
}
