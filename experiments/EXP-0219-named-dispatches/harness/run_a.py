#!/usr/bin/env python3
"""EXP-0219 part-A driver (the four `imad` dispatches EXP-0218 named).  G17P.

  python3 harness/run_a.py --run <run_id> --carrier dag|const \
      [--order forward|reverse|shuffle] [--limit N] [--arms a,b]

Per case: build the synthesized program for the case's seed set (seeds -> PRE
sentinel -> the lifted 12-byte imad with one/two named bytes replaced ->
16-register dump -> POST sentinel -> stop), splice it over the WHOLE `_agc.main`,
RE-READ the spliced window back from the file that was handed to Metal, decode
the 12 block bytes from THAT with the pinned DB, dispatch once, and append one
record immediately (flush + fsync).

GATE A is enforced per case: `gate_a_ok` is true only when the requested
byte+7 / byte+8 / byte+9 equal the values decoded back out of the ACTUAL bytes.
GATE B: the unmutated anchor baseline is taken per (arm, seed set) and
re-validated every BASELINE_EVERY cases; the `ctrl` arm carries the declared
detection-power cases.  GATE C: `harness/oracle_a.py` records the product and
every model prediction computable without the GPU.

Hang policy (declared in PRE_REGISTRATION section 7): 8 hangs per arm, 32 for the
experiment; and if `recoveryCount` is unchanged across 6 consecutive hangs the
arm stops immediately and the capture is marked cascade-contaminated.
"""
from __future__ import print_function

import argparse
import json
import platform
import random
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import imad_helpers as H          # noqa: E402
import imad_carrier as C          # noqa: E402
import casematrix_a as CM         # noqa: E402
import oracle_a as O              # noqa: E402

isadb = H.isadb
BASELINE_EVERY = 400
RETRIES = 3
REQ_TIMEOUT = 8.0
HANG_BUDGET_ARM = 8
HANG_BUDGET_RUN = 32
CASCADE_RUN = 6

CARRIER_SRC = {"dag": "kernels/carrier_dag.metal",
               "const": "kernels/carrier_const.metal"}


def sh(cmd):
    try:
        return subprocess.check_output(cmd, shell=True,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "?"


def recovery_count():
    out = sh("ioreg -l -w0 -r -c AGXAcceleratorG17P 2>/dev/null | "
             "grep -o '\"recoveryCount\"=[0-9]*' | head -1")
    try:
        return int(out.split("=")[1])
    except Exception:
        return None


def block_offset(kind, sset):
    """Byte offset of the lifted block inside the synthesized program."""
    n = sum(len(x) for x in H.seed_instrs(kind, sset))
    n += sum(len(x) for x in H.pre_sentinel_instrs(kind, sset))
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--carrier", required=True, choices=("dag", "const"))
    ap.add_argument("--anchor", required=True, help="12-byte imad anchor, hex")
    ap.add_argument("--order", default="forward",
                    choices=("forward", "reverse", "shuffle"))
    ap.add_argument("--seed", type=int, default=219)
    ap.add_argument("--arms", default="")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    rundir = EXP / "raw" / a.run
    if rundir.exists():
        sys.exit("run dir already exists, refusing to reuse: %s" % rundir)
    rundir.mkdir(parents=True)

    cases = CM.build_cases(a.anchor, a.carrier)
    msha = CM.matrix_sha256(cases)
    if a.arms:
        want = set(a.arms.split(","))
        cases = [c for c in cases if c["arm"] in want]
    if a.limit:
        cases = cases[:a.limit]
    ordered = list(cases)
    if a.order == "reverse":
        ordered = list(reversed(ordered))
    elif a.order == "shuffle":
        rnd = random.Random(a.seed)
        rnd.shuffle(ordered)
    # controls always run first, whatever the order
    ordered = ([c for c in ordered if c["arm"] == "ctrl"]
               + [c for c in ordered if c["arm"] != "ctrl"])

    car = C.Carrier(EXP / CARRIER_SRC[a.carrier], "k",
                    EXP / "work" / ("run_%s" % a.run), timeout=REQ_TIMEOUT)
    rc0 = recovery_count()
    env = {"target": "G17P", "device": car.device, "host": platform.node(),
           "os": sh("sw_vers -productVersion") + " (" + sh("sw_vers -buildVersion") + ")",
           "machine": sh("sysctl -n hw.model"), "python": sys.version.split()[0],
           "carrier": a.carrier, "carrier_src": CARRIER_SRC[a.carrier],
           "carrier_src_sha256": sh("shasum -a 256 %s | cut -d' ' -f1"
                                    % (EXP / CARRIER_SRC[a.carrier])),
           "anchor": a.anchor, "region_len": car.region_len,
           "region_off": car.region_off,
           "base_archive_sha256": sh("shasum -a 256 %s | cut -d' ' -f1"
                                     % car.base_path),
           "db_sha256": sh("shasum -a 256 %s | cut -d' ' -f1"
                           % (H.ISA_DIR / "db.json")),
           "isadb_sha256": sh("shasum -a 256 %s | cut -d' ' -f1"
                              % (H.ISA_DIR / "isadb.py")),
           "harness_sha256": sh("shasum -a 256 %s | cut -d' ' -f1" % (HERE / "run_a.py")),
           "matrix_sha256": msha, "order": a.order, "order_seed": a.seed,
           "n_cases": len(ordered), "recoveryCount_pre": rc0,
           "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (rundir / "00_env.json").write_text(json.dumps(env, indent=1, sort_keys=True))

    log = C.Log(rundir / "sweep.jsonl")
    blog = C.Log(rundir / "baseline.jsonl")
    baselines = {}
    counters = {}
    hangs_arm = {}
    hang_run = 0
    consec_hang = 0
    rc_at_first_consec = None
    cascade = []

    def baseline_for(key, force=False):
        arm, sset = key
        if key in baselines and not force:
            return baselines[key]
        blk = bytes.fromhex(a.anchor)
        prog = H.synth_program("int", blk, car.region_len, sset)
        d = None
        for att in range(6):
            resp, words, _ = car.run_program(prog)
            if resp["status"] == "OK" and words:
                d = C.digest(words)
                break
            if C.is_victim(resp.get("error")):
                time.sleep(2.0 * (att + 1))
            if att == 3:
                car.restart()
        blog.write({"arm": arm, "sset": sset, "kind": "refresh" if force else "initial",
                    "status": resp["status"], "error": resp.get("error"),
                    "digest": C.digest_hex(d) if d else None,
                    "regs": d["regs"] if d else None,
                    "poison": C.poison_count(d)})
        if d is not None:
            baselines[key] = d
        return d

    t0 = time.time()
    n = 0
    cur = None
    stop_all = False
    for c in ordered:
        if stop_all:
            break
        key = (c["arm"], c["sset"])
        if key != cur:
            cur = key
            b = baseline_for(key)
            print("[%s] %s sset%d baseline %s"
                  % (time.strftime("%H:%M:%S"), c["arm"], c["sset"],
                     "OK" if b else "FAILED"), flush=True)
        base = baselines.get(key)
        blk = bytes.fromhex(c["bytes"])
        prog = H.synth_program("int", blk, car.region_len, c["sset"])
        boff = block_offset("int", c["sset"])
        seeds = H.seeds_for("int", c["sset"])

        attempts = []
        outcome, obs, actual_blk = None, None, None
        for k in range(RETRIES):
            resp, words, actual = car.run_program(prog)
            actual_blk = actual[boff:boff + 12]
            d = C.digest(words) if resp["status"] == "OK" and words else None
            oc = C.classify(resp["status"], d, base) if base else "undecodable"
            attempts.append({"status": resp["status"], "outcome": oc,
                             "error": resp.get("error"),
                             "victim": C.is_victim(resp.get("error"))})
            if oc in ("ok", "silent_zero", "wrong_value"):
                outcome, obs = oc, d
                break
            if k == RETRIES - 1:
                bad = [x["outcome"] for x in attempts]
                outcome = max(set(bad), key=bad.count)
                obs = d
        # ---- GATE A: decode the ACTUAL bytes independently -------------------
        ledger = {"requested_bytes": c["bytes"], "actual_bytes": actual_blk.hex(),
                  "bytes_match": actual_blk.hex() == c["bytes"],
                  "block_off": boff, "region_off": car.region_off}
        try:
            dec, L = isadb.decode_one(actual_blk, 0)
            ledger["decoded_mnemonic"] = dec["mnemonic"]
            ledger["decoded_len"] = L
            ledger["decoded_b7"] = dec["fields"].get("srcC_desc")
            ledger["decoded_b8"] = dec["fields"].get("mulsel")
            ledger["decoded_b9"] = dec["fields"].get("b9")
            ledger["gate_a_ok"] = bool(
                dec["mnemonic"] == "imad" and L == 12
                and ledger["decoded_b7"] == c["fields"]["b7"]
                and ledger["decoded_b8"] == c["fields"]["b8"]
                and ledger["decoded_b9"] == c["fields"]["b9"])
        except Exception as e:                                  # noqa: BLE001
            ledger.update(decoded_mnemonic=None, decoded_b7=None, decoded_b8=None,
                          decoded_b9=None, gate_a_ok=False,
                          decode_error=str(e)[:120])

        b5, b6, b7 = actual_blk[5], actual_blk[6], actual_blk[7]
        b8, b9, b3 = actual_blk[8], actual_blk[9], actual_blk[3]
        P = O.product(seeds, b5, b6)
        m = O.m_of(b7)
        oracle = {"P": P, "m": m, "dst_reg": (b3 >> 1) & 0x7F,
                  "A_models_nofit": O.A_models(b7, b8, b9),
                  "dest_if": {k: (O.dest(P, m, v) if m is not None else None)
                              for k, v in O.A_models(b7, b8, b9).items()},
                  "fit_rule": "FILE[j] := addend from arm cross, b9=0x2e, "
                              "b8=0xd0, K=j, sset 1, run01 only"}
        # model-free addend readout, valid where m == 0 (product dropped) and
        # where the destination is trusted; recorded, not interpreted here.
        rec_A = None
        if obs is not None:
            r = obs["regs"][(b3 >> 1) & 0xF] if ((b3 >> 1) & 0x7F) < 16 else None
            if r is not None and m is not None:
                rec_A = (r - m * P) & 0xFFFFFFFF
        victim = any(x["victim"] for x in attempts)
        sent_bad = bool(obs and (obs["pre"] != H.expected_pre()
                                 or obs["post"] != H.SENT_POST))
        counters[outcome] = counters.get(outcome, 0) + 1
        if victim:
            counters["victim"] = counters.get("victim", 0) + 1
        if sent_bad:
            counters["sentinel_bad"] = counters.get("sentinel_bad", 0) + 1

        log.write({"idx": c["idx"], "run": a.run, "target": "G17P",
                   "carrier": a.carrier, "arm": c["arm"], "instr": "imad",
                   "field": "b7b8b9", "value": c["fields"], "sset": c["sset"],
                   "seeds": {str(k): v for k, v in seeds.items()},
                   "bytes": c["bytes"], "ledger": ledger,
                   "observed": {"regs": obs["regs"] if obs else None,
                                "pre": obs["pre"] if obs else None,
                                "post": obs["post"] if obs else None,
                                "digest": C.digest_hex(obs) if obs else None},
                   "baseline_digest": C.digest_hex(base) if base else None,
                   "recovered_A": rec_A,
                   "oracle": oracle, "outcome": outcome,
                   "poison_words": C.poison_count(obs),
                   "victim": victim, "sentinel_bad": sent_bad,
                   "attempts": attempts, "order_index": n,
                   "predict": c["predict"]})
        n += 1

        if outcome == "hang":
            hang_run += 1
            hangs_arm[c["arm"]] = hangs_arm.get(c["arm"], 0) + 1
            consec_hang += 1
            if consec_hang == 1:
                rc_at_first_consec = recovery_count()
            if consec_hang >= CASCADE_RUN:
                rc_now = recovery_count()
                cascade.append({"arm": c["arm"], "at_case": n,
                                "consecutive_hangs": consec_hang,
                                "recoveryCount_first": rc_at_first_consec,
                                "recoveryCount_now": rc_now,
                                "class": ("accumulating"
                                          if rc_now == rc_at_first_consec
                                          else "driver-recoverable")})
                print("!! cascade guard fired:", cascade[-1], flush=True)
                stop_all = True
            if hangs_arm[c["arm"]] >= HANG_BUDGET_ARM or hang_run >= HANG_BUDGET_RUN:
                print("!! hang budget reached (arm %s: %d, run: %d)"
                      % (c["arm"], hangs_arm[c["arm"]], hang_run), flush=True)
                stop_all = True
        else:
            consec_hang = 0

        if n % BASELINE_EVERY == 0:
            d = baseline_for(key, force=True)
            if d is None or base is None or d["regs"] != base["regs"]:
                print("  !! baseline drift at n=%d arm=%s -> restart"
                      % (n, c["arm"]), flush=True)
                counters["baseline_fail"] = counters.get("baseline_fail", 0) + 1
                car.restart()
                baselines.pop(key, None)
                baseline_for(key)
        if n % 250 == 0:
            el = time.time() - t0
            print("  %6d/%d  %.1f case/s  %s"
                  % (n, len(ordered), n / max(el, 1e-9),
                     json.dumps(counters, sort_keys=True)), flush=True)
            (rundir / "01_progress.json").write_text(json.dumps(
                {"done": n, "counters": counters, "elapsed_s": round(el, 1)},
                indent=1, sort_keys=True))

    rc1 = recovery_count()
    (rundir / "02_summary.json").write_text(json.dumps(
        {"cases": n, "planned": len(ordered), "counters": counters,
         "hangs_by_arm": hangs_arm, "hangs_total": hang_run,
         "cascade": cascade, "stopped_early": stop_all,
         "recoveryCount_pre": rc0, "recoveryCount_post": rc1,
         "recoveryCount_delta": (None if rc0 is None or rc1 is None else rc1 - rc0),
         "elapsed_s": round(time.time() - t0, 1),
         "matrix_sha256": msha}, indent=1, sort_keys=True))
    log.close()
    blog.close()
    car.close()
    print("DONE", n, json.dumps(counters, sort_keys=True))


if __name__ == "__main__":
    main()
