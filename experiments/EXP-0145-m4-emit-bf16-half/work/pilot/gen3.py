import sys,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from lib import *
K=os.path.join(EXP,'work','pilot','k')
HDR="#include <metal_stdlib>\nusing namespace metal;\n"
CAR={
 'h4add': "kernel void k(device half4* out [[buffer(0)]], device const half4* a [[buffer(1)]], device const half4* b [[buffer(2)]], uint g [[thread_position_in_grid]]){ out[g]=a[g]+b[g]; }",
 'packh2':"kernel void k(device uint* out [[buffer(0)]], device const float2* a [[buffer(1)]], uint g [[thread_position_in_grid]]){ half2 h=half2(a[g]); out[g]=as_type<uint>(h); }",
 'pack2x':"kernel void k(device uint2* out [[buffer(0)]], device const float4* a [[buffer(1)]], uint g [[thread_position_in_grid]]){ float4 v=a[g]; half2 lo=half2(v.xy)+half2(1.0h); half2 hi=half2(v.zw)*half2(2.0h); out[g]=uint2(as_type<uint>(lo),as_type<uint>(hi)); }",
 'h2mulpk':"kernel void k(device uint* out [[buffer(0)]], device const half2* a [[buffer(1)]], device const half2* b [[buffer(2)]], uint g [[thread_position_in_grid]]){ half2 s=a[g]*b[g]; out[g]=as_type<uint>(s); }",
}
for name,body in CAR.items():
    src=os.path.join(K,name+'.metal'); open(src,'w').write(HDR+body+"\n")
    try:
        compile_carrier(src,os.path.join(K,name+'.bin'))
        _,_,main=load_base(os.path.join(K,name+'.bin'))
        print('='*72); print(name,'len',len(main)); show(main)
    except Exception as e:
        print('='*72); print(name,'FAILED',str(e)[:200])
