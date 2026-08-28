#!/usr/bin/env python3
"""EXP-0141 sweep executor.

Runs every arm of `sweepdefs.build_all()` against the local M4 through
`tools/agxtest/agxrun_persist` (one live MTLDevice per carrier; a fresh
MTLLibrary is loaded from each spliced archive, so every case's bytes really
execute) and APPENDS one JSON record per case to `raw/<run_id>/sweep.jsonl`,
flushing + fsync-ing after every record. Nothing is buffered to the end: a kill
at any point loses at most the case in flight.

Safety (FIELD-SWEEP-PROTOCOL 7): per-request watchdog; after TWO genuine hangs
in one arm the arm is ABORTED and marked PARTIAL, and after HANG_STOP_CARRIER
hangs on one carrier the whole carrier is abandoned. Faults and hangs are
recorded as results, never dropped.
"""
import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(REPO / "tools" / "agxtest"))
import carriers as C  # noqa: E402
import sweepdefs as SD  # noqa: E402
import locate as LOC  # noqa: E402
from persistrun import PersistRunner  # noqa: E402

FAULT_RX = re.compile(r"kIOGPUCommandBufferCallbackError\\w+")


def fault_class(resp):
    """The OS fault-classification token, recorded alongside every non-OK
    status (FIELD-SWEEP-PROTOCOL 7.2). `...ErrorInnocentVictim` (and its
    `Discarded (victim of GPU error/recovery)` text) is evidence about the
    MACHINE -- a sibling experiment's or a previous case's contained fault
    landing in our command buffer -- not about the bytes under test."""
    e = resp.get("error") or ""
    if not e:
        return None
    m = FAULT_RX.search(e)
    if m:
        return m.group(0)
    if "Discarded (victim" in e:
        return "kIOGPUCommandBufferCallbackErrorInnocentVictim"
    return e.strip()[:60]


def is_innocent(resp):
    fc = fault_class(resp) or ""
    return "InnocentVictim" in fc or "Discarded (victim" in (resp.get("error") or "")


HANG_STOP_ARM = 2
HANG_STOP_CARRIER = 6
REQ_TIMEOUT = 8.0
INNOCENT_RETRIES = 6          # bounded retry for machine-attributable failures
CONFIRM_ATTEMPTS = 3          # a `fault` must reproduce in >=2 of 3 attempts
BASELINE_EVERY = 100          # mid-run unmutated-carrier health check
CANARY_RETRIES = 4            # attempts to obtain a run whose sentinel landed
CONFIRM_ABNORMAL = 3          # a non-`ok` verdict needs 2 agreeing observations


def canary_ok(carrier, resp):
    """EVERY carrier writes a fixed sentinel through a path independent of the
    instruction under test -- `sweepdefs._canary` for the synthesised programs,
    an unconditional first store for each own-MSL splice carrier. Its absence
    means our shader did not really run: under concurrent sibling GPU work a
    command buffer can report STATUS OK having executed nothing, and an
    all-zero readback is otherwise indistinguishable from a genuine silent
    zero. Such a run is INVALID and is repeated, never recorded as a property
    of the swept value."""
    idx, word, val = C.CARRIERS[carrier]["sentinel"]
    raw = resp.get("outs", {}).get(idx)
    if not raw:
        return False
    w = C.decode(carrier, idx, raw)
    return len(w) > word and w[word] == val


def _silent_signature(case):
    o = case.get("oracle")
    if o == SD.ALU_ORACLE:
        return ("f", SD.K_SMALL)          # srcA read as 0 -> immediate alone
    if o == SD.FWD_ORACLE:
        return ("f", 0.0)
    return ("z", 0)                        # all-zero output


def classify(case, status, observed, match):
    if status == "HANG":
        return "hang"
    if status != "OK":
        return "fault"
    if match:
        return "ok"
    kind, val = _silent_signature(case)
    got = observed.get("out0")
    if kind == "f" and got and got[0] == val:
        return "silent_zero"
    if kind == "z":
        n = observed.get("n_0")
        allz = all(v == 0 for v in (got or [1]))
        if allz and n:
            return "silent_zero"
    return "wrong_value"


def _baseline_case(carrier, base, main_off):
    """The UNMUTATED program for this carrier, with its host-computed oracle --
    re-issued every BASELINE_EVERY cases so a GPU error cascade is detected
    while it is happening rather than inferred afterwards
    (FIELD-SWEEP-PROTOCOL 7.3)."""
    if carrier == "synth":
        prog, _, _ = SD.prog_alu(R=7)
        b = bytearray(base)
        b[main_off:main_off + len(prog)] = prog
        return bytes(b), SD.ALU_ORACLE
    return bytes(base), None


def run_carrier(carrier, arms, bin_dir, work, fres, sites, mains, progress, health):
    spec = C.CARRIERS[carrier]
    arch_src, main_off, main = mains[carrier]
    base = Path(arch_src).read_bytes()
    ins = {}
    for idx, (fn, data) in spec["inputs"].items():
        p = work / fn
        p.write_bytes(data)
        ins[idx] = str(p)
    spdir = work / "sp"
    spdir.mkdir(exist_ok=True)
    seq = [0]
    runner = [None]

    def start():
        runner[0] = PersistRunner(
            source=str(EXP / spec["metal"]), function=spec["func"],
            fast_math=False,
            agxrun_persist=str(Path(bin_dir) / "agxrun_persist"))

    def stop():
        try:
            if runner[0]:
                runner[0].close()
        except Exception:
            pass
        runner[0] = None

    def submit(blob, timeout=REQ_TIMEOUT):
        """One request, on a UNIQUE archive path.

        HARNESS FINDING (this experiment's own pilot, work/ stability probe):
        REUSING one archive filename across persistent-runner requests -- the
        pattern in RT-1a-FIX/harness/mem_index.py -- produces a ~7-8 % rate of
        SPURIOUS `CMDBUF_ERROR` on byte-identical, known-good archives
        (28 / 360 unmutated requests over three carriers). Giving every request
        its own path and unlinking it afterwards drove that to 0 / 360.
        Overwriting a file the driver may still hold mapped is the mechanism we
        infer; either way, a fresh inode per request is required or a sweep
        will report phantom faults."""
        seq[0] += 1
        p = spdir / ("%s_%d.bin" % (carrier, seq[0]))
        p.write_bytes(blob)
        try:
            return runner[0].request(archive=str(p), grid=spec["grid"],
                                     tg=spec["tg"], ins=ins, outs=spec["outs"],
                                     timeout=timeout)
        finally:
            try:
                os.unlink(p)
            except OSError:
                pass

    def issue(blob):
        """Submit with the two mandated robustness layers:

        1. `ErrorInnocentVictim`-class failures are the MACHINE's, not the
           encoding's, so they are retried (bounded) and SEGREGATED -- their
           classification strings are kept in the record but they never by
           themselves make a case a `fault`.
        2. Any surviving non-OK is CONFIRMED: the case is re-issued until
           CONFIRM_ATTEMPTS non-innocent attempts exist. A `fault` verdict
           requires the failure to REPRODUCE (>= 2 of 3); a single failure
           among successes is reported `nondeterministic`, never `fault`.
        """
        statuses, classes, innocent = [], [], 0
        resp = submit(blob)
        while resp["status"] != "OK" and is_innocent(resp) and innocent < INNOCENT_RETRIES:
            classes.append(fault_class(resp))
            innocent += 1
            time.sleep(0.08 * innocent)
            resp = submit(blob)
        statuses.append(resp["status"])
        if resp["status"] != "OK":
            classes.append(fault_class(resp))
        best = resp
        if resp["status"] != "OK":
            confirm = 1
            while confirm < CONFIRM_ATTEMPTS:
                r2 = submit(blob)
                inn = 0
                while r2["status"] != "OK" and is_innocent(r2) and inn < INNOCENT_RETRIES:
                    classes.append(fault_class(r2))
                    inn += 1
                    time.sleep(0.08 * inn)
                    r2 = submit(blob)
                statuses.append(r2["status"])
                if r2["status"] != "OK":
                    classes.append(fault_class(r2))
                else:
                    best = r2
                confirm += 1
        nbad = sum(1 for s in statuses if s != "OK")
        return best, statuses, classes, innocent, nbad


    def health_check(where):
        blob, oracle = _baseline_case(carrier, base, main_off)
        for _ in range(CANARY_RETRIES):
            resp, statuses, classes, innocent, nbad = issue(blob)
            observed, match = C.summarize(carrier, resp["outs"], oracle)
            if resp["status"] != "OK":
                match = False
            if match or canary_ok(carrier, resp):
                break
            time.sleep(0.05)
        rec = {"arm": "_HEALTH", "i": len(health), "carrier": carrier,
               "instr": "-", "field": "_baseline_health", "value": 0,
               "bytes": "", "observed": observed,
               "oracle": oracle if oracle is not None else {"ref": "carrier:" + carrier},
               "match": bool(match), "outcome": "ok" if match else "cascade_suspected",
               "status": resp["status"], "rt": None, "statuses": statuses,
               "fault_classes": classes or None, "innocent_retries": innocent,
               "expect_match": True, "note": "mid-run unmutated-carrier health "
               "check at " + where}
        fres.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + chr(10))
        fres.flush()
        os.fsync(fres.fileno())
        health.append({"carrier": carrier, "where": where, "match": bool(match),
                       "status": resp["status"], "fault_classes": classes})
        return bool(match)

    start()
    carrier_hangs = 0
    cascade = None
    since_health = 0
    try:
        if not health_check("%s:start" % carrier):
            stop(); start()
            if not health_check("%s:start-after-restart" % carrier):
                cascade = "carrier %s baseline failed at start, twice" % carrier
                return carrier_hangs, cascade
        for arm in arms:
            if cascade:
                break
            arm_hangs = 0
            aborted = None
            t0 = time.time()
            n = -1
            for n, case in enumerate(arm["cases"]):
                b = bytearray(base)
                if case["kind"] == "synth":
                    prog = bytes.fromhex(case["prog"])
                    b[main_off:main_off + len(prog)] = prog
                else:
                    for rel, hx in case["splice"]:
                        by = bytes.fromhex(hx)
                        b[main_off + rel:main_off + rel + len(by)] = by
                blob = bytes(b)
                oracle = case.get("oracle")

                def measure():
                    """One measurement, made robust against machine state:
                    innocent-victim retries inside `issue`, then up to
                    CANARY_RETRIES attempts to obtain a run whose sentinel
                    actually landed."""
                    for _ in range(CANARY_RETRIES):
                        resp, statuses, classes, innocent, nbad = issue(blob)
                        observed, match = C.summarize(carrier, resp["outs"], oracle)
                        if resp["status"] != "OK":
                            match = False
                        can = canary_ok(carrier, resp)
                        oc = classify(case, resp["status"], observed, match)
                        if oc in ("fault", "hang") and nbad < 2:
                            oc = "nondeterministic"
                        if oc in ("fault", "hang"):
                            # A failed command buffer returns NO output, so the
                            # integrity sentinel is trivially absent -- retrying
                            # for it would be a fault storm. `issue()` has
                            # already reproduced this failure in >= 2 of 3
                            # non-innocent attempts, so it IS the measurement.
                            return (oc, observed, False, resp["status"],
                                    statuses, classes, innocent, False)
                        if can:
                            return (oc, observed, bool(match), resp["status"],
                                    statuses, classes, innocent, True)
                        time.sleep(0.05)
                    return ("invalid_run", observed, False, resp["status"],
                            statuses, classes, innocent, False)

                obs_list = [measure()]
                # A NON-`ok` verdict is never taken from one observation
                # (FIELD-SWEEP-PROTOCOL 7.1, generalised: under sibling GPU
                # load an OK-but-empty command buffer forges a mismatch just as
                # readily as it forges a fault). Repeat until two observations
                # agree, or three have been made.
                while (len(obs_list) < CONFIRM_ABNORMAL
                       and obs_list[-1][0] not in ("ok", "fault", "hang")):
                    obs_list.append(measure())
                    if obs_list[-1][:3] == obs_list[-2][:3]:
                        break
                keys = [(o[0], json.dumps(o[1], sort_keys=True)) for o in obs_list]
                winner, confirmed = obs_list[-1], True
                if len(obs_list) > 1:
                    agree = [o for o, k in zip(obs_list, keys) if keys.count(k) >= 2]
                    if agree:
                        winner = agree[0]
                    else:
                        confirmed = False
                outcome, observed, match, status, statuses, classes, innocent, can = winner
                if not confirmed:
                    outcome = "nondeterministic"
                rec = {"arm": arm["arm"], "i": n, "carrier": carrier,
                       "instr": case["instr"], "field": case["field"],
                       "value": case["value"], "bytes": case["ibytes"],
                       "observed": observed,
                       "oracle": oracle if oracle is not None else {"ref": "carrier:" + carrier},
                       "match": bool(match), "outcome": outcome,
                       "status": status, "rt": case.get("rt"),
                       "statuses": statuses if len(statuses) > 1 else None,
                       "fault_classes": classes or None,
                       "innocent_retries": innocent or None,
                       "observations": len(obs_list) if len(obs_list) > 1 else None,
                       "confirmed": confirmed if len(obs_list) > 1 else None,
                       "canary_ok": can if carrier == "synth" else None,
                       "expect_match": case["expect_match"], "note": case["note"]}
                fres.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + chr(10))
                fres.flush()
                os.fsync(fres.fileno())
                since_health += 1
                if outcome == "hang":
                    arm_hangs += 1
                    carrier_hangs += 1
                if since_health >= BASELINE_EVERY or outcome in ("hang", "fault"):
                    if since_health >= BASELINE_EVERY:
                        since_health = 0
                        if not health_check("%s/%s@%d" % (carrier, arm["arm"], n)):
                            stop(); start()
                            if not health_check("%s/%s@%d-restart" % (carrier, arm["arm"], n)):
                                cascade = ("cascade: %s baseline failed twice at "
                                           "%s case %d" % (carrier, arm["arm"], n))
                                aborted = cascade
                                break
                if arm_hangs >= HANG_STOP_ARM:
                    aborted = "arm aborted after %d reproduced hangs at case %d/%d" % (
                        arm_hangs, n + 1, len(arm["cases"]))
                    break
                if carrier_hangs >= HANG_STOP_CARRIER:
                    aborted = "carrier abandoned after %d reproduced hangs" % carrier_hangs
                    break
            progress.append({"arm": arm["arm"], "carrier": carrier,
                             "cases_run": n + 1, "cases_total": len(arm["cases"]),
                             "seconds": round(time.time() - t0, 2),
                             "hangs": arm_hangs, "aborted": aborted})
            print("  %-28s %4d/%-4d %6.2fs%s" % (arm["arm"], n + 1,
                  len(arm["cases"]), time.time() - t0,
                  "  ABORTED: " + aborted if aborted else ""), flush=True)
            if carrier_hangs >= HANG_STOP_CARRIER:
                break
        if not cascade:
            health_check("%s:end" % carrier)
    finally:
        stop()
    return carrier_hangs, cascade


def gpu_neighbours():
    """FIELD-SWEEP-PROTOCOL 7.4: record how much OTHER GPU work was running.
    Counts live sibling hardware-runner processes (`agxrun*`, `agxrender`,
    `shdump`) that are NOT this process tree, so the reader can tell a sweep
    run alone from a sweep run against siblings."""
    try:
        out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,comm="], text=True,
                             capture_output=True, timeout=15).stdout
    except Exception as e:
        return {"error": type(e).__name__}
    mine, others = [], []
    me = os.getpid()
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        pid, ppid, comm = parts
        name = Path(comm.strip()).name
        if name.startswith(("agxrun", "agxrender", "shdump")):
            (mine if int(ppid) == me else others).append(name)
    return {"own_runner_processes": sorted(mine),
            "other_gpu_runner_processes": sorted(others),
            "n_other": len(others)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--bin-dir", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--only-carrier", default=None)
    ap.add_argument("--addendum", action="store_true",
                    help="run the atomic_rmw addendum matrix instead of the main one")
    ap.add_argument("--arms-regex", default=None,
                    help="smoke/debug only: restrict to arms matching this regex")
    a = ap.parse_args()
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    raw = Path(a.raw)
    raw.mkdir(parents=True, exist_ok=True)

    sites, mains = LOC.locate_all(a.bin_dir, work)
    # the synthesis carrier is not a splice site; compile it here
    arch, moff, main = LOC.compile_carrier("synth", a.bin_dir, work)
    if len(main) != SD.CARRIER_LEN:
        raise SystemExit("synth carrier _agc.main length %d != %d"
                         % (len(main), SD.CARRIER_LEN))
    mains["synth"] = (str(arch), moff, main)

    arms = SD.build_addendum(sites) if a.addendum else SD.build_all(sites)
    if a.arms_regex:
        import re
        rx = re.compile(a.arms_regex)
        arms = [x for x in arms if rx.search(x["arm"])]
    by_carrier = {}
    for arm in arms:
        if arm["carrier"] == "multi":
            continue
        by_carrier.setdefault(arm["carrier"], []).append(arm)
    # the multi-carrier control arm is split per case
    ctrl = [x for x in arms if x["carrier"] == "multi"]
    for arm in ctrl:
        groups = {}
        for c in arm["cases"]:
            groups.setdefault(c["carrier"], []).append(c)
        for cname, cases in groups.items():
            by_carrier.setdefault(cname, []).insert(
                0, {"arm": "CTRL_SPLICE", "carrier": cname, "instr": "-",
                    "field": "_controls", "cases": cases, "doc": arm["doc"]})

    manifest = {"run_id": a.run_id,
                "sites": {k: [v[0], v[1], v[2], v[3].hex()] for k, v in sites.items()},
                "mains": {c: {"main_off": mo, "main_len": len(mm),
                              "main_sha256": hashlib.sha256(mm).hexdigest()}
                          for c, (ap_, mo, mm) in mains.items()},
                "arms": [{"arm": x["arm"], "carrier": x["carrier"],
                          "instr": x["instr"], "field": x["field"],
                          "n_cases": len(x["cases"]), "doc": x["doc"]}
                         for x in arms],
                "n_cases": sum(len(x["cases"]) for x in arms),
                "carrier_oracles": {k: (v["oracle"] if k != "tgtile" else "ramp(256)")
                                    for k, v in C.CARRIERS.items()}}
    (raw / "00_manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")

    progress, health, cascades = [], [], []
    order = [c for c in ("synth", "atdev", "atdevimm", "attg", "tgtile", "devfence")
             if c in by_carrier and (a.only_carrier in (None, c))]
    conc_start = gpu_neighbours()
    with open(raw / "sweep.jsonl", "a") as fres:
        for cname in order:
            print("carrier %s (%d arms)" % (cname, len(by_carrier[cname])), flush=True)
            _, cascade = run_carrier(cname, by_carrier[cname], a.bin_dir, work,
                                     fres, sites, mains, progress, health)
            if cascade:
                cascades.append(cascade)
                print("  CASCADE: " + cascade, flush=True)
    conc_end = gpu_neighbours()
    (raw / "01_progress.json").write_text(json.dumps(
        {"arms": progress, "health_checks": health, "cascades": cascades,
         "concurrency_start": conc_start, "concurrency_end": conc_end},
        indent=1) + "\n")
    print("DONE %s: %d cases planned" % (a.run_id, manifest["n_cases"]))


if __name__ == "__main__":
    main()
