import sys, os, subprocess, struct
sys.path.insert(0,".")
from persistrun import PersistRunner
def locate(a): return int(subprocess.check_output(["python3","agxparse.py",a,"--locate","_agc.main"],text=True).split()[0])
fb=open("falubank.bin","rb").read(); fm=locate("falubank.bin")
v=[10.0,20.0,3.0,4.0,5.0,6.0,7.0,8.0]
open("vfb.bin","wb").write(struct.pack("<8f",*v))
ins={2:"vfb.bin"}; outs={0:4,1:4}
r=PersistRunner(source="rt1a_falubank.metal",function="k",fast_math=False,agxrun_persist="./agxrun_persist")
def run(splices):
    sp=bytearray(fb)
    for p,val in splices: sp[fm+p]=val
    open("sp.bin","wb").write(sp)
    resp=r.request(archive="sp.bin",grid=1,tg=1,ins=ins,outs=outs,timeout=6)
    if resp["status"]!="OK": return resp["status"],None,None
    return "OK",struct.unpack("<f",resp["outs"][0])[0],struct.unpack("<f",resp["outs"][1])[0]
print("baseline", run([]))
# redirect dst of the two 0x18 ops (byte0 high nibble) to an unused reg -> stale consumer
print("+0x48 byte0 0x19->0x59 (dst r1->r5):", run([(0x48,0x59)]))
print("+0x4c byte0 0x09->0x59 (dst r0->r5):", run([(0x4c,0x59)]))
# change the 0x18 op's opsel byte+2 low3 (0x18->0x19 = would be 'mul' opsel bit0) 
print("+0x48 byte+2 0x18->0x1c (arith-enable/fadd byte):", run([(0x48+2,0x1c)]))
print("+0x48 byte+2 0x18->0x1d (mul opsel):", run([(0x48+2,0x1d)]))
r.close()
