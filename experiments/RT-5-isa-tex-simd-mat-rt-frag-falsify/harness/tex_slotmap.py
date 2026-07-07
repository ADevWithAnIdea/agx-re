#!/usr/bin/env python3
# tex_slotmap.py -- find which byte(s) of the sample op actually select the
# texture, by splicing sample#0 (reads t0=red) and watching out[0] flip to
# t1=green / t2=blue. tex_read3: t0=red t1=green t2=blue (solid).
import sys, os, struct, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
SRC="kernels/tex_read3.metal"
def locate(a):
    o=subprocess.check_output(["python3","agxparse.py",a,"--locate","_agc.main"],text=True); return int(o.split()[0]),int(o.split()[1])
def color(v):
    # v = first float4
    r,g,b,a=v[:4]
    if r>0.5 and g<0.5 and b<0.5: return "RED(t0)"
    if g>0.5 and r<0.5 and b<0.5: return "GREEN(t1)"
    if b>0.5 and r<0.5 and g<0.5: return "BLUE(t2)"
    return f"({r:.2f},{g:.2f},{b:.2f},{a:.2f})"
def texrun(archive,texs):
    cmd=["./texrun","--archive",archive,"--source",SRC,"--function","k","--no-fast-math","--grid","1","--tg","1"]
    for t in texs: cmd+=["--tex",t]
    cmd+=["--out","0=48"]
    out=subprocess.check_output(cmd,text=True)
    for ln in out.splitlines():
        if ln.startswith("OUT "):
            b=bytes.fromhex(ln.split()[2]); return [struct.unpack("<f",b[i:i+4])[0] for i in range(0,len(b),4)]
    return None
def main():
    arch="tr3.bin"; subprocess.check_call(["./shdump","-o",arch,"--no-fast-math","-f","k",SRC])
    moff,mlen=locate(arch); base=bytearray(open(arch,"rb").read())
    texs=["0=1,1,255,0,0,255","1=1,1,0,255,0,255","2=1,1,0,0,255,255"]
    # sample#0: companion@+0x0c, sampler-op@+0x10
    COMP=0x0c; SOP=0x10
    positions={"comp+3":COMP+3,"op+1":SOP+1,"op+3":SOP+3,"op+4":SOP+4,"op+7":SOP+7,"op+9":SOP+9}
    print("baseline out[0]:", color(texrun(arch,texs)))
    for label,rel in positions.items():
        line=[]
        for v in [0x00,0x01,0x02,0x80,0xb8,0x48,0x24]:
            buf=bytearray(base); buf[moff+rel]=v; open("tsl.bin","wb").write(buf)
            try: r=texrun("tsl.bin",texs); c=color(r) if r else "ERR"
            except subprocess.CalledProcessError: c="FAULT"
            line.append(f"{v:#04x}:{c}")
        print(f"{label:8s} (+0x{rel:02x}): "+"  ".join(line))
    # combined: op+4=0x80 AND comp+3=0xb8 (t1+t2 bits) -> ?
    for combo in [[(SOP+4,0x80),(COMP+3,0xb8)],[(SOP+1,0x00),(COMP+3,0xb8)],[(SOP+1,0x48),(COMP+3,0x18)]]:
        buf=bytearray(base)
        for rel,v in combo: buf[moff+rel]=v
        open("tsl.bin","wb").write(buf); r=texrun("tsl.bin",texs)
        print("combo",[(hex(rel-SOP if rel>=SOP else rel-COMP),hex(v)) for rel,v in combo],"->",color(r) if r else "ERR")
if __name__=="__main__": main()
