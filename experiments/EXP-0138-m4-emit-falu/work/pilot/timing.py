import sys, time
from pathlib import Path
EXP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EXP / "harness"))
import isa_helpers as H, bench as B
bench = B.Bench(EXP/"kernels"/"carrier.metal","k",EXP/"work"/"bin",EXP/"work"/"pilot"/"bw")
mem = bench.write_in(1, [float(i) for i in range(16)])
seeds=[H.mov_imm(H.R_IDX,0)]+[H.seed(r,v) for r,v in sorted(H.SEED.items())]
t0=time.time(); n=60
for i in range(n):
    instrs = seeds+[H.falu2_raw(6,0,2,opsel=4,opflags5=0,mod_lo=i%8),H.store_word(0,6),H.stop()]
    p=H.build_program(instrs,bench.region_len)
    r=bench.run([(0,p)],ins={1:mem},outs={0:16})
dt=time.time()-t0
print("%.1f ms/case over %d cases" % (dt/n*1000, n))
bench.close()
