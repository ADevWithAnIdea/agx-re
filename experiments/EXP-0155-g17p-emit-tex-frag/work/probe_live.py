#!/usr/bin/env python3
"""probe_live.py -- PRE-FREEZE diagnostic: is a splice into this carrier's
fragment program observable at all?  Zeroes each byte of the located
instruction, one at a time, and reports the pixel."""
import os, subprocess, sys, struct, json
HERE=os.path.dirname(os.path.abspath(__file__)); EXP=os.path.dirname(HERE)
REPO=os.environ.get("AGXRE_REPO")
sys.path.insert(0,os.path.join(EXP,"harness")); sys.path.insert(0,os.path.join(REPO,"tools","agx-isa"))
import isadb, casematrix as CM
sys.path.insert(0,os.path.join(EXP,"harness"))
from runner import RenderRunner
GFRUN=os.path.join(HERE,"gfrun"); AGXPARSE=os.path.join(REPO,"tools","shdump","agxparse.py")

carrier, stage, mnem, occ = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
cfg=CM.CARRIERS[carrier]; arch=os.path.join(HERE,f"{carrier}.bin")
def sh(c):
    r=subprocess.run(c,capture_output=True,text=True,timeout=120)
    if r.returncode: raise RuntimeError(r.stderr[-500:])
    return r.stdout
a=[sys.executable,AGXPARSE,arch]+([] if stage=="compute" else ["--stage",stage])
off,ln=(int(x) for x in sh(a+["--locate","_agc.main"]).split())
buf=bytes.fromhex(sh(a+["--extract-hex"]).strip())
# locate
recs=[];o=0;left=None
while o<len(buf):
    try: r,L=isadb.decode_one(buf,o)
    except ValueError: left=o;break
    r["off"]=o;recs.append(r);o+=L
if left is None: hits=[r["off"] for r in recs if r["mnemonic"]==mnem]
else:
    hits=[]
    for o in range(len(buf)-1):
        try: r,L=isadb.decode_one(buf,o)
        except ValueError: continue
        if r["mnemonic"]!=mnem: continue
        ok,p=True,o+L
        for _ in range(2):
            if p>=len(buf): break
            try: _r,_l=isadb.decode_one(buf,p)
            except ValueError: ok=False;break
            p+=_l
        if ok: hits.append(o)
ioff=hits[occ]; rec,L=isadb.decode_one(buf,ioff)
print("located",mnem,"occ",occ,"at",ioff,"len",L,"hex",rec["hex"],"abs",off+ioff)
b0=[struct.unpack("<I",struct.pack("<f",v))[0] for v in (CM.BUF0_DERIV if carrier=="t_deriv" else CM.BUF0)] if cfg.get("buf0") else None
rr=RenderRunner(GFRUN,os.path.join(EXP,cfg["src"]),arch,os.path.join(HERE,"probe_scratch.bin"),cfg,b0)
def px(resp):
    if resp["status"]!="OK": return resp["status"]+" "+resp.get("error","")[:80]
    W=cfg["width"];p=resp["pix"]["PIX0"]
    out=[[round(v,4) for v in struct.unpack_from("<4f",p,(y*W+x)*16)] for (x,y) in CM.PROBE_PIXELS[:1]]
    if "texw" in resp:
        t=resp["texw"];tw,_=cfg["tex_write"]
        out.append([[round(v,3) for v in struct.unpack_from("<4f",t,(y*tw+x)*16)] for (x,y) in CM.PROBE_TEXELS])
    return out
base=rr.render([]); print("BASE", px(base))
orig=bytes.fromhex(rec["hex"])
for i in range(L):
    for nv in (0x00,0xff):
        b=bytearray(orig); 
        if b[i]==nv: continue
        b[i]=nv
        r=rr.render([(off+ioff,bytes(b).hex())])
        print(f"  byte+{i:2d}={nv:#04x}", px(r))
rr.close()
