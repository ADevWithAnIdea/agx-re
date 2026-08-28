import sys
from pathlib import Path
EXP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EXP / "harness"))
import isa_helpers as H, bench as B
bench = B.Bench(EXP/"kernels"/"carrier.metal","k",EXP/"work"/"bin",EXP/"work"/"pilot"/"bw")
mem = bench.write_in(1, [float(i) for i in range(16)])
seeds=[H.mov_imm(H.R_IDX,0)]+[H.seed(r,v) for r,v in sorted(H.SEED.items())]
D=6
def go(tag, instr, want):
    instrs = seeds+[instr, H.store_word(0,D), H.store_word(4,11), H.store_word(8,0), H.stop()]
    p=H.build_program(instrs,bench.region_len)
    try: H.assert_round_trip(p)
    except Exception as e: print("%-22s RT-FAIL %s" % (tag,e)); return
    r=bench.run([(0,p)],ins={1:mem},outs={0:64})
    w=B.words_f32(r["outs"].get(0,b""),12)
    if len(w)<9:
        print("%-22s %-12s NO-OUTPUT err=%s" % (tag,r["status"],r.get("error"))); return
    print("%-22s %-12s dst=%-8s ctl=%-6s r0=%-6s want %s %s" % (tag,r["status"],w[0],w[4],w[8],want,"OK" if w[0]==want else "<<<"))
RD=H.reg_desc
go("falu2 add",       H.falu2_raw(D,0,2,opsel=4,opflags5=0), 8.0)
go("falu2 mul",       H.falu2_raw(D,0,2,opsel=5,opflags5=0), 15.0)
go("falu2i add3",     H.falu2i_raw(D,0,3.0,opflags4=0,mods=0xC0), 8.0)
go("falu2_ext sat",   H.falu2_ext_raw(D,3,8,opsel=4,opflags5=0,srcB_neg=0), 0.75)
go("falu2_ext satclamp",H.falu2_ext_raw(D,0,2,opsel=4,opflags5=0,srcB_neg=0), 1.0)
go("falu2_ext sub",   H.falu2_ext_raw(D,0,2,opsel=4,opflags5=0,srcB_neg=1), 1.0)
go("srcmod10 plain",  H.falu2_srcmod10_raw(D,0,2,opsel=4,opflags5=0), 8.0)
go("srcmod10 absA",   H.falu2_srcmod10_raw(D,0,2,opsel=4,opflags5=0,ext_srcmod=0x00018000), 8.0)
# opsel==4 on falu_srcmod12b is the EXP-0119 unrelated-register corruptor: NOT run here.
go("srcmod12b opsel0",H.falu_srcmod12b_raw(D,0,2,opsel=0,opflags5=0), 8.0)
go("falu3 fma",       H.falu3_raw(D,RD(0),0x1e,RD(2),0x81,RD(4,0)), 22.0)
go("falu3 fma b4=01", H.falu3_raw(D,RD(0),0x1e,RD(2),0x01,RD(4,0)), 22.0)
go("falu3_ext satfma",H.falu3_ext_raw(D,RD(0),0x1e,RD(2),0x82,RD(4,0)), 1.0)
go("f3srcmod12 fma",  H.falu3_srcmod12_raw(D,0,2,opsel=6,opflags5=0), 22.0)
go("falu_acc add",    H.falu_acc_raw(D,RD(0),RD(2),op=0), 8.0)
go("falu_acc mul",    H.falu_acc_raw(D,RD(0),RD(2),op=1), 15.0)
bench.close()
