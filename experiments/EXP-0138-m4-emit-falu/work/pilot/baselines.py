import sys
from pathlib import Path
EXP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EXP / "harness"))
import isa_helpers as H, bench as B
bench = B.Bench(EXP/"kernels"/"carrier.metal","k",EXP/"work"/"bin",EXP/"work"/"pilot"/"bw")
mem = bench.write_in(1,[float(i) for i in range(16)])
seeds=[H.mov_imm(H.R_IDX,0)]+[H.seed(r,v) for r,v in sorted(H.SEED.items())]
RD=H.reg_desc
def go(tag,instr):
    instrs=seeds+[instr,H.store_word(0,6),H.store_word(4,11),H.store_word(8,0),H.store_word(12,2),H.stop()]
    p=H.build_program(instrs,bench.region_len); H.assert_round_trip(p)
    r=bench.run([(0,p)],ins={1:mem},outs={0:64}); w=B.words_f32(r["outs"].get(0,b""),13)
    print("%-24s %-10s w0=%-8s ctl=%-6s r0=%-6s r2=%-6s %s" % (tag,r["status"],w[0] if len(w)>0 else '-',w[4] if len(w)>4 else '-',w[8] if len(w)>8 else '-',w[12] if len(w)>12 else '-', (r.get("error") or "")[:90]))
go("falu2",            H.falu2_raw(6,0,2,opflags5=0))
go("falu2i",           H.falu2i_raw(6,0,3.0,opflags4=0))
go("falu2_ext tail80", H.falu2_ext_raw(6,0,2,opflags5=0,ext_tail=0x8000))
go("falu2_ext tail82", H.falu2_ext_raw(6,0,2,opflags5=0,ext_tail=0x8200))
go("srcmod10",         H.falu2_srcmod10_raw(6,0,2,opflags5=0))
go("srcmod12b",        H.falu_srcmod12b_raw(6,0,2,opsel=0,opflags5=0))
go("falu3",            H.falu3_raw(6,RD(0),0x1e,RD(2),0x81,RD(4,0)))
go("falu3 srcmods00",  H.falu3_raw(6,RD(0),0x1e,RD(2),0x81,RD(4,0),srcmods=0x00))
go("falu3_ext ext80",  H.falu3_ext_raw(6,RD(0),0x1e,RD(2),0x82,RD(4,0),ext=0x80000002))
go("falu3_ext ext82",  H.falu3_ext_raw(6,RD(0),0x1e,RD(2),0x82,RD(4,0),ext=0x82000002))
go("f3srcmod12",       H.falu3_srcmod12_raw(6,0,2,opsel=6,opflags5=0))
go("falu_acc",         H.falu_acc_raw(6,RD(0),RD(2),op=0))
go("falu_acc cache0",  H.falu_acc_raw(6,RD(0),RD(2),op=0,cache=0))
bench.close()
