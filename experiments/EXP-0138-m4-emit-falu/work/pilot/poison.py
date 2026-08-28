import sys, struct
from pathlib import Path
EXP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EXP / "harness"))
import isa_helpers as H, bench as B
b = B.Bench(EXP/"kernels"/"carrier.metal","k",EXP/"work"/"bin",EXP/"work"/"pilot"/"bp")
mem = b.write_in(1,[float(i) for i in range(16)])
poison = b.poison_file(64)
seeds=[H.mov_imm(H.R_IDX,0)]+[H.seed(r,v) for r,v in sorted(H.SEED.items())]
instrs = seeds+[H.falu2_raw(6,0,2,opflags5=0),H.store_word(0,6),H.store_word(4,11),H.store_word(8,0),H.stop()]
p=H.build_program(instrs,b.region_len)
r=b.run([(0,p)], ins={0:poison,1:mem}, outs={0:64})
u=B.words_u32(r["outs"].get(0,b""),16)
print("status",r["status"],"class",r.get("outcome_class"))
print("u32:", [hex(x) for x in u])
print("f32:", B.words_f32(r["outs"].get(0,b""),16))
b.close()
