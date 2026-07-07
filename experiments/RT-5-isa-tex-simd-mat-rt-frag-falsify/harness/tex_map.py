#!/usr/bin/env python3
# tex_map.py -- map the texture-sample slot/variant bytes by splicing sample#0
# and running texrun (multi-texture/sampler compute runner) each time.
import sys, os, struct, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def locate(a):
    o=subprocess.check_output(["python3","agxparse.py",a,"--locate","_agc.main"],text=True); return int(o.split()[0])

def find_first_sample(buf):
    for j in range(len(buf)-14):
        if (buf[j]&0x0f)==0x05 and (buf[j+1]&0xf0)==0x80 and buf[j+2]==0x0c:
            return j  # companion offset; sampler-op = j+4
    return None

def f4(vals): return b"".join(struct.pack("<f",v) for v in vals)

def texrun(archive, texargs, sampargs, nout, outidx=0):
    cmd=["./texrun","--archive",archive,"--source",SRC,"--function","k","--no-fast-math","--grid","1","--tg","1"]
    for t in texargs: cmd+=["--tex",t]
    for s in sampargs: cmd+=["--samp",s]
    cmd+=["--out",f"{outidx}={nout*16}"]
    out=subprocess.check_output(cmd,text=True)
    res={}
    for ln in out.splitlines():
        if ln.startswith("OUT "):
            _,idx,hexb=ln.split(); b=bytes.fromhex(hexb)
            res[int(idx)]=[struct.unpack("<f",b[i:i+4])[0] for i in range(0,len(b),4)]
        if ln.startswith("STATUS"): res["status"]=ln.split()[1]
    return res

SRC="kernels/tex_read3.metal"
def main():
    arch="tr3.bin"
    subprocess.check_call(["./shdump","-o",arch,"--no-fast-math","-f","k",SRC])
    moff=locate(arch); base=bytearray(open(arch,"rb").read())
    hexmain=base[moff:moff+ (int(subprocess.check_output(["python3","agxparse.py",arch,"--locate","_agc.main"],text=True).split()[1]))]
    comp=find_first_sample(hexmain)
    sop=comp+4
    print(f"# _agc.main abs {moff}, first-sample companion@+0x{comp:02x} sampler-op@+0x{sop:02x}")
    print(f"# baseline op: {bytes(hexmain[sop:sop+10]).hex()}")
    texs=["0=1,1,255,0,0,255","1=1,1,0,255,0,255","2=1,1,0,0,255,255"]  # red green blue solid
    # baseline
    r=texrun(arch,texs,[],3)
    print("baseline out:", {k:r[k] for k in (0,1,2) if k in r}, r.get("status"))
    OP4 = sop+4  # tex_slot within _agc.main
    for v in [0x00,0x01,0x02,0x03,0x80,0x81,0x82,0x83]:
        buf=bytearray(base); buf[moff+OP4]=v
        open("txspl.bin","wb").write(buf)
        r=texrun("txspl.bin",texs,[],3)
        o0=r.get(0,["?"]); print(f"  op+4=0x{v:02x} -> out[0]={o0}  status={r.get('status')}")

if __name__=="__main__": main()
