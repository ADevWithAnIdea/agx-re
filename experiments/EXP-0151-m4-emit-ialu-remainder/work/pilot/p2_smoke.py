import sys, time, struct
from pathlib import Path
E=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(E/"harness"))
import sweeprun as S, seedcarrier as SC, anchors as A, isadb
c=S.Carrier(E/"kernels"/"carrier_seed.metal","k",E/"work"/"pilot_smoke",timeout=8.0)
ins={1:c.write_input("mem.bin",[0]*32),2:c.write_input("imem.bin",[0]*32)}
def go(instr,dst=SC.R_DST,label=""):
    prog=SC.seed_program(instr,dst)
    r,w=c.run(prog,ins)
    oc,_=S.classify(r["status"],r.get("error"),w,None,1,SC.SENTINEL_INTEGRITY)
    print("%-26s status=%-12s out0=%d(0x%x) out1=%d  %s %s"%(label,r["status"],w[0] if w else -1,w[0] if w else 0,w[1] if len(w)>1 else -1,oc,(r.get("error") or "")[:60]))
    return w
# 1. pure seed program: no instruction under test -> r6 keeps its sentinel
go(b"", label="no-instr (r6 sentinel)")
# 2. iadd2 r0+r2 (EXP-0128 rule) -> 3+23 = 26
i=isadb.assemble("iadd2",dict(addsub=1,lenbit=1,srcB_reg_hi=0,b2_bit0=0,store_en=1,
   b2_fmt=0x15,dst=(SC.R_DST<<1),opmode=2,srcB_imm=4*2,srcB_imm_hi=0,srcB_ext=0,
   srcA=0xA8,opc_tail=0x17,opc_tail2=5))
go(i,label="iadd2 r0+r2 (want 26)")
# 3. isel8 anchor from k_abs with dst redirected to r6
an=bytes.fromhex("02010f8081040702")
for dstv in (0,6):
    go(A.set_field(an,"isel8","dst",dstv), label="isel8 anchor dst=%d"%dstv)
# 4. throughput
t=time.time()
for k in range(40): c.run(SC.seed_program(i),ins)
print("throughput: %.1f ms/dispatch"%((time.time()-t)/40*1000))
c.close()
