#!/usr/bin/env python3
"""run.py -- EXP-0199 gated run driver.  Runs ON THE NEO under ~/agxre/EXP-0199.

Executes the frozen case matrix of CAPTURE_CONTRACT.json and appends ONE JSON
object per case to raw/<run_id>/sweep.jsonl, flushed immediately, so a kill costs
at most one case.  Nothing is buffered to be written at the end.

    python3 run.py <run_id> [--arms A,B,C,D,E]

CLEAN-ROOM: drives our own runners over shaders compiled from our own MSL.
"""
import hashlib
import json
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "harness"))
from runner199 import ComputeRunner, RenderRunner          # noqa: E402

CONTRACT = json.load(open(os.path.join(HERE, "CAPTURE_CONTRACT.json")))
CAR = CONTRACT["carriers"]
PTS = [tuple(p) for p in CONTRACT["probe_pixels"]]
POISON32 = 0xDEADBEEF
HANG_BUDGET = CONTRACT["hang_policy"]["per_arm_budget"]
HEALTH_EVERY = CONTRACT["gate"]["health_check_every_n_cases"]


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


class Sink:
    def __init__(self, path):
        self.f = open(path, "a")
        self.n = 0

    def write(self, rec):
        rec["t"] = round(time.time(), 3)
        self.f.write(json.dumps(rec, separators=(",", ":")) + "\n")
        self.f.flush()
        os.fsync(self.f.fileno())
        self.n += 1


# ----------------------------------------------------------------- compute ---
KL = CAR["k_line3"]
A_IN = [(0x9E3779B9 * (i + 1)) & 0xFFFFFFFF for i in range(32)]
C_ORACLE = [((((A_IN[i] * 3 + i * 7 + 11) & 0xFFFFFFFF) ^ 0x13579BDF)
             + 0x2468ACE0) & 0xFFFFFFFF for i in range(32)]
C_SENT = [(0xA5A50000 + i) & 0xFFFFFFFF for i in range(32)]


def score_compute(r):
    """-> (outcome, observed)."""
    st = r["status"]
    if st == "MALFORMED":
        return "measurement_failed", {"raw": r.get("raw", [])[:6]}
    if st == "HANG":
        return "hang", {"err": r.get("error", "")[:120]}
    if st == "CMDBUF_ERROR":
        return "fault", {"err": r.get("error", "")[:160],
                         "errdom": r.get("errdom", "")}
    if st != "OK":
        return "fault", {"st": st, "err": r.get("error", "")[:160]}
    o = r["surf"].get("OUT0", b"")
    if len(o) != 512:
        return "measurement_failed", {"len": len(o)}
    v = list(struct.unpack("<128I", o))
    comp, sent = v[:32], v[64:96]
    mid, tail = v[32:64], v[96:128]
    obs = {"h": hashlib.sha256(o).hexdigest()[:24], "f2": [v[0], v[1]],
           "poison_guard": all(x == POISON32 for x in mid + tail)}
    if sent != C_SENT:
        if all(x == POISON32 for x in sent):
            return "never_ran", obs
        return "wrong_value", obs                     # sentinel itself corrupted
    if comp == C_ORACLE:
        return "ok", obs
    if all(x == POISON32 for x in comp):
        return "halted_poison", obs
    if all(x == 0 for x in comp):
        return "zero", obs
    return "wrong_value", obs


# ------------------------------------------------------------------ render ---
def px(buf, w, bpp, fmt, pts):
    return [[round(x, 6) for x in struct.unpack_from(fmt, buf, (y * w + x0) * bpp)]
            for (x0, y) in pts]


def score_depth(r, base):
    st = r["status"]
    if st == "MALFORMED":
        return "measurement_failed", {"raw": r.get("raw", [])[:6]}
    if st == "HANG":
        return "hang", {"err": r.get("error", "")[:120]}
    if st != "OK":
        return "fault", {"st": st, "err": r.get("error", "")[:160],
                         "errdom": r.get("errdom", "")}
    if "PIX0" not in r["surf"] or "DEPTH" not in r["surf"]:
        return "measurement_failed", {"surf": sorted(r["surf"])}
    p, d = r["surf"]["PIX0"], r["surf"]["DEPTH"]
    obs = {"col": px(p, 16, 16, "<4f", PTS), "dep": px(d, 16, 4, "<1f", PTS),
           "ph": hashlib.sha256(p).hexdigest()[:24],
           "dh": hashlib.sha256(d).hexdigest()[:24]}
    if p[:4] == b"\xef\xbe\xad\xde" and p == b"\xef\xbe\xad\xde" * (len(p) // 4):
        return "poison", obs
    cmoved = obs["ph"] != base["ph"]
    dmoved = obs["dh"] != base["dh"]
    clr = CAR["c_depth"]["clear_color"]
    if (all(c == [round(x, 6) for x in clr] for c in obs["col"])
            and all(abs(dd[0] - CAR["c_depth"]["depth_clear"]) < 1e-6 for dd in obs["dep"])):
        return "tile_discarded", obs
    if cmoved and dmoved:
        return "both_moved", obs
    if dmoved:
        return "depth_moved", obs
    if cmoved:
        return "color_moved", obs
    return "ok", obs


def score_vary(r, base):
    st = r["status"]
    if st == "MALFORMED":
        return "measurement_failed", {"raw": r.get("raw", [])[:6]}
    if st == "HANG":
        return "hang", {"err": r.get("error", "")[:120]}
    if st != "OK":
        return "fault", {"st": st, "err": r.get("error", "")[:160],
                         "errdom": r.get("errdom", "")}
    if "PIX0" not in r["surf"]:
        return "measurement_failed", {"surf": sorted(r["surf"])}
    p = r["surf"]["PIX0"]
    obs = {"rgba": px(p, 16, 16, "<4f", PTS),
           "ph": hashlib.sha256(p).hexdigest()[:24]}
    if p[:4] == b"\xef\xbe\xad\xde" and p == b"\xef\xbe\xad\xde" * (len(p) // 4):
        return "poison", obs
    clr = [round(x, 6) for x in CAR["c_vary4"]["clear_color"]]
    if all(c == clr for c in obs["rgba"]):
        return "draw_gone", obs
    if obs["ph"] == base["ph"]:
        return "ok", obs
    # which channels changed, and did any pick up ANOTHER varying's value?
    want = [1000.0, 2000.0, 3000.0, 4000.0]
    got = obs["rgba"][0]
    moved = [i for i in range(4) if abs(got[i] - want[i]) > 1e-3]
    picked = {}
    for i in moved:
        for j in range(4):
            if j != i and abs(got[i] - want[j]) < 1e-3:
                picked[str(i)] = j
    obs["moved_ch"] = moved
    obs["relocated"] = picked
    return ("relocated" if picked else "moved"), obs


# ------------------------------------------------------------ case matrix ----
def build_cases(main3, off3, cdoff, cvoff, FRAGMAIN, VTXMAIN):
    """(arm, case_id, kind, splices, meta) in execution order."""
    C = []

    def ins(B, hx):
        return [(off3 + B, hx + main3[B:].hex())]

    # ---- ARM A : frag_depth_store ---------------------------------------
    A = cdoff + CAR["c_depth"]["anchor_frag_depth_store_off"]
    C.append(("A", "A0_baseline", "depth", [], {}))
    C.append(("A", "A0_identity", "depth", [(cdoff, FRAGMAIN.hex())],
              {"role": "falsifier_F1"}))
    C.append(("A", "A_F4_byte1_06", "depth", [(A + 1, "06")],
              {"role": "falsifier_F4"}))
    for name, boff in (("b3", 3), ("b4", 4), ("b5", 5),
                       ("byte1", 1), ("byte2", 2)):
        for v in range(256):
            C.append(("A", "A_%s_%02x" % (name, v), "depth",
                      [(A + boff, "%02x" % v)],
                      {"instr": "frag_depth_store", "field": name, "value": v}))
    for v in (0xd7, 0xd6, 0xd5, 0xd3, 0xdf, 0xc7, 0xe7, 0xf7, 0x57, 0x97,
              0x17, 0x77, 0xb7, 0x37, 0x07, 0x67):
        C.append(("A", "A_byte0_%02x" % v, "depth", [(A, "%02x" % v)],
                  {"instr": "frag_depth_store", "field": "byte0", "value": v}))
    for lbl, hx in (("barrier_depth", "070254010000"),
                    ("barrier_color", "0702540c0200"),
                    ("six_pads", "000000000000")):
        C.append(("A", "A_null_" + lbl, "depth", [(A, hx)],
                  {"instr": "frag_depth_store", "field": "_null", "value": lbl}))

    # ---- ARM B : vary_slot ----------------------------------------------
    V = cvoff + CAR["c_vary4"]["anchor_vary_slot_off"]
    C.append(("B", "B0_baseline", "vary", [], {}))
    C.append(("B", "B0_identity", "vary", [(cvoff, VTXMAIN.hex())],
              {"role": "falsifier_F1"}))
    for name, boff in (("slot", 3), ("sel", 1), ("byte0", 0), ("byte2", 2)):
        for v in range(256):
            C.append(("B", "B_%s_%02x" % (name, v), "vary",
                      [(V + boff, "%02x" % v)],
                      {"instr": "vary_slot", "field": name, "value": v}))
    # positive control IN THE SAME DIMENSION: vary_store.out_slot
    for si, so in enumerate(CAR["c_vary4"]["anchor_vary_store_offs"][4:]):
        for v in (0x00, 0x20, 0x40, 0x60, 0x80, 0xa0, 0xc0, 0xe0):
            C.append(("B", "B_posctl_store%d_%02x" % (si + 4, v), "vary",
                      [(cvoff + so + 4, "%02x" % v)],
                      {"instr": "vary_store", "field": "out_slot", "value": v,
                       "role": "positive_control"}))
    C.append(("B", "B_null_4pad", "vary", [(V, "00000000")],
              {"instr": "vary_slot", "field": "_null", "value": "4pad"}))

    # ---- ARM C : sfu_marker insertion -----------------------------------
    BOUND = CAR["k_line3"]["insertion_boundaries_used"]
    C.append(("C", "C0_baseline", "comp", [], {}))
    C.append(("C", "C0_identity", "comp", [(off3, main3.hex())],
              {"role": "falsifier_F1"}))
    C.append(("C", "C0_append_pad", "comp",
              [(off3 + len(main3), "0602")], {"role": "shift_control"}))
    for B in BOUND:
        C.append(("C", "C_sfu0602@%d" % B, "comp", ins(B, "0602"),
                  {"instr": "sfu_marker", "field": "_insert2", "value": "0602",
                   "site": B}))
        for lbl, hx in (("pad0000", "0000"), ("ffff", "ffff")):
            C.append(("C", "C_ctl_%s@%d" % (lbl, B), "comp", ins(B, hx),
                      {"role": "falsifier_F6", "value": hx, "site": B}))
        C.append(("C", "C_del2@%d" % B, "comp",
                  [(off3 + B, main3[B + 2:].hex())],
                  {"role": "falsifier_F2", "site": B}))
    for B in (74, 94):
        for v in range(256):
            C.append(("C", "C_b0_%02x@%d" % (v, B), "comp",
                      ins(B, "%02x02" % v),
                      {"instr": "sfu_marker", "field": "match_byte0", "value": v,
                       "site": B}))
        for v in range(256):
            C.append(("C", "C_b1_%02x@%d" % (v, B), "comp",
                      ins(B, "06%02x" % v),
                      {"instr": "sfu_marker", "field": "match_byte1", "value": v,
                       "site": B}))

    # ---- ARM D : frame_marker_compact insertion --------------------------
    C.append(("D", "D0_baseline", "comp", [], {}))
    for B in BOUND:
        C.append(("D", "D_fmc4_6001_0000@%d" % B, "comp", ins(B, "60010000"),
                  {"instr": "frame_marker_compact", "field": "_insert4",
                   "value": "60010000", "site": B}))
        C.append(("D", "D_fmc2_6001@%d" % B, "comp", ins(B, "6001"),
                  {"instr": "frame_marker_compact", "field": "_insert2",
                   "value": "6001", "site": B}))
        C.append(("D", "D_ctl_4pad@%d" % B, "comp", ins(B, "00000000"),
                  {"role": "falsifier_F6_4byte", "value": "00000000", "site": B}))
    for B in (74, 94):
        for v in range(256):
            if v in (3, 7):
                continue                     # EXP-0172 device-hang hazard
            C.append(("D", "D_b1x4_%02x@%d" % (v, B), "comp",
                      ins(B, "60%02x0000" % v),
                      {"instr": "frame_marker_compact", "field": "b1_in_4byte",
                       "value": v, "site": B}))
    for v in range(256):
        if v in (3, 7):
            continue
        C.append(("D", "D_b1x2_%02x@74" % v, "comp", ins(74, "60%02x" % v),
                  {"instr": "frame_marker_compact", "field": "b1_in_2byte",
                   "value": v, "site": 74}))
    for v in range(256):
        C.append(("D", "D_b2x4_%02x@74" % v, "comp", ins(74, "6001%02x00" % v),
                  {"instr": "frame_marker_compact", "field": "byte2_in_4byte",
                   "value": v, "site": 74}))
    for v in range(256):
        C.append(("D", "D_b3x4_%02x@74" % v, "comp", ins(74, "600100%02x" % v),
                  {"instr": "frame_marker_compact", "field": "byte3_in_4byte",
                   "value": v, "site": 74}))
    for v in (0x60, 0x61, 0x62, 0x64, 0x68, 0x70, 0x40, 0x20, 0xe0, 0x00,
              0x50, 0x63, 0x6f, 0x30, 0xa0, 0xc0):
        C.append(("D", "D_byte0_%02x@74" % v, "comp",
                  ins(74, "%02x010000" % v),
                  {"instr": "frame_marker_compact", "field": "match_byte0",
                   "value": v, "site": 74}))

    # ---- ARM E : n2_op6 ---------------------------------------------------
    N = cdoff + CAR["c_depth"]["anchor_n2_op6_offs"][0]
    N2 = cdoff + CAR["c_depth"]["anchor_n2_op6_offs"][1]
    C.append(("E", "E0_baseline", "depth", [], {}))
    for name, boff in (("byte0", 0), ("opsel", 2), ("imm_sel", 5)):
        for v in range(256):
            C.append(("E", "E_%s_%02x" % (name, v), "depth",
                      [(N + boff, "%02x" % v)],
                      {"instr": "n2_op6", "field": name, "value": v, "site": 48}))
    for v in range(256):
        C.append(("E", "E_i2_byte0_%02x" % v, "depth", [(N2, "%02x" % v)],
                  {"instr": "n2_op6", "field": "byte0", "value": v, "site": 88}))
    C.append(("E", "E_null_barrier", "depth", [(N, "070254010000")],
              {"instr": "n2_op6", "field": "_null", "value": "barrier"}))
    return C


# ------------------------------------------------------------------- main ----
def main():
    run_id = sys.argv[1]
    arms = set(sys.argv[2].replace(",", "")) if len(sys.argv) > 2 else set("ABCDE")
    rawdir = os.path.join(HERE, "raw", run_id)
    os.makedirs(rawdir, exist_ok=True)
    W = os.path.join(HERE, "work")

    # verify the frozen archives before anything runs
    inputs = {"run_id": run_id, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                             time.gmtime()),
              "arms": sorted(arms), "archive_sha256": {}, "hash_ok": True}
    for rel, want in CONTRACT["frozen_archive_sha256"].items():
        got = sha256_file(os.path.join(HERE, rel))
        inputs["archive_sha256"][rel] = got
        if got != want:
            inputs["hash_ok"] = False
    json.dump(inputs, open(os.path.join(rawdir, "00_inputs.json"), "w"), indent=1)
    if not inputs["hash_ok"]:
        print("FROZEN ARCHIVE HASH MISMATCH -- refusing to run")
        return 2

    main3 = None
    import subprocess
    S = os.path.expanduser("~/agxre/tools/shdump/agxparse.py")
    main3 = bytes.fromhex(subprocess.check_output(
        ["python3", S, os.path.join(W, "k_line3.bin"), "--extract-hex"],
        text=True).strip())
    off3 = CAR["k_line3"]["main_off"]
    cdoff = CAR["c_depth"]["frag_main_off"]
    cvoff = CAR["c_vary4"]["vtx_main_off"]

    FRAGMAIN = bytes.fromhex(subprocess.check_output(
        ["python3", S, os.path.join(W, "c_depth.bin"), "--stage", "fragment",
         "--extract-hex"], text=True).strip())
    VTXMAIN = bytes.fromhex(subprocess.check_output(
        ["python3", S, os.path.join(W, "c_vary4.bin"), "--stage", "vertex",
         "--extract-hex"], text=True).strip())
    assert len(FRAGMAIN) == CAR["c_depth"]["frag_main_len"], "frag main len drift"
    assert len(VTXMAIN) == CAR["c_vary4"]["vtx_main_len"], "vtx main len drift"
    assert len(main3) == CAR["k_line3"]["main_len"], "k_line3 main len drift"
    cases = [c for c in build_cases(main3, off3, cdoff, cvoff, FRAGMAIN, VTXMAIN)
             if c[0] in arms]
    print("cases: %d" % len(cases))
    sink = Sink(os.path.join(rawdir, "sweep.jsonl"))

    # runners, created lazily
    R = {}

    def get(kind):
        if kind in R:
            return R[kind]
        if kind == "comp":
            R[kind] = ComputeRunner(
                os.path.join(HERE, "harness/crun199"),
                os.path.join(HERE, "kernels/k_line3.metal"), "k_line3",
                os.path.join(W, "k_line3.bin"),
                os.path.join(W, "sc_%s_kl3.bin" % run_id),
                os.path.join(W, "k_line_in.bin"), 512, 32, 32)
        elif kind == "depth":
            cfg = dict(color_format=125, width=16, height=16, depth=True,
                       depth_clear=CAR["c_depth"]["depth_clear"],
                       depth_compare=CAR["c_depth"]["depth_compare"],
                       clear=CAR["c_depth"]["clear_color"])
            R[kind] = RenderRunner(os.path.join(HERE, "harness/gfrun5"),
                                   os.path.join(HERE, "kernels/c_depth.metal"),
                                   os.path.join(W, "c_depth.bin"),
                                   os.path.join(W, "sc_%s_cd.bin" % run_id), cfg)
        else:
            cfg = dict(color_format=125, width=16, height=16,
                       clear=CAR["c_vary4"]["clear_color"])
            R[kind] = RenderRunner(os.path.join(HERE, "harness/gfrun5"),
                                   os.path.join(HERE, "kernels/c_vary4.metal"),
                                   os.path.join(W, "c_vary4.bin"),
                                   os.path.join(W, "sc_%s_cv.bin" % run_id), cfg)
        return R[kind]

    def fire(kind, spl, timeout=None):
        r = get(kind)
        if kind == "comp":
            return r.run(spl, timeout=timeout or 20)
        return r.render(spl, timeout=timeout or 25)

    # frozen baselines (before any mutation)
    base = {}
    for kind, scorer in (("comp", None), ("depth", None), ("vary", None)):
        if kind == "comp" and not (arms & set("CD")):
            continue
        if kind == "depth" and not (arms & set("AE")):
            continue
        if kind == "vary" and "B" not in arms:
            continue
        r = fire(kind, [])
        if kind == "comp":
            oc, ob = score_compute(r)
        elif kind == "depth":
            ob = {"ph": "", "dh": ""}
            oc, ob = score_depth(r, ob)
        else:
            oc, ob = score_vary(r, {"ph": ""})
        base[kind] = ob
        sink.write(dict(arm="_", case="BASELINE_" + kind, kind=kind, outcome=oc,
                        observed=ob, status=r["status"], splice=[]))
        print("baseline %s: %s %s" % (kind, oc, json.dumps(ob)[:160]))

    hangs = {}
    stopped = set()
    n = 0
    t0 = time.time()
    for (arm, cid, kind, spl, meta) in cases:
        if arm in stopped:
            continue
        n += 1
        if n % HEALTH_EVERY == 0:
            hr = fire(kind, [])
            if kind == "comp":
                hoc, hob = score_compute(hr)
            elif kind == "depth":
                hoc, hob = score_depth(hr, base["depth"])
            else:
                hoc, hob = score_vary(hr, base["vary"])
            sink.write(dict(arm="_", case="HEALTH_%d_%s" % (n, kind), kind=kind,
                            outcome=hoc, observed=hob, status=hr["status"],
                            splice=[]))
            print("[%d/%d %.0fs] health(%s)=%s" %
                  (n, len(cases), time.time() - t0, kind, hoc))
        r = fire(kind, spl)
        if kind == "comp":
            oc, ob = score_compute(r)
        elif kind == "depth":
            oc, ob = score_depth(r, base["depth"])
        else:
            oc, ob = score_vary(r, base["vary"])
        rec = dict(arm=arm, case=cid, kind=kind, outcome=oc, observed=ob,
                   status=r["status"], errdom=r.get("errdom", ""),
                   error=r.get("error", "")[:200], splice=spl,
                   restarts=get(kind).restarts,
                   foreign_retries=r.get("foreign_retries", 0))
        rec.update(meta)
        sink.write(rec)
        if oc == "hang":
            hangs[arm] = hangs.get(arm, 0) + 1
            print("  HANG %s %s (arm total %d)" % (arm, cid, hangs[arm]))
            if hangs[arm] >= HANG_BUDGET:
                stopped.add(arm)
                sink.write(dict(arm=arm, case="ARM_STOPPED_HANG_BUDGET",
                                outcome="stopped", observed={"hangs": hangs[arm]},
                                status="", splice=[]))
                print("  ARM %s STOPPED (hang budget)" % arm)
        if n % 250 == 0:
            print("[%d/%d] %.0fs elapsed" % (n, len(cases), time.time() - t0))
    for r in R.values():
        r.close()
    json.dump(dict(cases=n, seconds=round(time.time() - t0, 1), hangs=hangs,
                   stopped=sorted(stopped),
                   finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
              open(os.path.join(rawdir, "05_run_manifest.json"), "w"), indent=1)
    print("DONE %d cases in %.0fs; hangs=%s" % (n, time.time() - t0, hangs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
