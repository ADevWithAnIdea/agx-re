#!/usr/bin/env python3
"""PREFREEZE pilot 3 -- 4-byte insertion (k_line3, 6 bytes of slack) and the
n2_op6 spot checks in c_depth."""
import json, os, struct, subprocess, sys
sys.path.insert(0, os.path.expanduser("~/agxre/EXP-0199/harness"))
from runner199 import ComputeRunner, RenderRunner
HERE = os.path.expanduser("~/agxre/EXP-0199")
S = os.path.expanduser("~/agxre/tools/shdump/agxparse.py")
rep = {}

o = subprocess.check_output(["python3", S, os.path.join(HERE, "work/k_line3.bin"),
                             "--locate", "_agc.main"], text=True).split()
off, ln = int(o[0]), int(o[1])
main = bytes.fromhex(subprocess.check_output(
    ["python3", S, os.path.join(HERE, "work/k_line3.bin"), "--extract-hex"],
    text=True).strip())
a = [(0x9E3779B9 * (i + 1)) & 0xFFFFFFFF for i in range(32)]
oracle = [((((a[i] * 3 + i * 7 + 11) & 0xFFFFFFFF) ^ 0x13579BDF) + 0x2468ACE0) & 0xFFFFFFFF
          for i in range(32)]
sent = [(0xA5A50000 + i) & 0xFFFFFFFF for i in range(32)]
cr = ComputeRunner(os.path.join(HERE, "harness/crun199"),
                   os.path.join(HERE, "kernels/k_line3.metal"), "k_line3",
                   os.path.join(HERE, "work/k_line3.bin"),
                   os.path.join(HERE, "work/sc3_kl3.bin"),
                   os.path.join(HERE, "work/k_line_in.bin"), 128 * 4, 32, 32)
def score(r):
    o = r["surf"].get("OUT0", b"")
    if len(o) != 512:
        return dict(st=r["status"], err=r.get("error", "")[:100])
    v = list(struct.unpack("<128I", o))
    return dict(st=r["status"],
                comp=("OK" if v[:32] == oracle else
                      ("POISON" if all(x == 0xDEADBEEF for x in v[:32]) else
                       ("ZERO" if all(x == 0 for x in v[:32]) else "WRONG"))),
                sent=("OK" if v[64:96] == sent else "NOT"),
                f2=[hex(x) for x in v[:2]])
rep["k3_base"] = score(cr.run([], timeout=20))
rep["k3_ident"] = score(cr.run([(off, main.hex())], timeout=20))
for B in (52, 74, 94):
    for lbl, ins in [("i2_0602", "0602"), ("i2_6001", "6001"), ("i2_6000", "6000"),
                     ("i4_06020602", "06020602"), ("i4_60010000", "60010000"),
                     ("i4_60000000", "60000000"), ("i4_00000000", "00000000"),
                     ("i4_6001ffff", "6001ffff"),
                     ("i6_060206020602", "060206020602")]:
        rep["k3_%s@%d" % (lbl, B)] = score(
            cr.run([(off + B, ins + main[B:].hex())], timeout=20))
cr.close()

# ---- n2_op6 in c_depth ----------------------------------------------------
CAR = json.load(open(os.path.join(HERE, "work", "carriers_raw.json")))
foff = CAR["c_depth/fragment"]["main_off"]
cfg = dict(color_format=125, width=16, height=16, depth=True, depth_clear=1.0,
           depth_compare=7, clear=[0.75, 0.75, 0.75, 0.75])
rr = RenderRunner(os.path.join(HERE, "harness/gfrun5"),
                  os.path.join(HERE, "kernels/c_depth.metal"),
                  os.path.join(HERE, "work/c_depth.bin"),
                  os.path.join(HERE, "work/sc3_cd.bin"), cfg)
PTS = [(8, 8), (5, 10), (11, 5)]
def rp(r):
    d = dict(st=r["status"], err=r.get("error", "")[:100])
    if "PIX0" in r["surf"]:
        d["col"] = [round(struct.unpack_from("<4f", r["surf"]["PIX0"], (y*16+x)*16)[0], 5) for (x, y) in PTS]
    if "DEPTH" in r["surf"]:
        d["dep"] = [round(struct.unpack_from("<f", r["surf"]["DEPTH"], (y*16+x)*4)[0], 5) for (x, y) in PTS]
    return d
rep["n2_base"] = rp(rr.render([], timeout=25))
N = 48
for lbl, spl in [("dst_1", [(foff+N, "12")]), ("dst_2", [(foff+N, "22")]),
                 ("dst_8", [(foff+N, "82")]), ("dst_f", [(foff+N, "f2")]),
                 ("lonib_0", [(foff+N, "00")]), ("lonib_3", [(foff+N, "03")]),
                 ("srcdesc_00", [(foff+N+1, "00")]), ("srcdesc_ff", [(foff+N+1, "ff")]),
                 ("opsel_02", [(foff+N+2, "02")]), ("opsel_ff", [(foff+N+2, "ff")]),
                 ("opA_01", [(foff+N+3, "01")]), ("opB_20", [(foff+N+4, "20")]),
                 ("imm_00", [(foff+N+5, "00")]), ("imm_08", [(foff+N+5, "08")]),
                 ("imm_0c", [(foff+N+5, "0c")]), ("imm_ff", [(foff+N+5, "ff")]),
                 ("null_barrier", [(foff+N, "070254010000")])]:
    rep["n2_" + lbl] = rp(rr.render(spl, timeout=25))
rr.close()
print(json.dumps(rep, indent=None, separators=(",", ":")))
