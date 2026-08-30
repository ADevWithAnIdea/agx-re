#!/usr/bin/env python3
"""EXP-0161 gated-run driver (G17P).

  python3 harness/run.py --run g17p_YYYYMMDD_runNN [--arms A,B] [--order reverse]
  python3 harness/run.py --run ... --danger        # lease-only fspecial arm

Per case: build the mutated program, dispatch it once, and append one
FIELD-SWEEP-PROTOCOL section-4 record immediately (flush + fsync).

Safety / anti-contamination (FIELD-SWEEP-PROTOCOL sections 7 and 7A, binding):
  * majority-of-3 before any `fault`/`hang` is written to a record;
  * the OS fault-classification string is recorded verbatim on every non-OK
    case, and `...ErrorInnocentVictim`-class failures are flagged `victim`;
  * the read-back buffer is POISONED with 0xDEADBEEF+i before every dispatch,
    so an unwritten word identifies itself and a suspect fault can be
    adjudicated offline from the committed digest;
  * the unmutated baseline is re-validated every BASELINE_EVERY cases; a
    baseline failure restarts the child runner rather than logging a cascade;
  * NO `fault`/`hang` verdict is promoted from this run -- section 7A requires
    lease confirmation, which harness/adjudicate.py performs separately.
"""
from __future__ import print_function

import argparse
import json
import math
import platform
import struct
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H      # noqa: E402
import sweeprun as S         # noqa: E402
import cases as CM           # noqa: E402

BASELINE_EVERY = 250
RETRIES = 3
REQ_TIMEOUT = 8.0
DANGER_TIMEOUT = 12.0        # EXP-0138's watchdog, so a hang is comparable


def sh(cmd):
    try:
        return subprocess.check_output(cmd, shell=True,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "?"


def env_block(device, extra):
    d = {
        "target": "G17P",
        "device": device,
        "host": platform.node(),
        "os": sh("sw_vers -productVersion") + " (" + sh("sw_vers -buildVersion") + ")",
        "machine": sh("sysctl -n hw.model"),
        "python": sys.version.split()[0],
        "db_sha256": sh("shasum -a 256 %s | cut -d' ' -f1" % (H.ISA_DIR / "db.json")),
        "isadb_sha256": sh("shasum -a 256 %s | cut -d' ' -f1" % (H.ISA_DIR / "isadb.py")),
        "persistrun_sha256": sh("shasum -a 256 %s | cut -d' ' -f1"
                                % (S.TOOLS / "agxtest" / "persistrun.py")),
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    d.update(extra)
    return d


# ---------------------------------------------------------------------------
# per-arm carriers
# ---------------------------------------------------------------------------
def make_carrier(arm, workdir, timeout):
    if arm["style"] == "synth":
        return S.Carrier(EXP / "kernels" / "carrier_seed.metal", "k",
                         workdir, timeout=timeout, fast_math=False,
                         inputs={0: ("poison_synth.bin", CM.poison(H.OUT_WORDS)),
                                 1: ("seedbuf.bin", H.seed_buffer_bytes())},
                         outs={0: H.OUT_WORDS * 4}), dict(grid=1, tg=1)
    c = CM.CARRIERS[arm["carrier"]]
    return S.Carrier(EXP / "kernels" / "probes.metal", c["func"], workdir,
                     timeout=timeout, fast_math=c["fast_math"],
                     inputs=c["inputs"], outs=c["outs"]), \
        dict(grid=c["grid"], tg=c["tg"])


def decode_out(carrier_cfg, outs):
    raw = outs.get(carrier_cfg["out_idx"], b"")
    if not raw:
        return None
    dt = carrier_cfg["dtype"]
    if dt == "u32":
        return [struct.unpack_from("<I", raw, i)[0]
                for i in range(0, len(raw) - 3, 4)]
    if dt == "u64":
        return [struct.unpack_from("<Q", raw, i)[0]
                for i in range(0, len(raw) - 7, 8)]
    if dt == "f32":
        return [struct.unpack_from("<f", raw, i)[0]
                for i in range(0, len(raw) - 3, 4)]
    raise ValueError(dt)


def close_enough(got, oracle, tol):
    if got is None or len(got) != len(oracle):
        return False
    if tol is None:
        return got == oracle
    for g, o in zip(got, oracle):
        if g != g:                       # NaN
            return False
        if abs(g - o) > tol * max(1.0, abs(o)):
            return False
    return True


def poison_view(carrier_cfg):
    """The poison words as seen through the carrier's own element type."""
    n = carrier_cfg["outs"][carrier_cfg["out_idx"]] // 4
    w = [CM.POISON_WORD(i) for i in range(n)]
    dt = carrier_cfg["dtype"]
    if dt == "u32":
        return w
    if dt == "u64":
        return [w[i] | (w[i + 1] << 32) for i in range(0, n - 1, 2)]
    if dt == "f32":
        return [struct.unpack("<f", struct.pack("<I", v))[0] for v in w]
    raise ValueError(dt)


def classify(arm, status, outs, base, carrier_cfg):
    """Returns (outcome, observation-dict)."""
    if status == "HANG":
        return "hang", None
    if status != "OK":
        return "fault", None
    if arm["style"] == "synth":
        words = S.words_u32(outs.get(0, b""))
        d = S.digest(words)
        if d is None:
            return "undecodable", None
        return S.classify_synth("OK", d, base), {
            "digest": S.digest_hex(d), "regs": d["regs"],
            "pre": d["pre"], "post": d["post"]}
    got = decode_out(carrier_cfg, outs)
    if got is None:
        return "undecodable", None
    pv = poison_view(carrier_cfg)
    npois = sum(1 for g, p in zip(got, pv) if g == p
                or (isinstance(g, float) and isinstance(p, float)
                    and struct.pack("<f", g) == struct.pack("<f", p)))
    obs = {"out": [("%.9g" % g) if isinstance(g, float) else g for g in got],
           "poison_words": npois}
    if close_enough(got, carrier_cfg["oracle"], carrier_cfg["tol"]):
        return "ok", obs
    if npois == len(got):
        return "silent_zero", obs        # nothing written at all
    if all((g == 0 or (isinstance(g, float) and g == 0.0)) for g in got):
        return "silent_zero", obs
    return "wrong_value", obs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--arms", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--order", default="forward", choices=("forward", "reverse"))
    ap.add_argument("--danger", action="store_true")
    ap.add_argument("--supp", action="store_true")
    ap.add_argument("--supp2", action="store_true")
    a = ap.parse_args()

    rundir = EXP / "raw" / a.run
    rundir.mkdir(parents=True, exist_ok=True)
    rep = json.loads((EXP / "work" / "anchors" / "anchor_report.json").read_text())

    if a.danger:
        arms = [CM.DANGER_ARM]
        allcases = CM.build_cases(rep, arms=[], include_danger=True)
        timeout = DANGER_TIMEOUT
    elif a.supp2:
        arms = list(CM.SUPP2_ARMS)
        allcases = CM.build_cases(rep, arms=arms)
        timeout = REQ_TIMEOUT
    elif a.supp:
        arms = list(CM.SUPP_ARMS)
        allcases = CM.build_cases(rep, arms=arms)
        timeout = REQ_TIMEOUT
    else:
        arms = list(CM.ARMS)
        allcases = CM.build_cases(rep)
        timeout = REQ_TIMEOUT
    armdefs = dict((x["arm"], x) for x in arms)

    if a.arms:
        want = set(a.arms.split(","))
        allcases = [c for c in allcases if c["arm"] in want]
    if a.order == "reverse":
        order = []
        for c in allcases:
            if not order or order[-1] != c["arm"]:
                order.append(c["arm"])
        rank = dict((n, -i) for i, n in enumerate(order))
        allcases = sorted(allcases, key=lambda c: (rank[c["arm"]], c["idx"]))
    if a.limit:
        allcases = allcases[:a.limit]

    done = set()
    jl = rundir / "sweep.jsonl"
    if jl.exists():
        for ln in jl.open():
            try:
                done.add(json.loads(ln)["idx"])
            except Exception:
                pass
        print("resume: %d cases already recorded" % len(done))

    log = S.Log(jl)
    blog = S.Log(rundir / "baseline.jsonl")
    counters = dict(ok=0, silent_zero=0, wrong_value=0, fault=0, hang=0,
                    undecodable=0, victim=0, sentinel_bad=0, baseline_fail=0)
    genuine_hangs = {}
    t0 = time.time()
    n = 0
    envw = False

    # group by arm, preserving the (possibly reversed) matrix order
    groups = []
    for c in allcases:
        if not groups or groups[-1][0] != c["arm"]:
            groups.append((c["arm"], []))
        groups[-1][1].append(c)

    for armname, cs in groups:
        arm = armdefs[armname]
        cs = [c for c in cs if c["idx"] not in done]
        if not cs:
            continue
        wd = EXP / "work" / ("run_%s_%s" % (a.run, armname))
        car, disp = make_carrier(arm, wd, timeout)
        ccfg = CM.CARRIERS.get(arm.get("carrier", ""), None)
        if not envw:
            (rundir / "00_env.json").write_text(json.dumps(
                env_block(car.device, {"matrix_sha256": CM.matrix_sha256(allcases),
                    "order": a.order, "danger": a.danger, "supp": a.supp}),
                indent=1, sort_keys=True))
            envw = True
        base_bytes = None
        for c in cs:
            if c["field"] == "__baseline":
                base_bytes = bytes.fromhex(c["bytes"])
        if base_bytes is None:
            base_bytes = bytes.fromhex(
                [x for x in allcases if x["arm"] == armname
                 and x["field"] == "__baseline"][0]["bytes"])

        def dispatch(blk):
            if arm["style"] == "synth":
                prog = H.synth_program(arm["kind"], blk, car.region_len)
                return car.run_program(prog, **disp)
            return car.run_inplace(0, blk, **disp)

        def get_baseline(force=False):
            for att in range(8):
                resp, outs = dispatch(base_bytes)
                if resp["status"] == "OK":
                    break
                if S.is_victim(resp["error"]):
                    time.sleep(4.0 * (att + 1))
                    if att == 3:
                        car.restart()
                else:
                    break
            if arm["style"] == "synth":
                d = S.digest(S.words_u32(outs.get(0, b""))) \
                    if resp["status"] == "OK" else None
                bstate = d
                bhex = S.digest_hex(d) if d else None
            else:
                got = decode_out(ccfg, outs) if resp["status"] == "OK" else None
                bstate = got
                bhex = json.dumps(["%.9g" % g if isinstance(g, float) else g
                                   for g in got]) if got else None
            blog.write({"arm": armname, "status": resp["status"],
                        "error": resp["error"], "digest": bhex,
                        "kind": "refresh" if force else "initial",
                        "oracle_match": (
                            None if arm["style"] == "synth" else
                            close_enough(bstate, ccfg["oracle"], ccfg["tol"]))})
            return bstate

        base = get_baseline()
        print("[%s] arm %-18s baseline %s  (%d cases)"
              % (time.strftime("%H:%M:%S"), armname,
                 "OK" if base is not None else "FAILED", len(cs)))
        if base is None:
            counters["baseline_fail"] += 1

        stop_arm = False
        for c in cs:
            if stop_arm:
                break
            blk = bytes.fromhex(c["bytes"])
            rt_ok = H.round_trips(
                blk[c["ioff"]:c["ioff"] + CM.INS[c["instr"]]["length"]]
                if arm["style"] == "inplace" else blk)
            attempts = []
            outcome, obs = None, None
            for k in range(RETRIES):
                resp, outs = dispatch(blk)
                oc, o = classify(arm, resp["status"], outs, base, ccfg)
                attempts.append({"status": resp["status"], "outcome": oc,
                                 "error": resp["error"],
                                 "victim": S.is_victim(resp["error"])})
                if oc in ("ok", "silent_zero", "wrong_value"):
                    outcome, obs = oc, o
                    break
                if k == RETRIES - 1:
                    bad = [x["outcome"] for x in attempts]
                    outcome, obs = max(set(bad), key=bad.count), o
            victim = any(x["victim"] for x in attempts)
            sent_bad = False
            if arm["style"] == "synth" and obs:
                sent_bad = (obs.get("pre") != H.expected_pre()
                            or obs.get("post") != H.SENT_POST)
            counters[outcome] = counters.get(outcome, 0) + 1
            if victim:
                counters["victim"] += 1
            if sent_bad:
                counters["sentinel_bad"] += 1

            rec = {"idx": c["idx"], "arm": armname, "style": arm["style"],
                   "instr": c["instr"], "field": c["field"], "value": c["value"],
                   "bytes": (blk[c["ioff"]:c["ioff"] + CM.INS[c["instr"]]["length"]].hex()),
                   "observed": obs, "outcome": outcome,
                   "carrier": ("SYNTH+LIFTED:%s@%s+%d" % (c["probe"], c["instr"], c["ioff"])
                               if arm["style"] == "synth"
                               else "INPLACE:%s@%s+%d" % (c["carrier"], c["instr"], c["ioff"])),
                   "kind": c.get("kind", ""), "rt_ok": rt_ok, "victim": victim,
                   "sentinel_bad": sent_bad, "attempts": attempts,
                   "predict": c.get("predict", ""),
                   "byte_index": c.get("byte_index"),
                   "fstart": c.get("fstart"), "fwidth": c.get("fwidth"),
                   "note": ""}
            log.write(rec)
            n += 1

            if outcome == "hang" and not victim:
                genuine_hangs[armname] = genuine_hangs.get(armname, 0) + 1
                print("  !! GENUINE HANG %d in %s at %s=%s"
                      % (genuine_hangs[armname], armname, c["field"], c["value"]))
                if genuine_hangs[armname] >= 2:
                    print("  !! STOP-RULE: two genuine hangs in %s -- arm STOPPED "
                          "(FIELD-SWEEP-PROTOCOL section 8)" % armname)
                    (rundir / ("STOPPED_%s.json" % armname)).write_text(
                        json.dumps({"arm": armname, "reason": "two genuine hangs",
                                    "last_case": c["idx"], "field": c["field"],
                                    "value": c["value"]}, indent=1))
                    stop_arm = True

            if n % BASELINE_EVERY == 0:
                d = get_baseline(force=True)
                if d is None or (base is not None and d != base):
                    print("  !! baseline drift/failure at n=%d arm=%s -- restarting"
                          % (n, armname))
                    counters["baseline_fail"] += 1
                    car.restart()
                    base = get_baseline(force=True)
            if n % 1000 == 0:
                el = time.time() - t0
                print("  %6d  %.1f case/s  %s"
                      % (n, n / max(el, 1e-9), json.dumps(counters, sort_keys=True)))
                (rundir / "01_progress.json").write_text(json.dumps(
                    {"done": n, "counters": counters, "elapsed_s": round(el, 1),
                     "arm": armname}, indent=1, sort_keys=True))
        car.close()

    (rundir / "02_summary.json").write_text(json.dumps(
        {"cases": n, "counters": counters, "genuine_hangs": genuine_hangs,
         "elapsed_s": round(time.time() - t0, 1)}, indent=1, sort_keys=True))
    log.close()
    blog.close()
    print("DONE", n, json.dumps(counters, sort_keys=True))


if __name__ == "__main__":
    main()
