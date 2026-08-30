import sys, time
from pathlib import Path
E=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(E/"harness"))
import sweeprun as S, seedcarrier as SC, anchors as A, isadb
c=S.Carrier(E/"kernels"/"carrier_seed.metal","k",E/"work"/"pilot_dump",timeout=8.0)
ins={1:c.write_input("mem.bin",[0]*32),2:c.write_input("imem.bin",[0]*32)}
c.poison_words=64
import struct
Path(c.poison_path).write_bytes(struct.pack("<64I",*([S.POISON]*64)))
def go(instr,label=""):
    r,w=c.run(SC.seed_program(instr),ins,out_words=64)
    regs=SC.regs_from_words(w)
    base=[SC.SEED[k] for k in range(16)]
    diff={k:(base[k],regs[k]) for k in range(16) if regs[k]!=base[k]}
    print("%-28s %-10s sent=%s  diffs=%s"%(label,r["status"],w[1] if len(w)>1 else None,diff))
    return regs
go(b"", "no-instr")
i=isadb.assemble("iadd2",dict(addsub=1,lenbit=1,srcB_reg_hi=0,b2_bit0=0,store_en=1,
   b2_fmt=0x15,dst=(6<<1),opmode=2,srcB_imm=4*2,srcB_imm_hi=0,srcB_ext=0,
   srcA=0xA8,opc_tail=0x17,opc_tail2=5))
go(i,"iadd2 r0+r2->r6 (26)")
an=bytes.fromhex("02010f8081040702")
for dv in range(16):
    go(A.set_field(an,"isel8","dst",dv),"isel8 dst=%d"%dv)
c.close()
