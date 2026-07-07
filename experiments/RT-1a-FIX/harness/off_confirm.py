import subprocess, struct, sys
sys.path.insert(0,".")
from persistrun import PersistRunner
ARCH="bank.bin"
MAIN_OFF=int(subprocess.check_output(["python3","agxparse.py",ARCH,"--locate","_agc.main"],text=True).split()[0])
base=open(ARCH,"rb").read()
INSN_OFF=0x1c
NA=2048
open("a_big.bin","wb").write(struct.pack("<%dI"%NA,*[100*j+3 for j in range(NA)]))
open("idx.bin","wb").write(struct.pack("<4I",40,3,77,12))
ins={2:"a_big.bin",3:"idx.bin"}; outs={0:4,1:4}
r=PersistRunner(source="bank.metal",function="k",fast_math=False,agxrun_persist="./agxrun_persist")
def ai(v):
  return (v-3)//100 if (v is not None and v>=3 and (v-3)%100==0) else None
try:
  for name,bo,vals in [("byte+11",11,[0x40,0x41,0x42]),("byte+10",10,[0x00,0x08,0x10]),("byte+9",9,[0x01,0x81])]:
    for v in vals:
      sp=bytearray(base); sp[MAIN_OFF+INSN_OFF+bo]=v
      open("sp.bin","wb").write(sp)
      resp=r.request(archive="sp.bin",grid=1,tg=1,ins=ins,outs=outs,timeout=6)
      o0=struct.unpack("<I",resp["outs"][0])[0] if resp["status"]=="OK" else None
      k=ai(o0)
      print("%s 0x%02x %s o0=%s idx=%s" % (name,v,resp["status"],o0,k))
finally:
  r.close()
