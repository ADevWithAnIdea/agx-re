#include <metal_stdlib>
using namespace metal;

// Authored after AMENDMENT-01. These kernels nominate lifecycle bits only;
// their instruction bytes are never copied into the generated recipe.

kernel void add_dead(device const uint *in [[buffer(0)]],
                     device uint *out [[buffer(1)]])
{
    uint a = in[0];
    uint b = in[1];
    uint c = a + b;
    out[0] = c;
    out[1] = c + 17u;
    out[2] = c ^ 0x5a5a5a5au;
}

kernel void add_live(device const uint *in [[buffer(0)]],
                     device uint *out [[buffer(1)]])
{
    uint a = in[0];
    uint b = in[1];
    uint c = a + b;
    out[0] = c;
    out[1] = a + 17u;
    out[2] = b ^ 0x5a5a5a5au;
}

kernel void sub_live(device const uint *in [[buffer(0)]],
                     device uint *out [[buffer(1)]])
{
    uint a = in[0];
    uint b = in[1];
    uint c = a - b;
    out[0] = c;
    out[1] = a + 17u;
    out[2] = b ^ 0x5a5a5a5au;
}
