#include <metal_stdlib>
using namespace metal;
static uint p1by1(uint x){ x&=0x0000ffffu; x=(x|(x<<8))&0x00ff00ffu; x=(x|(x<<4))&0x0f0f0f0fu; x=(x|(x<<2))&0x33333333u; x=(x|(x<<1))&0x55555555u; return x; }
kernel void k(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]], device const uint* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=p1by1(a[i])|(p1by1(b[i])<<1); }
