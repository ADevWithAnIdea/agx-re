#!/usr/bin/env python3
"""PREFREEZE pilot -- verifies the harness and the baseline oracles BEFORE the
contract is frozen.  Output is retained under raw/prefreeze/."""
import json, os, struct, sys
sys.path.insert(0, os.path.expanduser("~/agxre/EXP-0199/harness"))
from runner199 import ComputeRunner, RenderRunner

HERE = os.path.expanduser("~/agxre/EXP-0199")
CAR = json.load(open(os.path.join(HERE, "work", "carriers_raw.json")))
rep = {}

# ---- compute: k_line ------------------------------------------------------
kl = CAR["k_line/compute"]
main = bytes.fromhex(kl["main_hex"]); off = kl["main_off"]
a = [(0x9E3779B9 * (i + 1)) & 0xFFFFFFFF for i in range(32)]
oracle = [((a[i] * 3 + i * 7 + 11) & 0xFFFFFFFF) for i in range(32)]
sent = [(0xA5A50000 + i) & 0xFFFFFFFF for i in range(32)]
cr = ComputeRunner(os.path.join(HERE, "harness/crun199"),
                   os.path.join(HERE, "kernels/k_line.metal"), "k_line",
                   os.path.join(HERE, "work/k_line.bin"),
                   os.path.join(HERE, "work/sc_kline.bin"),
                   os.path.join(HERE, "work/k_line_in.bin"),
                   128 * 4, 32, 32)
r = cr.run([], timeout=20)
o = r["surf"].get("OUT0", b"")
vals = list(struct.unpack("<128I", o)) if len(o) == 512 else []
rep["k_line_baseline"] = dict(status=r["status"], gputime=r.get("gputime"),
    ok_compute=vals[0:32] == oracle, ok_sentinel=vals[64:96] == sent,
    poison_mid=all(v == 0xDEADBEEF for v in vals[32:64]),
    poison_tail=all(v == 0xDEADBEEF for v in vals[96:128]),
    first4=[hex(v) for v in vals[:4]], oracle4=[hex(v) for v in oracle[:4]])
# identity splice must reproduce the baseline
r2 = cr.run([(off, main.hex())], timeout=20)
o2 = r2["surf"].get("OUT0", b"")
rep["k_line_identity_splice"] = dict(status=r2["status"], same=(o2 == o))
# 2-byte insertion smoke: pad 0000 at B=52, and a deletion falsifier
for lbl, spl in [("ins_pad@52", [(off + 52, (b"\x00\x00" + main[52:]).hex())]),
                 ("del2@52", [(off + 52, main[54:].hex())])]:
    rr = cr.run(spl, timeout=20)
    oo = rr["surf"].get("OUT0", b"")
    vv = list(struct.unpack("<128I", oo)) if len(oo) == 512 else []
    rep["k_line_" + lbl] = dict(status=rr["status"], err=rr.get("error", "")[:120],
        ok_compute=vv[0:32] == oracle if vv else None,
        ok_sentinel=vv[64:96] == sent if vv else None,
        first4=[hex(v) for v in vv[:4]] if vv else [])
cr.close()

# ---- render: c_depth ------------------------------------------------------
cd = CAR["c_depth/fragment"]
cfg = dict(color_format=125, width=16, height=16, depth=True,
           depth_clear=1.0, depth_compare=7, clear=[0.75, 0.75, 0.75, 0.75])
rr = RenderRunner(os.path.join(HERE, "harness/gfrun5"),
                  os.path.join(HERE, "kernels/c_depth.metal"),
                  os.path.join(HERE, "work/c_depth.bin"),
                  os.path.join(HERE, "work/sc_cdepth.bin"), cfg)
r = rr.render([], timeout=25)
def probes(buf, w, bpp, pts, fmt):
    return [[round(v, 6) for v in struct.unpack_from(fmt, buf, (y * w + x) * bpp)]
            for (x, y) in pts]
PTS = [(8, 8), (5, 10), (11, 5)]
rep["c_depth_baseline"] = dict(status=r["status"], err=r.get("error", "")[:150],
    color=probes(r["surf"]["PIX0"], 16, 16, PTS, "<4f") if "PIX0" in r["surf"] else None,
    depth=probes(r["surf"]["DEPTH"], 16, 4, PTS, "<1f") if "DEPTH" in r["surf"] else None,
    surfaces=sorted(r["surf"].keys()))
# NULL the frag_depth_store (offset 168, 6 bytes) with the barrier that follows it
foff = cd["main_off"]
r2 = rr.render([(foff + 168, "070254010000")], timeout=25)
rep["c_depth_null_fds"] = dict(status=r2["status"], err=r2.get("error", "")[:150],
    color=probes(r2["surf"]["PIX0"], 16, 16, PTS, "<4f") if "PIX0" in r2["surf"] else None,
    depth=probes(r2["surf"]["DEPTH"], 16, 4, PTS, "<1f") if "DEPTH" in r2["surf"] else None)
rr.close()

# ---- render: c_vary4 ------------------------------------------------------
cv = CAR["c_vary4/vertex"]
cfg2 = dict(color_format=125, width=16, height=16, clear=[0.75, 0.75, 0.75, 0.75])
r3 = RenderRunner(os.path.join(HERE, "harness/gfrun5"),
                  os.path.join(HERE, "kernels/c_vary4.metal"),
                  os.path.join(HERE, "work/c_vary4.bin"),
                  os.path.join(HERE, "work/sc_cvary.bin"), cfg2)
r = r3.render([], timeout=25)
rep["c_vary4_baseline"] = dict(status=r["status"], err=r.get("error", "")[:150],
    color=probes(r["surf"]["PIX0"], 16, 16, PTS, "<4f") if "PIX0" in r["surf"] else None)
voff = cv["main_off"]
# positive control in the SAME dimension: move v0's vary_store out_slot 0x80->0xa0
r2 = r3.render([(voff + 104 + 32 + 4, "a0")], timeout=25)
rep["c_vary4_posctl_outslot"] = dict(status=r2["status"], err=r2.get("error", "")[:150],
    color=probes(r2["surf"]["PIX0"], 16, 16, PTS, "<4f") if "PIX0" in r2["surf"] else None)
# vary_slot.slot 0x00 -> 0xff at vertex offset 28+3
r4 = r3.render([(voff + 31, "ff")], timeout=25)
rep["c_vary4_varyslot_slot_ff"] = dict(status=r4["status"], err=r4.get("error", "")[:150],
    color=probes(r4["surf"]["PIX0"], 16, 16, PTS, "<4f") if "PIX0" in r4["surf"] else None)
r3.close()

print(json.dumps(rep, indent=1))
