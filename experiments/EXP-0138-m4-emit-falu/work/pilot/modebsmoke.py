import sys, struct
from pathlib import Path
EXP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EXP / "harness"))
import isa_helpers as H, bench as B
K = EXP/"kernels"
def half_in(bench, vals):
    p = bench.work/"inh.bin"; p.write_bytes(b"".join(struct.pack("<e",v) for v in vals)); return str(p)

# --- half_alu (k_hadd) ---
b = B.Bench(K/"anchors.metal","k_hadd",EXP/"work"/"bin",EXP/"work"/"pilot"/"bh")
inp = half_in(b,[5.0,3.0,0.5,7.0,9.0,11.0,13.0,0.25])
print("k_hadd main len", b.region_len, b.main_bytes[0x2a:0x30].hex())
for tag,off,data in [("baseline",None,None),
                     ("hmul",0x2a,bytes.fromhex("10041d0200c0")),
                     ("modlo1",0x2a,bytes.fromhex("10041c0200c1")),
                     ("modlo2",0x2a,bytes.fromhex("10041c0200c2"))]:
    pairs = [] if off is None else [(off,data)]
    r=b.run(pairs, ins={1:inp}, outs={0:8})
    print("  %-9s %-10s %s" % (tag, r["status"], B.halfs(r["outs"].get(0,b""),4)))
b.close()

# --- fspecial (k_rsqrtf, fast math) ---
b = B.Bench(K/"anchors3.metal","k_rsqrtf",EXP/"work"/"bin",EXP/"work"/"pilot"/"bs",fast_math=True)
inp = b.write_in(1,[4.0,3.0,0.5,7.0])
print("k_rsqrtf main len", b.region_len, b.main_bytes[0x12:0x1c].hex())
for tag,off,data in [("baseline",None,None),
                     ("rcp",0x12,bytes.fromhex("af005600020010482000")),
                     ("exp2",0x12,bytes.fromhex("af0256000200b0400000")),
                     ("floor",0x12,bytes.fromhex("2f0056000200b0400200"))]:
    pairs = [] if off is None else [(off,data)]
    r=b.run(pairs, ins={1:inp}, outs={0:16})
    print("  %-9s %-10s %s" % (tag, r["status"], B.words_f32(r["outs"].get(0,b""),2)))
b.close()

# --- copysign (k_copysign) ---
b = B.Bench(K/"anchors.metal","k_copysign",EXP/"work"/"bin",EXP/"work"/"pilot"/"bc")
inp = b.write_in(1,[5.0,-3.0,0.5,7.0])
print("k_copysign main len", b.region_len, b.main_bytes[0x30:0x34].hex())
for tag,off,data in [("baseline",None,None),
                     ("ops=01",0x30,bytes.fromhex("07c28801")),
                     ("ops=02",0x30,bytes.fromhex("07c28802")),
                     ("ops=ff",0x30,bytes.fromhex("07c288ff"))]:
    pairs = [] if off is None else [(off,data)]
    r=b.run(pairs, ins={1:inp}, outs={0:16})
    print("  %-9s %-10s %s" % (tag, r["status"], B.words_f32(r["outs"].get(0,b""),2)))
b.close()
