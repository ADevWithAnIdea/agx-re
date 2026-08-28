import sys,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from lib import *
K=os.path.join(EXP,'work','pilot','k')
HDR="#include <metal_stdlib>\nusing namespace metal;\n"
CAR={
 'nh_add':  "kernel void k(device half* out [[buffer(0)]], device const half* a [[buffer(1)]], device const half* b [[buffer(2)]], uint g [[thread_position_in_grid]]){ out[g]=a[g]+b[g]; }",
 'nh_mul':  "kernel void k(device half* out [[buffer(0)]], device const half* a [[buffer(1)]], device const half* b [[buffer(2)]], uint g [[thread_position_in_grid]]){ out[g]=a[g]*b[g]; }",
 'nh2_add': "kernel void k(device half2* out [[buffer(0)]], device const half2* a [[buffer(1)]], device const half2* b [[buffer(2)]], uint g [[thread_position_in_grid]]){ out[g]=a[g]+b[g]; }",
 'nh2_mul': "kernel void k(device half2* out [[buffer(0)]], device const half2* a [[buffer(1)]], device const half2* b [[buffer(2)]], uint g [[thread_position_in_grid]]){ out[g]=a[g]*b[g]; }",
 'nh2_fma': "kernel void k(device half2* out [[buffer(0)]], device const half2* a [[buffer(1)]], device const half2* b [[buffer(2)]], device const half2* c [[buffer(3)]], uint g [[thread_position_in_grid]]){ out[g]=fma(a[g],b[g],c[g]); }",
 'nh_min':  "kernel void k(device half* out [[buffer(0)]], device const half* a [[buffer(1)]], device const half* b [[buffer(2)]], uint g [[thread_position_in_grid]]){ out[g]=min(a[g],b[g]); }",
 'nh_max':  "kernel void k(device half* out [[buffer(0)]], device const half* a [[buffer(1)]], device const half* b [[buffer(2)]], uint g [[thread_position_in_grid]]){ out[g]=max(a[g],b[g]); }",
 'nh2_min': "kernel void k(device half2* out [[buffer(0)]], device const half2* a [[buffer(1)]], device const half2* b [[buffer(2)]], uint g [[thread_position_in_grid]]){ out[g]=min(a[g],b[g]); }",
 'h2rt':    "kernel void k(device float2* out [[buffer(0)]], device const float2* a [[buffer(1)]], uint g [[thread_position_in_grid]]){ half2 h=half2(a[g]); out[g]=float2(h); }",
 'nbf_add': "kernel void k(device bfloat* out [[buffer(0)]], device const bfloat* a [[buffer(1)]], device const bfloat* b [[buffer(2)]], uint g [[thread_position_in_grid]]){ out[g]=a[g]+b[g]; }",
 'nbf_fma': "kernel void k(device bfloat* out [[buffer(0)]], device const bfloat* a [[buffer(1)]], device const bfloat* b [[buffer(2)]], device const bfloat* c [[buffer(3)]], uint g [[thread_position_in_grid]]){ out[g]=a[g]*b[g]+c[g]; }",
 'nbf2_add':"kernel void k(device bfloat2* out [[buffer(0)]], device const bfloat2* a [[buffer(1)]], device const bfloat2* b [[buffer(2)]], uint g [[thread_position_in_grid]]){ out[g]=a[g]+b[g]; }",
 'nbf_chain':"kernel void k(device bfloat* out [[buffer(0)]], device const bfloat* a [[buffer(1)]], device const bfloat* b [[buffer(2)]], uint g [[thread_position_in_grid]]){ bfloat s=a[g]+b[g]; out[g]=s*a[g]; }",
}
for name,body in CAR.items():
    src=os.path.join(K,name+'.metal'); open(src,'w').write(HDR+body+"\n")
    try:
        compile_carrier(src,os.path.join(K,name+'.bin'))
        _,_,main=load_base(os.path.join(K,name+'.bin'))
        print('='*72); print(name,'len',len(main)); show(main)
    except Exception as e:
        print('='*72); print(name,'FAILED',str(e)[:200])
