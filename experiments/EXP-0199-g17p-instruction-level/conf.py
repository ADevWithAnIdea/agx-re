#!/usr/bin/env python3
"""conf.py -- EXP-0199 AMENDMENT-01 confirmation driver.  Runs ON THE NEO.

Adds, relative to run.py, exactly the three things RE_EXPERIMENT_PROCESS_CORRECTIONS
requires and the original contract lacked:

  GATE A  every case records the ACTUAL bytes present in the dispatched file
          (printed by the runner from the file re-read off disk), an INDEPENDENT
          decode of the swept value out of those bytes, the program hash, and the
          db/harness revisions -- and asserts requested == decoded BEFORE the
          observation is allowed to count.
  GATE C  a per-case prediction from each pre-registered competing model, computed
          by analysis/predictor.py and written to disk BEFORE the run reads any
          output.
  GATE E  shuffled / reversed case order, plus a sampled measurement of concurrent
          GPU activity (the machine cannot be made quiet on this project).

    python3 conf.py g17p_conf01 shuffle
    python3 conf.py g17p_conf02 reverse

CLEAN-ROOM: drives our own runners over shaders compiled from our own MSL.
"""
import collections
import hashlib
import json
import os
import random
import struct
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "harness2"))
sys.path.insert(0, os.path.join(HERE, "analysis"))
from runner199 import ComputeRunner, RenderRunner          # noqa: E402
import predictor as PRED                                    # noqa: E402

CONTRACT = json.load(open(os.path.join(HERE, "CAPTURE_CONTRACT-AMENDMENT-01.json")))
CAR = CONTRACT["carriers"]
PTS = [tuple(p) for p in CONTRACT["probe_pixels"]]
POISON32 = 0xDEADBEEF
SEED = 20260830
AGXPARSE = os.path.expanduser("~/agxre/tools/shdump/agxparse.py")
ISADIR = os.path.expanduser("~/agxre/tools/agx-isa")
sys.path.insert(0, ISADIR)
try:
    import isadb
except Exception:                                    # pragma: no cover
    isadb = None


def sha256_file(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def md5_file(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


class Sink:
    def __init__(self, path):
        self.f = open(path, "a")

    def write(self, rec):
        self.f.write(json.dumps(rec, separators=(",", ":")) + "\n")
        self.f.flush()
        os.fsync(self.f.fileno())


def sample_concurrency(path, stop):
    """GATE E: the machine's business is MEASURED, not asserted."""
    f = open(path, "a")
    while not stop.is_set():
        try:
            out = subprocess.check_output(
                ["ps", "-Ao", "pid,pcpu,comm"], text=True, timeout=10)
            rows = [l.split(None, 2) for l in out.splitlines()[1:]]
            busy = [r for r in rows if len(r) == 3 and float(r[1]) > 5.0]
            f.write(json.dumps({"t": round(time.time(), 2),
                                "busy": [[r[0], r[1], r[2][-40:]] for r in busy][:20],
                                "n_gfrun": sum(1 for r in rows if "gfrun" in r[-1]),
                                "n_crun": sum(1 for r in rows if "crun" in r[-1]),
                                "n_agxrun": sum(1 for r in rows if "agxrun" in r[-1])},
                               separators=(",", ":")) + "\n")
            f.flush()
        except Exception:
            pass
        stop.wait(5)
    f.close()


# ------------------------------------------------------------- observation ---
A_IN = [(0x9E3779B9 * (i + 1)) & 0xFFFFFFFF for i in range(32)]
C_ORACLE = [((((A_IN[i] * 3 + i * 7 + 11) & 0xFFFFFFFF) ^ 0x13579BDF)
             + 0x2468ACE0) & 0xFFFFFFFF for i in range(32)]
C_SENT = [(0xA5A50000 + i) & 0xFFFFFFFF for i in range(32)]


def score_compute(r):
    st = r["status"]
    if st == "MALFORMED":
        return "measurement_failed", {"raw": r.get("raw", [])[:6]}
    if st == "HANG":
        return "hang", {"err": r.get("error", "")[:120]}
    if st != "OK":
        return "fault", {"st": st, "err": r.get("error", "")[:160],
                         "errdom": r.get("errdom", "")}
    o = r["surf"].get("OUT0", b"")
    if len(o) != 512:
        return "measurement_failed", {"len": len(o)}
    v = list(struct.unpack("<128I", o))
    comp, sent, mid, tail = v[:32], v[64:96], v[32:64], v[96:128]
    obs = {"h": hashlib.sha256(o).hexdigest()[:24], "f2": [v[0], v[1]],
           "poison_guard": all(x == POISON32 for x in mid + tail)}
    if sent != C_SENT:
        return ("never_ran" if all(x == POISON32 for x in sent) else "wrong_value"), obs
    if comp == C_ORACLE:
        return "ok", obs
    if all(x == POISON32 for x in comp):
        return "halted_poison", obs
    if all(x == 0 for x in comp):
        return "zero", obs
    return "wrong_value", obs


def pxf(buf, w, bpp, fmt, pts):
    return [[round(x, 6) for x in struct.unpack_from(fmt, buf, (y * w + x0) * bpp)]
            for (x0, y) in pts]


def _diffsum(buf, basebuf, bpp, comp):
    """Exact difference counts against the baseline surface -- required so a
    semantic claim can quote numerators, not a hash inequality."""
    n = len(buf) // bpp
    d = sum(1 for i in range(n)
            if buf[i * bpp:(i + 1) * bpp] != basebuf[i * bpp:(i + 1) * bpp])
    vals = collections.Counter(
        round(struct.unpack_from("<f", buf, i * bpp)[0], 6) for i in range(n))
    return d, sorted(vals.items(), key=lambda kv: -kv[1])[:6]


def score_depth(r, base, car):
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
    obs = {"col": pxf(p, 16, 16, "<4f", PTS), "dep": pxf(d, 16, 4, "<1f", PTS),
           "ph": hashlib.sha256(p).hexdigest()[:24],
           "dh": hashlib.sha256(d).hexdigest()[:24]}
    if p[:4] == b"\xef\xbe\xad\xde" and p == b"\xef\xbe\xad\xde" * (len(p) // 4):
        return "poison", obs
    clr = [round(x, 6) for x in CAR[car]["clear_color"]]
    if (all(c == clr for c in obs["col"])
            and all(abs(dd[0] - CAR[car]["depth_clear"]) < 1e-6 for dd in obs["dep"])):
        return "tile_discarded", obs
    cm, dm = obs["ph"] != base["ph"], obs["dh"] != base["dh"]
    if base.get("pbuf") is not None:
        obs["n_pix_diff"], obs["col_r_hist"] = _diffsum(p, base["pbuf"], 16, 0)
        obs["n_dep_diff"], obs["dep_hist"] = _diffsum(d, base["dbuf"], 4, 0)
    return (("both_moved" if cm else "depth_moved") if dm else
            ("color_moved" if cm else "ok")), obs


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
    obs = {"rgba": pxf(p, 16, 16, "<4f", PTS),
           "ph": hashlib.sha256(p).hexdigest()[:24]}
    if p[:4] == b"\xef\xbe\xad\xde" and p == b"\xef\xbe\xad\xde" * (len(p) // 4):
        return "poison", obs
    clr = [round(x, 6) for x in CAR["c_vary4"]["clear_color"]]
    if all(c == clr for c in obs["rgba"]):
        return "draw_gone", obs
    if obs["ph"] == base["ph"]:
        return "ok", obs
    if base.get("pbuf") is not None:
        obs["n_pix_diff"], obs["col_r_hist"] = _diffsum(p, base["pbuf"], 16, 0)
    want = [1000.0, 2000.0, 3000.0, 4000.0]
    got = obs["rgba"][0]
    moved = [i for i in range(4) if abs(got[i] - want[i]) > 1e-3]
    picked = {str(i): j for i in moved for j in range(4)
              if j != i and abs(got[i] - want[j]) < 1e-3}
    obs["moved_ch"], obs["relocated"] = moved, picked
    return ("relocated" if picked else "moved"), obs


# ------------------------------------------------------------------- main ----
def main():
    run_id, order = sys.argv[1], sys.argv[2]
    rawdir = os.path.join(HERE, "raw", run_id)
    os.makedirs(rawdir, exist_ok=True)
    W = os.path.join(HERE, "work")

    hashes = {rel: sha256_file(os.path.join(HERE, rel))
              for rel in CONTRACT["frozen_archive_sha256"]}
    bad = [k for k, v in hashes.items() if v != CONTRACT["frozen_archive_sha256"][k]]
    harness_md5 = {p: md5_file(os.path.join(HERE, p)) for p in
                   ("harness2/crun199.m", "harness2/gfrun5.m", "harness2/runner199.py")}
    db_sha = sha256_file(os.path.join(ISADIR, "db.json"))
    json.dump({"run_id": run_id, "order": order, "seed": SEED,
               "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "archive_sha256": hashes, "archive_hash_mismatch": bad,
               "harness_md5": harness_md5, "db_sha256": db_sha},
              open(os.path.join(rawdir, "00_inputs.json"), "w"), indent=1)
    if bad:
        print("FROZEN ARCHIVE HASH MISMATCH", bad)
        return 2

    def mainhex(f, stage=None):
        a = ["python3", AGXPARSE, os.path.join(W, f), "--extract-hex"]
        if stage:
            a[3:3] = ["--stage", stage]
        return bytes.fromhex(subprocess.check_output(a, text=True).strip())

    M3 = mainhex("k_line3.bin")
    FD = mainhex("c_depth.bin", "fragment")
    FD2 = mainhex("c_depth2.bin", "fragment")
    VX = mainhex("c_vary4.bin", "vertex")
    off3 = CAR["k_line3"]["main_off"]
    cd, cd2 = CAR["c_depth"]["frag_main_off"], CAR["c_depth2"]["frag_main_off"]
    cv = CAR["c_vary4"]["vtx_main_off"]
    assert len(M3) == 122 and len(FD) == 208 and len(FD2) == 226 and len(VX) == 172

    cases = PRED.build_cases(M3, off3, FD, cd, FD2, cd2, VX, cv)
    if order == "shuffle":
        random.Random(SEED).shuffle(cases)
    elif order == "reverse":
        random.Random(SEED).shuffle(cases)
        cases.reverse()
    print("cases %d order %s" % (len(cases), order))

    # GATE C: predictions written BEFORE any output is read.
    preds = {c["case"]: PRED.predict(c) for c in cases}
    json.dump(preds, open(os.path.join(HERE, "analysis",
                                       "predictions_%s.json" % run_id), "w"), indent=1)
    print("predictions written for %d cases" % len(preds))

    stop = threading.Event()
    th = threading.Thread(target=sample_concurrency,
                          args=(os.path.join(rawdir, "concurrency.jsonl"), stop),
                          daemon=True)
    th.start()

    R = {}

    def get(kind):
        if kind in R:
            return R[kind]
        if kind == "comp":
            R[kind] = ComputeRunner(
                os.path.join(HERE, "harness2/crun199"),
                os.path.join(HERE, "kernels/k_line3.metal"), "k_line3",
                os.path.join(W, "k_line3.bin"),
                os.path.join(W, "sc_%s_kl3.bin" % run_id),
                os.path.join(W, "k_line_in.bin"), 512, 32, 32,
                ledger=["%d:%d" % (off3 + B, 8)
                        for B in CAR["k_line3"]["insertion_boundaries_used"]])
        elif kind in ("depth", "depth2"):
            c = "c_depth" if kind == "depth" else "c_depth2"
            cfg = dict(color_format=125, width=16, height=16, depth=True,
                       depth_clear=CAR[c]["depth_clear"],
                       depth_compare=CAR[c]["depth_compare"],
                       clear=CAR[c]["clear_color"],
                       ledger=["%d:%d" % (CAR[c]["frag_main_off"]
                                          + CAR[c]["anchor_frag_depth_store_off"], 8),
                               "%d:%d" % (CAR[c]["frag_main_off"] + 48, 8)]
                       if kind == "depth" else
                       ["%d:%d" % (CAR[c]["frag_main_off"]
                                   + CAR[c]["anchor_frag_depth_store_off"], 8)])
            R[kind] = RenderRunner(os.path.join(HERE, "harness2/gfrun5"),
                                   os.path.join(HERE, "kernels/%s.metal" % c),
                                   os.path.join(W, "%s.bin" % c),
                                   os.path.join(W, "sc_%s_%s.bin" % (run_id, kind)), cfg)
        else:
            cfg = dict(color_format=125, width=16, height=16,
                       clear=CAR["c_vary4"]["clear_color"],
                       ledger=["%d:%d" % (cv + 28, 8),
                               "%d:%d" % (cv + 136, 8)])
            R[kind] = RenderRunner(os.path.join(HERE, "harness2/gfrun5"),
                                   os.path.join(HERE, "kernels/c_vary4.metal"),
                                   os.path.join(W, "c_vary4.bin"),
                                   os.path.join(W, "sc_%s_cv.bin" % run_id), cfg)
        return R[kind]

    def fire(kind, spl):
        r = get(kind)
        return r.run(spl, timeout=20) if kind == "comp" else r.render(spl, timeout=25)

    base = {}
    sink = Sink(os.path.join(rawdir, "sweep.jsonl"))
    for kind in ("comp", "depth", "depth2", "vary"):
        if not any(c["kind"] == kind for c in cases):
            continue
        # A baseline that is not `ok` is a MEASUREMENT FAILURE on a shared device,
        # never a hardware result.  Retry, and if it still will not come back
        # clean, abort the run and let it be RETAINED and replaced under a NEW id
        # rather than scoring 6507 cases against a broken reference.
        for attempt in range(6):
            r = fire(kind, [])
            if r["status"] == "OK" and "PIX0" in r["surf"] or \
               (kind == "comp" and r["status"] == "OK"):
                break
            sink_pre = dict(arm="_", case="BASELINE_RETRY_%s_%d" % (kind, attempt),
                            kind=kind, outcome="measurement_failed",
                            observed={}, status=r["status"],
                            error=r.get("error", "")[:200], splice=[])
            Sink(os.path.join(rawdir, "sweep.jsonl")).write(sink_pre)
            time.sleep(2.0 * (attempt + 1))
        if kind == "comp":
            oc, ob = score_compute(r)
        elif kind.startswith("depth"):
            oc, ob = score_depth(r, {"ph": None, "dh": None},
                                 "c_depth" if kind == "depth" else "c_depth2")
            # the baseline is its OWN reference: `moved` is meaningless here, so
            # only a fault / poison / tile-discard makes it unusable.
            if oc in ("both_moved", "depth_moved", "color_moved"):
                oc = "ok"
        else:
            oc, ob = score_vary(r, {"ph": None})
            if oc in ("moved", "relocated"):
                oc = "ok"
        if oc != "ok":
            sink.write(dict(arm="_", case="BASELINE_FAILED_" + kind, kind=kind,
                            outcome=oc, observed=ob, status=r["status"],
                            error=r.get("error", "")[:200], splice=[]))
            print("BASELINE %s NOT ok (%s) -- aborting; retain this run id and "
                  "capture the replacement under a NEW id" % (kind, oc))
            stop.set()
            return 3
        base[kind] = dict(ob)
        base[kind]["pbuf"] = r["surf"].get("PIX0")
        base[kind]["dbuf"] = r["surf"].get("DEPTH")
        # the full baseline surfaces are retained ONCE per run as raw evidence
        ob = dict(ob)
        if r["surf"].get("DEPTH"):
            ob["depth_full_hex"] = r["surf"]["DEPTH"].hex()
        if r["surf"].get("PIX0"):
            ob["pix0_full_hex"] = r["surf"]["PIX0"].hex()
        sink.write(dict(arm="_", case="BASELINE_" + kind, kind=kind, outcome=oc,
                        observed=ob, status=r["status"], splice=[],
                        actual={str(k): v.hex() for k, v in r.get("actual", {}).items()}))
        print("baseline %s: %s %s" % (kind, oc, json.dumps(ob)[:150]))

    hangs, stopped, n, t0 = {}, set(), 0, time.time()
    for c in cases:
        if c["arm"] in stopped:
            continue
        n += 1
        r = fire(c["kind"], c["splice"])
        kind = c["kind"]
        if kind == "comp":
            oc, ob = score_compute(r)
        elif kind.startswith("depth"):
            oc, ob = score_depth(r, base[kind],
                                 "c_depth" if kind == "depth" else "c_depth2")
        else:
            oc, ob = score_vary(r, base[kind])
        actual = {str(k): v.hex() for k, v in r.get("actual", {}).items()}
        led = PRED.check_ledger(c, actual)          # GATE A
        if not led["ok"]:
            oc = "invalid_ledger"
        sink.write(dict(arm=c["arm"], case=c["case"], kind=kind, order_index=n,
                        instr=c.get("instr"), field=c.get("field"),
                        value=c.get("value"), site=c.get("site"),
                        role=c.get("role"), carrier=c.get("carrier"),
                        splice=c["splice"], req_bytes=c.get("req_bytes"),
                        actual=actual, ledger=led,
                        prediction=preds[c["case"]],
                        outcome=oc, observed=ob, status=r["status"],
                        errdom=r.get("errdom", ""), error=r.get("error", "")[:200],
                        restarts=get(kind).restarts,
                        foreign_retries=r.get("foreign_retries", 0),
                        t=round(time.time(), 3)))
        if oc == "hang":
            hangs[c["arm"]] = hangs.get(c["arm"], 0) + 1
            print("  HANG %s %s (%d)" % (c["arm"], c["case"], hangs[c["arm"]]))
            if hangs[c["arm"]] >= 6:
                stopped.add(c["arm"])
                print("  ARM %s STOPPED (hang budget)" % c["arm"])
        if n % 500 == 0:
            print("[%d/%d] %.0fs" % (n, len(cases), time.time() - t0))
    stop.set()
    for r in R.values():
        r.close()
    json.dump(dict(cases=n, seconds=round(time.time() - t0, 1), hangs=hangs,
                   stopped=sorted(stopped), order=order,
                   finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
              open(os.path.join(rawdir, "05_run_manifest.json"), "w"), indent=1)
    print("DONE %d in %.0fs hangs=%s" % (n, time.time() - t0, hangs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
