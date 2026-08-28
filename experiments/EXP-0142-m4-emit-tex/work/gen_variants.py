import subprocess,sys,os
def gen(n, pre_store, name):
    L=['#include <metal_stdlib>','using namespace metal;',
'kernel void k_sample(texture2d<float, access::sample> t [[texture(0)]],',
'                     device const float *in  [[buffer(0)]],',
'                     device float       *out [[buffer(1)]],',
'                     uint tid [[thread_position_in_grid]])','{',
'    constexpr sampler s(coord::pixel, filter::nearest, address::clamp_to_edge, mip_filter::none);',
'    uint b = tid * 64u;']
    for i in range(n): L.append('    float v%d = in[b+%d];'%(i,i))
    if pre_store:
        for i in range(n): L.append('    out[%d] = v%d;'%(i+1,i))
    L.append('    float4 c = t.sample(s, float2(in[b+62], in[b+63]), level(0.0f));')
    L.append('    out[0] = c.x;')
    for i in range(n): L.append('    out[%d] = v%d;'%(n+1+i,i))
    L.append('    out[%d] = c.y; out[%d] = c.z; out[%d] = c.w;'%(2*n+1,2*n+2,2*n+3))
    L.append('}')
    open(name,'w').write('\n'.join(L)+'\n')
for n in (0,2,4,8,12,16,20,24,28,32):
    gen(n, True, 'v_n%d.metal'%n)
