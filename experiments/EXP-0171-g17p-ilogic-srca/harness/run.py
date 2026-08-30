#!/usr/bin/env python3
"""EXP-0171 gated-run driver (G17P).

  python3 harness/run.py --run g17p_YYYYMMDD_runNN [--ranks 1] [--order forward]

Per case: splice the mutated instruction (NAT: one byte in place in the probe
kernel's own archive; SYNTH/FRAME: the instruction lifted into a program we
assembled), dispatch it once, and append one FIELD-SWEEP-PROTOCOL sect 4 record
IMMEDIATELY (flush + fsync). Never buffers results in memory.

Anti-contamination (FIELD-SWEEP-PROTOCOL sect 7, binding):
  * the read-back buffer is POISONED with 0xDEADBEEF before every dispatch;
  * NAT carries its integrity sentinels in a SEPARATE device buffer (index 4);
    SYNTH/FRAME carry the PRE/POST sentinels of EXP-0154;
  * "STATUS OK and wrote nothing" is `undecodable` + `invalid_run`, never
    `silent_zero` (EXP-0160);
  * majority-of-3 before any `fault`/`hang` is recorded, and the OS
    fault-classification string is recorded VERBATIM on every non-OK case;
  * `...ErrorInnocentVictim`-class failures are flagged `victim` and segregated;
  * the unmutated baseline is re-validated every BASELINE_EVERY cases; a drift
    restarts the child rather than letting a cascade be logged as data;
  * a unique splice-archive path per process;
  * after HANG_STOP genuine hangs in one (arm, carrier) that pair is ABANDONED
    and reported PARTIAL (FIELD-SWEEP-PROTOCOL sect 8).
"""
from __future__ import print_function

import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H      # noqa: E402
import sweeprun as S         # noqa: E402
import casematrix as CM      # noqa: E402

BASELINE_EVERY = 250
RETRIES = 3
REQ_TIMEOUT = 8.0
HANG_STOP = 2


def sh(cmd):
    try:
        return subprocess.check_output(cmd, shell=True,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "?"


def env_block(device):
    return {
        "target": "G17P",
        "device": device,
        "host": platform.node(),
        "os": sh("sw_vers -productVersion") + " (" + sh("sw_vers -buildVersion") + ")",
        "machine": sh("sysctl -n hw.model"),
        "python": sys.version.split()[0],
        "db_sha256": sh("shasum -a 256 %s | cut -d' ' -f1" % (H.ISA_DIR / "db.json")),
        "isadb_sha256": sh("shasum -a 256 %s | cut -d' ' -f1" % (H.ISA_DIR / "isadb.py")),
        "isa_dir": str(H.ISA_DIR),
        "concurrent_gpu": sh("ps ax -o pid,comm | grep -c '[a]gxrun_persist'"),
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--ranks", default="", help="e.g. 1  or  2,3,4")
    ap.add_argument("--order", default="forward", choices=("forward", "reverse"))
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    ranks = set(int(x) for x in a.ranks.split(",") if x.strip()) or None
    rundir = EXP / "raw" / a.run
    rundir.mkdir(parents=True, exist_ok=True)
    rep = json.loads((EXP / "work" / "anchors" / "anchor_report.json").read_text())
    cases, skipped = CM.build_cases(rep, ranks=ranks)
    (rundir / "03_matrix.json").write_text(json.dumps(
        {"cases": len(cases), "matrix_sha256": CM.matrix_sha256(cases),
         "ranks": sorted(ranks) if ranks else "all", "skipped": skipped},
        indent=1, sort_keys=True))

    if a.order == "reverse":
        # The two gated runs execute the SAME frozen matrix in opposite
        # (arm, carrier) order so that, running concurrently with siblings,
        # they are not hitting the same illegal encodings at the same moment.
        # A contamination mitigation, not a change of matrix.
        groups = []
        for c in cases:
            k = (c["arm"], c["carrier"], c["probe"])
            if not groups or groups[-1] != k:
                groups.append(k)
        rank = dict((g, -i) for i, g in enumerate(groups))
        cases = sorted(cases, key=lambda c: (rank[(c["arm"], c["carrier"],
                                                   c["probe"])], c["idx"]))
    if a.limit:
        cases = cases[:a.limit]

    # resume: never re-run or overwrite a case already recorded in this run
    done = set()
    jl = rundir / "sweep.jsonl"
    if jl.exists():
        for ln in jl.open():
            try:
                done.add(json.loads(ln)["idx"])
            except Exception:
                pass
        print("resume: %d cases already recorded" % len(done))

    workdir = EXP / "work" / ("run_%s" % a.run)
    log = S.Log(jl)
    blog = S.Log(rundir / "baseline.jsonl")
    carriers = {}
    baselines = {}
    abandoned = set()
    hangcount = {}
    counters = dict(ok=0, silent_zero=0, wrong_value=0, fault=0, hang=0,
                    undecodable=0, victim=0, sentinel_bad=0, invalid_run=0,
                    baseline_fail=0, poison_out=0, carrier_fail=0)
    env_written = [False]

    def get_carrier(ckey):
        style, probe = ckey
        if ckey in carriers:
            return carriers[ckey]
        try:
            if style == "NAT":
                car = S.NatCarrier(EXP / "kernels" / "probes.metal", probe,
                                   workdir, timeout=REQ_TIMEOUT)
            else:
                car = S.SynthCarrier(EXP / "kernels" / "carrier_dag.metal",
                                     workdir, suffix=(style == "FRAME"),
                                     timeout=REQ_TIMEOUT)
        except Exception as e:
            print("  !! carrier %s/%s FAILED: %s" % (style, probe, str(e)[:200]))
            counters["carrier_fail"] += 1
            carriers[ckey] = None
            return None
        carriers[ckey] = car
        if not env_written[0]:
            (rundir / "00_env.json").write_text(
                json.dumps(env_block(car.device), indent=1, sort_keys=True))
            env_written[0] = True
        return car

    def shape(style, car, c):
        """(n_expect, sent_idx) for the observable of this carrier style."""
        if style == "NAT":
            return CM.KERNELS[c["probe"]]["n_out"], [16, 17]
        return H.N_REGS, [16, 17]

    def dispatch(style, car, c, mut):
        if style == "NAT":
            return car.run_mut(c["instr_off"], mut)
        blk = bytearray(bytes.fromhex(c["anchor_bytes"]))
        for bi, v in mut:
            blk[bi] = v
        return car.run_block(c["kind"], bytes(blk))

    def get_baseline(style, car, c, force=False):
        key = (style, c["probe"], c["instr"], c["tok_index"])
        if key in baselines and not force:
            return baselines[key]
        resp = words = None
        for att in range(8):
            resp, words = dispatch(style, car, c, [])
            if resp["status"] == "OK":
                break
            if S.is_victim(resp["error"]):
                time.sleep(3.0 * (att + 1))
                if att == 3:
                    car.restart()
            else:
                time.sleep(0.5)
        blog.write({"arm": c["arm"], "carrier": style, "probe": c["probe"],
                    "instr": c["instr"], "status": resp["status"],
                    "error": resp["error"], "digest": S.digest_hex(words),
                    "words": words, "kind": "refresh" if force else "initial",
                    "host_oracle": S.digest_hex(car.oracle)})
        if words is None:
            counters["baseline_fail"] += 1
        else:
            baselines[key] = words
        return baselines.get(key)

    n = 0
    t0 = time.time()
    cur = None
    for c in cases:
        if c["idx"] in done:
            continue
        ckey = (c["carrier"], c["probe"] if c["carrier"] == "NAT" else "_dag")
        gkey = (c["arm"], c["carrier"], c["probe"])
        if gkey in abandoned:
            continue
        car = get_carrier(ckey)
        if car is None:
            continue
        if cur != gkey:
            cur = gkey
            base = get_baseline(c["carrier"], car, c)
            print("[%s] %-12s %-5s %-12s baseline %s"
                  % (time.strftime("%H:%M:%S"), c["arm"], c["carrier"],
                     c["probe"], "OK" if base else "FAILED"))
        key = (c["carrier"], c["probe"], c["instr"], c["tok_index"])
        base = baselines.get(key)
        # THE COMPARATOR. Host oracle where one exists (NAT integer kernels),
        # else the measured baseline. Named in every record.
        cmpv = car.oracle if car.oracle is not None else base
        cmpsrc = "host_oracle" if car.oracle is not None else "baseline"
        n_expect, sent_idx = shape(c["carrier"], car, c)
        rt_ok = H.round_trips(bytes.fromhex(c["bytes"]))

        attempts = []
        outcome = None
        obs = None
        info = {}
        for k in range(RETRIES):
            resp, words = dispatch(c["carrier"], car, c, c["mut"])
            oc, inf = S.classify(resp["status"], words, cmpv, n_expect, sent_idx)
            attempts.append({"status": resp["status"], "outcome": oc,
                             "fault_class": resp["error"],
                             "victim": S.is_victim(resp["error"])})
            if oc in ("ok", "silent_zero", "wrong_value"):
                outcome, obs, info = oc, words, inf
                break
            if k == RETRIES - 1:
                bad = [x["outcome"] for x in attempts]
                outcome, obs, info = max(set(bad), key=bad.count), words, inf
        victim = any(x["victim"] for x in attempts)
        counters[outcome] = counters.get(outcome, 0) + 1
        if victim:
            counters["victim"] += 1
        if info.get("sentinel_bad"):
            counters["sentinel_bad"] += 1
        if info.get("invalid_run"):
            counters["invalid_run"] += 1
        if info.get("poison_out"):
            counters["poison_out"] += 1

        rec = {
            "idx": c["idx"], "arm": c["arm"], "rank": c["rank"],
            "instr": c["instr"], "carrier": c["carrier"], "probe": c["probe"],
            "carrier_id": "%s:%s@%s+%d" % (c["carrier"], c["probe"],
                                           c["instr"], c["instr_off"]),
            "role": c["role"], "field": c.get("field"),
            "byte_index": c.get("byte_index"), "value": c["value"],
            "mut": c["mut"], "bytes": c["bytes"],
            "anchor_bytes": c["anchor_bytes"], "instr_len": c["instr_len"],
            "observed": {"digest": S.digest_hex(obs), "words": obs},
            "oracle": {"digest": S.digest_hex(cmpv), "source": cmpsrc},
            "baseline_digest": S.digest_hex(base),
            "match": bool(obs is not None and cmpv is not None and obs == cmpv),
            "outcome": outcome, "kind": c["kind"], "rt_ok": rt_ok,
            "victim": victim, "poison_out": info.get("poison_out", 0),
            "sentinel_bad": bool(info.get("sentinel_bad")),
            "invalid_run": bool(info.get("invalid_run")),
            "fault_class": next((x["fault_class"] for x in attempts
                                 if x["fault_class"]), None),
            "attempts": attempts, "predict": c.get("predict", ""),
            "xplant_from": c.get("xplant_from"), "note": "",
        }
        log.write(rec)
        n += 1

        if outcome == "hang":
            hangcount[gkey] = hangcount.get(gkey, 0) + 1
            if hangcount[gkey] >= HANG_STOP:
                print("  !! %s: %d hangs -> ABANDONING this (arm,carrier) "
                      "and reporting PARTIAL" % (str(gkey), hangcount[gkey]))
                abandoned.add(gkey)
                continue

        if n % BASELINE_EVERY == 0:
            d = get_baseline(c["carrier"], car, c, force=True)
            if d is None or base is None or d != base:
                print("  !! baseline drift/failure at n=%d %s -> restart child"
                      % (n, str(gkey)))
                counters["baseline_fail"] += 1
                car.restart()
                baselines.pop(key, None)
                get_baseline(c["carrier"], car, c)
        if n % 1000 == 0:
            el = time.time() - t0
            print("  %6d/%d  %.1f case/s  %s"
                  % (n, len(cases) - len(done), n / max(el, 1e-9),
                     json.dumps(counters, sort_keys=True)))
            (rundir / "01_progress.json").write_text(json.dumps(
                {"done": n, "counters": counters, "elapsed_s": round(el, 1),
                 "abandoned": [list(x) for x in sorted(abandoned)]},
                indent=1, sort_keys=True))

    (rundir / "02_summary.json").write_text(json.dumps(
        {"cases": n, "counters": counters, "matrix_len": len(cases),
         "abandoned": [list(x) for x in sorted(abandoned)],
         "hangs_by_group": dict((":".join(k), v) for k, v in hangcount.items()),
         "carriers": dict(("%s:%s" % k, (None if v is None else v.requests))
                          for k, v in carriers.items()),
         "elapsed_s": round(time.time() - t0, 1)}, indent=1, sort_keys=True))
    log.close(); blog.close()
    for v in carriers.values():
        if v is not None:
            v.close()
    print("DONE", n, json.dumps(counters, sort_keys=True))


if __name__ == "__main__":
    main()
