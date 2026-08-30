#!/usr/bin/env python3
"""PREFREEZE pilot 2 -- does the INSERTION method work at all, and do the render
field spot-checks move the right observable?"""
import json, os, struct, sys
sys.path.insert(0, os.path.expanduser("~/agxre/EXP-0199/harness"))
from runner199 import ComputeRunner, RenderRunner
HERE = os.path.expanduser("~/agxre/EXP-0199")
CAR = json.load(open(os.path.join(HERE, "work", "carriers_raw.json")))
rep = {}

kl = CAR["k_line/compute"]; main = bytes.fromhex(kl["main_hex"]); off = kl["main_off"]
a = [(0x9E3779B9 * (i + 1)) & 0xFFFFFFFF for i in range(32)]
oracle = [((a[i] * 3 + i * 7 + 11) & 0xFFFFFFFF) for i in range(32)]
sent = [(0xA5A50000 + i) & 0xFFFFFFFF for i in range(32)]
cr = ComputeRunner(os.path.join(HERE, "harness/crun199"),
                   os.path.join(HERE, "kernels/k_line.metal"), "k_line",
                   os.path.join(HERE, "work/k_line.bin"),
                   os.path.join(HERE, "work/sc2_kline.bin"),
                   os.path.join(HERE, "work/k_line_in.bin"), 128 * 4, 32, 32)

def score(r):
    o = r["surf"].get("OUT0", b"")
    if len(o) != 512:
        return dict(status=r["status"], err=r.get("error", "")[:110])
    v = list(struct.unpack("<128I", o))
    return dict(status=r["status"], err=r.get("error", "")[:110],
                comp=("OK" if v[:32] == oracle else
                      ("POISON" if all(x == 0xDEADBEEF for x in v[:32]) else
                       ("ZERO" if all(x == 0 for x in v[:32]) else "WRONG"))),
                sent=("OK" if v[64:96] == sent else
                      ("POISON" if all(x == 0xDEADBEEF for x in v[64:96]) else "WRONG")),
                first2=[hex(x) for x in v[:2]])

# (a) pure append into the alignment pad -- no shift, nothing executes it
rep["append_pad"] = score(cr.run([(off + 102, "0602")], timeout=20))
# (b) 2-byte insert at every boundary, several payloads
BOUND = [38, 52, 62, 74, 84, 98]
PAY = {"pad0000": "0000", "sfu0602": "0602", "fmc6001": "6001", "n1_0100": "0100",
       "ffff": "ffff", "stop0e00": "0e00"}
for B in BOUND:
    for k, p in PAY.items():
        spl = [(off + B, p + main[B:].hex())]
        rep["ins_%s@%d" % (k, B)] = score(cr.run(spl, timeout=20))
cr.close()

# ---- c_depth field spot checks -------------------------------------------
cd = CAR["c_depth/fragment"]; foff = cd["main_off"]
cfg = dict(color_format=125, width=16, height=16, depth=True, depth_clear=1.0,
           depth_compare=7, clear=[0.75, 0.75, 0.75, 0.75])
rr = RenderRunner(os.path.join(HERE, "harness/gfrun5"),
                  os.path.join(HERE, "kernels/c_depth.metal"),
                  os.path.join(HERE, "work/c_depth.bin"),
                  os.path.join(HERE, "work/sc2_cdepth.bin"), cfg)
PTS = [(8, 8), (5, 10), (11, 5)]
def rprobe(r):
    d = dict(status=r["status"], err=r.get("error", "")[:110])
    if "PIX0" in r["surf"]:
        d["col"] = [round(struct.unpack_from("<4f", r["surf"]["PIX0"], (y*16+x)*16)[0], 5)
                    for (x, y) in PTS]
    if "DEPTH" in r["surf"]:
        d["dep"] = [round(struct.unpack_from("<f", r["surf"]["DEPTH"], (y*16+x)*4)[0], 5)
                    for (x, y) in PTS]
    return d
rep["cd_base"] = rprobe(rr.render([], timeout=25))
for lbl, spl in [("null_pads", [(foff+168, "000000000000")]),
                 ("null_barrier2", [(foff+168, "0702540c0200")]),
                 ("b3_01", [(foff+171, "01")]), ("b3_02", [(foff+171, "02")]),
                 ("b3_04", [(foff+171, "04")]), ("b3_08", [(foff+171, "08")]),
                 ("b3_ff", [(foff+171, "ff")]),
                 ("b4_01", [(foff+172, "01")]), ("b4_ff", [(foff+172, "ff")]),
                 ("b5_00", [(foff+173, "00")]), ("b5_01", [(foff+173, "01")]),
                 ("b5_02", [(foff+173, "02")]), ("b5_ff", [(foff+173, "ff")]),
                 ("byte1_06", [(foff+169, "06")]), ("byte1_15", [(foff+169, "15")]),
                 ("byte2_56", [(foff+170, "56")]),
                 ("setup_depth_to_color", [(foff+165, "0c")])]:
    rep["cd_" + lbl] = rprobe(rr.render(spl, timeout=25))
rr.close()

# ---- c_vary4 spot checks --------------------------------------------------
cv = CAR["c_vary4/vertex"]; voff = cv["main_off"]
cfg2 = dict(color_format=125, width=16, height=16, clear=[0.75, 0.75, 0.75, 0.75])
r3 = RenderRunner(os.path.join(HERE, "harness/gfrun5"),
                  os.path.join(HERE, "kernels/c_vary4.metal"),
                  os.path.join(HERE, "work/c_vary4.bin"),
                  os.path.join(HERE, "work/sc2_cvary.bin"), cfg2)
def vprobe(r):
    d = dict(status=r["status"], err=r.get("error", "")[:110])
    if "PIX0" in r["surf"]:
        d["rgba"] = [round(v, 3) for v in
                     struct.unpack_from("<4f", r["surf"]["PIX0"], (8*16+8)*16)]
    return d
rep["cv_base"] = vprobe(r3.render([], timeout=25))
for lbl, spl in [("slot_01", [(voff+31, "01")]), ("slot_02", [(voff+31, "02")]),
                 ("slot_04", [(voff+31, "04")]), ("slot_20", [(voff+31, "20")]),
                 ("slot_80", [(voff+31, "80")]), ("slot_ff", [(voff+31, "ff")]),
                 ("sel_00", [(voff+29, "00")]), ("sel_04", [(voff+29, "04")]),
                 ("sel_0a", [(voff+29, "0a")]), ("sel_ff", [(voff+29, "ff")]),
                 ("b0_10", [(voff+28, "10")]), ("b0_d0", [(voff+28, "d0")]),
                 ("b2_00", [(voff+30, "00")]), ("b2_41", [(voff+30, "41")]),
                 ("null_4pad", [(voff+28, "00000000")]),
                 ("d0fam_73_ff", [(voff+73, "ff")]),
                 ("outslot_v1_a0toc0", [(voff+104+40+4, "c0")])]:
    rep["cv_" + lbl] = vprobe(r3.render(spl, timeout=25))
r3.close()
print(json.dumps(rep, indent=None, separators=(",", ":")))
