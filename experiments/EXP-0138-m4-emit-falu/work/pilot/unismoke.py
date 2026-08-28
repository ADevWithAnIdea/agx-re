import sys, struct
from pathlib import Path
EXP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EXP / "harness"))
import isa_helpers as H, bench as B
b = B.Bench(EXP/"kernels"/"carrier_uni.metal","k",EXP/"work"/"bin",EXP/"work"/"pilot"/"bu")
print("region_len", b.region_len)
mem = b.write_in(1,[float(i) for i in range(16)])
uni = b.write_in(2,[101.0,202.0,303.0,404.0])
seeds=[H.mov_imm(H.R_IDX,0)]+[H.seed(r,v) for r,v in sorted(H.SEED.items())]
# read uniform register U as srcB with mod_lo=2 (hypothesis: bit1 -> srcB from uniform file)
for U in range(0,16):
    instrs = seeds+[H.falu2_raw(6,14,U,opsel=4,opflags5=0,mod_lo=2),H.store_word(0,6),H.stop()]
    p=H.build_program(instrs,b.region_len); H.assert_round_trip(p)
    r=b.run([(0,p)],ins={1:mem,2:uni},outs={0:16})
    print("  srcB(uni)=%2d mod_lo=2 -> %-10s %s" % (U,r["status"],B.words_f32(r["outs"].get(0,b""),1)))
# control: mod_lo=0 same encoding reads the GPR file
for U in (0,2,6):
    instrs = seeds+[H.falu2_raw(6,14,U,opsel=4,opflags5=0,mod_lo=0),H.store_word(0,6),H.stop()]
    p=H.build_program(instrs,b.region_len)
    r=b.run([(0,p)],ins={1:mem,2:uni},outs={0:16})
    print("  srcB(gpr)=%2d mod_lo=0 -> %-10s %s" % (U,r["status"],B.words_f32(r["outs"].get(0,b""),1)))
# mod_lo=1 : srcA from uniform?
for U in range(0,10):
    instrs = seeds+[H.falu2_raw(6,U,14,opsel=4,opflags5=0,mod_lo=1),H.store_word(0,6),H.stop()]
    p=H.build_program(instrs,b.region_len)
    r=b.run([(0,p)],ins={1:mem,2:uni},outs={0:16})
    print("  srcA(uni)=%2d mod_lo=1 -> %-10s %s" % (U,r["status"],B.words_f32(r["outs"].get(0,b""),1)))
b.close()
