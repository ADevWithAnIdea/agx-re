import sys
from pathlib import Path
EXP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EXP / "harness"))
import isa_helpers as H
import bench as B
bench = B.Bench(EXP/"kernels"/"carrier.metal","k",EXP/"work"/"bin",EXP/"work"/"pilot"/"bw")
mem = bench.write_in(1, [float(i) for i in range(16)])
def go(tag, instrs, nw=16):
    p=H.build_program(instrs, bench.region_len); H.assert_round_trip(p)
    r=bench.run([(0,p)], ins={1:mem}, outs={0:nw*4})
    print("%-28s %-14s %s" % (tag, r["status"], B.words_f32(r["outs"].get(0,b""), nw)))
seeds=[H.mov_imm(H.R_IDX,0)]+[H.seed(r,v) for r,v in sorted(H.SEED.items())]
# A: opflags5=0 on the tested falu2, stores after
go("opflags0", seeds+[H.falu2_raw(6,0,2,opsel=4,opflags5=0),
                      H.store_word(0,0),H.store_word(4,2),H.store_word(8,6),
                      H.falu2_raw(7,0,2,opsel=5,opflags5=0),H.store_word(12,7),H.stop()])
# B: stores of the seeds only, no ALU
go("seeds-only", seeds+[H.store_word(0,0),H.store_word(4,2),H.store_word(8,9),H.store_word(12,12),H.stop()])
# C: 8 stores to check word slots
go("8slots", seeds+[H.store_word(4*i, i) for i in range(8)]+[H.stop()], nw=32)
bench.close()
