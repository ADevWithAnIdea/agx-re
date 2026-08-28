import sys, time
from pathlib import Path
EXP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EXP / "harness"))
import isa_helpers as H, bench as B
bench = B.Bench(EXP/"kernels"/"carrier.metal","k",EXP/"work"/"bin",EXP/"work"/"pilot"/"bw")
mem = bench.write_in(1, [float(i) for i in range(16)])
seeds=[H.mov_imm(H.R_IDX,0)]+[H.seed(r,v) for r,v in sorted(H.SEED.items())]
t0=time.time()
for sb in (2,4,5,7,3,8,2):
    instrs = seeds+[H.falu2_raw(6,0,sb,opsel=4,opflags5=0),H.store_word(0,6),H.stop()]
    p=H.build_program(instrs,bench.region_len)
    r=bench.run([(0,p)],ins={1:mem},outs={0:16})
    print("srcB_reg=%2d -> %-10s %s" % (sb, r["status"], B.words_f32(r["outs"].get(0,b""),1)))
print("%.1f ms/case" % ((time.time()-t0)/7*1000))
bench.close()
