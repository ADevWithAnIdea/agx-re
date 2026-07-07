# RT-7 Task 2 bonus: prove the 0x09 32-bit srcA size bit reads the LOW halfword.
# out=x+y (x raw bits=0x00003C00 -> float32 ~= 0; low half 0x3C00 = half 1.0).
# 32-bit srcA: reads ~0 -> out~=100. Splice srcA size bit (byte+1 bit0) 1->0:
# reads low half = half(0x3C00)=1.0 -> out=101. Confirms low-half addressing.
import os,sys,subprocess,struct,importlib.util,shutil
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py")); ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
sys.path.insert(0,HERE); from persistrun import PersistRunner
SRC="""#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]], device const float* x [[buffer(1)]],
              device const float* y [[buffer(2)]], uint gid [[thread_position_in_grid]]) {
    out[gid] = x[gid] + y[gid];
}"""
kp=os.path.join(HERE,"kernels","halftest.metal"); open(kp,"w").write(SRC)
arch=os.path.join(HERE,"halftest.bin")
subprocess.run([os.path.join(HERE,"shdump"),"-o",arch,"-f","k","--no-fast-math",kp],capture_output=True)
buf=open(arch,"rb").read(); _,p=ap.extract_agx(buf); main=p["_agc.main"]
i=0;n=len(main);fa=None
while i+6<=n:
    if main[i]==0x09:
        L=8 if (main[i+2]&0x02) else 6
        if (main[i+2]&0x07)==0b100 and (main[i+4]>>7)==0: fa=(i,main[i+1]); break
        i+=L
    elif main[i] in (0x67,0xe7): i+=14
    elif main[i]==0x0e: i+=4
    else: i+=2
off,b1=fa; print("fadd off=%d byte+1=0x%02x srcA r%d size=%d"%(off,b1,b1>>1,b1&1))
loc=subprocess.run(["python3",os.path.join(HERE,"agxparse.py"),arch,"--stage","compute","--locate","_agc.main"],capture_output=True,text=True).stdout.split()
abs1=int(loc[0])+off+1
xb=os.path.join(HERE,"ht_x.bin"); yb=os.path.join(HERE,"ht_y.bin")
open(xb,"wb").write(struct.pack("<I",0x00003C00))   # low half=0x3C00=half 1.0; float32~0
open(yb,"wb").write(struct.pack("<f",100.0))
r=PersistRunner(source=kp,function="k",fast_math=False,agxrun_persist=os.path.join(HERE,"agxrun_persist"))
resp=r.request(archive=arch,grid=1,tg=1,ins={1:xb,2:yb},outs={0:4},timeout=8)
print("baseline (32-bit srcA): out=%s (x float32~=%g, expect ~100)"%(struct.unpack_from('<f',resp["outs"][0],0)[0], struct.unpack('<f',struct.pack('<I',0x00003C00))[0]))
spa=os.path.join(HERE,"ht_sp.bin"); shutil.copyfile(arch,spa)
with open(spa,"r+b") as f: f.seek(abs1); f.write(bytes([b1 & 0xFE]))  # clear size bit -> 16-bit
resp=r.request(archive=spa,grid=1,tg=1,ins={1:xb,2:yb},outs={0:4},timeout=8)
o=struct.unpack_from('<f',resp["outs"][0],0)[0]
print("size bit 1->0 (16-bit srcA): out=%s  (expect 101 if reads LOW half=half(0x3C00)=1.0)"%o)
r.close()
