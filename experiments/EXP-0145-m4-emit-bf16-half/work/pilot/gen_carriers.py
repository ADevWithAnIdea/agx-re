import sys,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from lib import *
K=os.path.join(EXP,'work','pilot','k')
HDR="#include <metal_stdlib>\nusing namespace metal;\n"
SIG="kernel void k(device float* out [[buffer(0)]], device float* a [[buffer(1)]], device float* b [[buffer(2)]], device float* c [[buffer(3)]], uint tid [[thread_position_in_grid]]) {\n"
CAR={
 'bfadd':  "bfloat x=bfloat(a[tid]),y=bfloat(b[tid]); out[tid]=float(x+y);",
 'bfmul':  "bfloat x=bfloat(a[tid]),y=bfloat(b[tid]); out[tid]=float(x*y);",
 'bffma':  "bfloat x=bfloat(a[tid]),y=bfloat(b[tid]),z=bfloat(c[tid]); out[tid]=float(fma(x,y,z));",
 'bfchain':"bfloat x=bfloat(a[tid]),y=bfloat(b[tid]); bfloat s=x+y; out[tid]=float(s*x);",
 'hadd':   "half x=half(a[tid]),y=half(b[tid]); out[tid]=float(x+y);",
 'h2add':  "half2 x=half2(a[tid],a[tid+1u]),y=half2(b[tid],b[tid+1u]); half2 s=x+y; out[tid]=float(s.x)+float(s.y)*1024.0f;",
 'h2mul':  "half2 x=half2(a[tid],a[tid+1u]),y=half2(b[tid],b[tid+1u]); half2 s=x*y; out[tid]=float(s.x)+float(s.y)*1024.0f;",
 'h2fma':  "half2 x=half2(a[tid],a[tid+1u]),y=half2(b[tid],b[tid+1u]),z=half2(c[tid],c[tid+1u]); half2 s=fma(x,y,z); out[tid]=float(s.x)+float(s.y)*1024.0f;",
 'hmin':   "half x=half(a[tid]),y=half(b[tid]); out[tid]=float(min(x,y));",
 'hmax':   "half x=half(a[tid]),y=half(b[tid]); out[tid]=float(max(x,y));",
 'h2pack': "half2 x=half2(a[tid],b[tid]); device half2* o=(device half2*)out; o[tid]=x;",
 'fabs':   "out[tid]=fabs(a[tid]);",
 'fneg':   "out[tid]=-a[tid];",
 'fldexp': "int n=int(b[tid]); out[tid]=ldexp(a[tid],n);",
 'orimm':  "device uint* o=(device uint*)out; device uint* ai=(device uint*)a; o[tid]=ai[tid]|0x100u;",
}
for name,body in CAR.items():
    src=os.path.join(K,name+'.metal')
    open(src,'w').write(HDR+SIG+"    "+body+"\n}\n")
    try:
        compile_carrier(src,os.path.join(K,name+'.bin'))
        _,_,main=load_base(os.path.join(K,name+'.bin'))
        print('='*72); print(name,'len',len(main)); show(main)
    except Exception as e:
        print('='*72); print(name,'FAILED',str(e)[:300])
