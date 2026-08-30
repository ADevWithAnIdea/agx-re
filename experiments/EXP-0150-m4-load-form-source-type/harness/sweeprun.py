#!/usr/bin/env python3
"""EXP-0150 sweep executor.

Runs every arm of `sweepdefs.build_all()` against the local M4 through
`tools/agxtest/agxrun_persist` (one live MTLDevice; a fresh MTLLibrary is loaded
from each spliced archive, so every case's bytes really execute) and APPENDS one
JSON record per case to `raw/<run_id>/sweep.jsonl`, flushing + fsync-ing after
every record. Nothing is buffered to the end: a kill at any point loses at most
the case in flight.

FIELD-SWEEP-PROTOCOL section 7 is implemented here, carried over from EXP-0141's
hardened executor:
  7.1  majority-of-3: no non-`ok` verdict from one observation
  7.2  OS fault-classification string recorded; InnocentVictim segregated
  7.3  periodic unmutated-baseline re-validation, cascade detection
  7.4  sibling GPU-runner census at run start and end
plus this experiment's own two additions:
  * a UNIQUE splice-archive path per request (EXP-0141: reuse forges ~8 % faults)
  * a POISONED (0xDEADBEEF) output buffer, bound as both input and output, so
    "the GPU wrote nothing" is distinguishable from "the GPU wrote zero".
"""
import argparse
import hashlib
import json
import os
import re
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
from persistrun import PersistRunner  # noqa: E402

FAULT_RX = re.compile(r"kIOGPUCommandBufferCallbackError\w+")

HANG_STOP_ARM = 2             # abort an arm after 2 reproduced hangs
HANG_STOP_RUN = 6             # abandon the run after 6
REQ_TIMEOUT = 8.0
INNOCENT_RETRIES = 6
CONFIRM_ATTEMPTS = 3          # a `fault` must reproduce in >= 2 of 3
BASELINE_EVERY = 100
CANARY_RETRIES = 4
CONFIRM_ABNORMAL = 3


def fault_class(resp):
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


def classify(case, status, observed, match):
    """FIELD-SWEEP-PROTOCOL section 4 vocabulary, plus `nondeterministic` /
    `invalid_run` (added by the executor, not here). A value that produces the
    case's SILENT SIGNATURE -- the result of the operand under test reading as
    0.0 -- is `silent_zero`, which is a RESULT, not a skipped case."""
    if status == "HANG":
        return "hang", None
    if status != "OK":
        return "fault", None
    if match:
        return "ok", None
    got = (observed.get("out0") or [None])[0]
    if got is None:
        return "wrong_value", None
    for label, val in case["silent"]:
        if got == val:
            return "silent_zero", label
    if got == C.POISON_F32:
        return "wrong_value", "poison_intact"
    return "wrong_value", None


def gpu_neighbours():
    """FIELD-SWEEP-PROTOCOL 7.4: how much OTHER GPU work is running. Counts live
    sibling hardware-runner processes that are NOT in this process tree."""
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
            "other_gpu_runner_processes": sorted(others), "n_other": len(others)}


def compile_carrier(bin_dir, out_dir):
    """Recompile our own MSL carrier and re-derive `_agc.main` fresh. Nothing is
    hardcoded: CARRIER_LEN is an ASSERTION checked before every capture, so a
    toolchain change is a loud stop rather than a silent splice."""
    arch = Path(out_dir) / "carrier.bin"
    subprocess.run([str(Path(bin_dir) / "shdump"), "-o", str(arch),
                    "--no-fast-math", str(EXP / C.CARRIER["metal"]),
                    "-f", C.CARRIER["func"]],
                   check=True, capture_output=True, timeout=120)
    off = int(subprocess.check_output(
        [sys.executable, "-B", str(REPO / "tools" / "shdump" / "agxparse.py"),
         str(arch), "--locate", "_agc.main"], text=True, timeout=60).split()[0])
    hexstr = subprocess.check_output(
        [sys.executable, "-B", str(REPO / "tools" / "shdump" / "agxparse.py"),
         str(arch), "--extract-hex"], text=True, timeout=60).strip()
    return arch, off, bytes.fromhex(hexstr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--bin-dir", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--arms-regex", default=None,
                    help="smoke/debug only: restrict to arms matching this regex")
    a = ap.parse_args()
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    raw = Path(a.raw)
    raw.mkdir(parents=True, exist_ok=True)

    arch, main_off, main = compile_carrier(a.bin_dir, work)
    if len(main) != SD.CARRIER_LEN:
        raise SystemExit("carrier _agc.main length %d != frozen %d"
                         % (len(main), SD.CARRIER_LEN))
    base = Path(arch).read_bytes()

    ins = {}
    for idx, (fn, data) in C.CARRIER["inputs"].items():
        p = work / fn
        p.write_bytes(data)
        ins[idx] = str(p)
    outs = C.CARRIER["outs"]
    spdir = work / "sp"
    spdir.mkdir(exist_ok=True)

    arms = SD.build_all()
    if a.arms_regex:
        rx = re.compile(a.arms_regex)
        arms = [x for x in arms if rx.search(x["arm"])]

    manifest = {
        "run_id": a.run_id,
        "carrier": {"metal": C.CARRIER["metal"], "main_off": main_off,
                    "main_len": len(main),
                    "main_sha256": hashlib.sha256(main).hexdigest(),
                    "archive_sha256": hashlib.sha256(base).hexdigest()},
        "poison": "0x%08X" % C.POISON_U32,
        "out_bytes": C.OUT_BYTES,
        "arms": [{"arm": x["arm"], "instr": x["instr"], "field": x["field"],
                  "n_cases": len(x["cases"]), "doc": x["doc"]} for x in arms],
        "n_cases": sum(len(x["cases"]) for x in arms),
    }
    (raw / "00_manifest.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n")

    seq = [0]
    runner = [None]

    def start():
        runner[0] = PersistRunner(
            source=str(EXP / C.CARRIER["metal"]), function=C.CARRIER["func"],
            fast_math=False,
            agxrun_persist=str(Path(a.bin_dir) / "agxrun_persist"))

    def stop():
        try:
            if runner[0]:
                runner[0].close()
        except Exception:
            pass
        runner[0] = None

    def submit(blob, timeout=REQ_TIMEOUT):
        """One request on a UNIQUE archive path (EXP-0141: reusing one path
        produced ~8 % spurious CMDBUF_ERROR on byte-identical archives)."""
        seq[0] += 1
        p = spdir / ("c_%d.bin" % seq[0])
        p.write_bytes(blob)
        try:
            return runner[0].request(archive=str(p), grid=C.CARRIER["grid"],
                                     tg=C.CARRIER["tg"], ins=ins, outs=outs,
                                     timeout=timeout)
        finally:
            try:
                os.unlink(p)
            except OSError:
                pass

    def issue(blob):
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

    BASE_CASE = SD.build_controls()[0]["cases"][0]      # CTRL/_load_baseline

    def health_check(where, fres, health):
        b = bytearray(base)
        prog = bytes.fromhex(BASE_CASE["prog"])
        b[main_off:main_off + len(prog)] = prog
        blob = bytes(b)
        for _ in range(CANARY_RETRIES):
            resp, statuses, classes, innocent, nbad = issue(blob)
            observed, match = C.summarize(resp["outs"], BASE_CASE["oracle"]["out0"])
            if resp["status"] != "OK":
                match = False
            if match or C.sentinel_ok(resp["outs"]):
                break
            time.sleep(0.05)
        rec = {"arm": "_HEALTH", "i": len(health), "instr": "-",
               "field": "_baseline_health", "value": 0, "bytes": "",
               "observed": observed, "oracle": BASE_CASE["oracle"],
               "match": bool(match), "outcome": "ok" if match else "cascade_suspected",
               "status": resp["status"], "statuses": statuses,
               "fault_classes": classes or None, "innocent_retries": innocent,
               "expect_match": True, "note": "unmutated-baseline health check at " + where}
        fres.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")
        fres.flush()
        os.fsync(fres.fileno())
        health.append({"where": where, "match": bool(match),
                       "status": resp["status"], "fault_classes": classes})
        return bool(match)

    progress, health, cascades = [], [], []
    conc_start = gpu_neighbours()
    start()
    run_hangs = 0
    since_health = 0
    cascade = None
    try:
        with open(raw / "sweep.jsonl", "a") as fres:
            if not health_check("run:start", fres, health):
                stop(); start()
                if not health_check("run:start-after-restart", fres, health):
                    cascades.append("baseline failed twice at run start")
                    cascade = cascades[-1]
            for arm in arms:
                if cascade:
                    break
                arm_hangs = 0
                aborted = None
                t0 = time.time()
                n = -1
                for n, case in enumerate(arm["cases"]):
                    b = bytearray(base)
                    prog = bytes.fromhex(case["prog"])
                    b[main_off:main_off + len(prog)] = prog
                    blob = bytes(b)

                    def measure():
                        for _ in range(CANARY_RETRIES):
                            resp, statuses, classes, innocent, nbad = issue(blob)
                            observed, match = C.summarize(resp["outs"],
                                                          case["oracle"]["out0"])
                            if resp["status"] != "OK":
                                match = False
                            oc, sk = classify(case, resp["status"], observed, match)
                            if oc in ("fault", "hang") and nbad < 2:
                                oc = "nondeterministic"
                            if oc in ("fault", "hang"):
                                # a failed command buffer returns NO output, so
                                # the sentinel is trivially absent; `issue` has
                                # already reproduced the failure >= 2 of 3.
                                return (oc, observed, False, resp["status"],
                                        statuses, classes, innocent, False, sk)
                            if C.sentinel_ok(resp["outs"]):
                                return (oc, observed, bool(match), resp["status"],
                                        statuses, classes, innocent, True, sk)
                            time.sleep(0.05)
                        return ("invalid_run", observed, False, resp["status"],
                                statuses, classes, innocent, False, None)

                    obs = [measure()]
                    while (len(obs) < CONFIRM_ABNORMAL
                           and obs[-1][0] not in ("ok", "fault", "hang")):
                        obs.append(measure())
                        if obs[-1][:3] == obs[-2][:3]:
                            break
                    keys = [(o[0], json.dumps(o[1], sort_keys=True)) for o in obs]
                    winner, confirmed = obs[-1], True
                    if len(obs) > 1:
                        agree = [o for o, k in zip(obs, keys) if keys.count(k) >= 2]
                        if agree:
                            winner = agree[0]
                        else:
                            confirmed = False
                    (outcome, observed, match, status, statuses, classes,
                     innocent, can, silent_kind) = winner
                    if not confirmed:
                        outcome = "nondeterministic"

                    rec = {"arm": arm["arm"], "i": n, "instr": case["instr"],
                           "field": case["field"], "value": case["value"],
                           "bytes": case["ibytes"], "observed": observed,
                           "oracle": case["oracle"], "silent": case["silent"],
                           "oracle_variant": case["oracle_variant"],
                           "match": bool(match), "outcome": outcome,
                           "silent_kind": silent_kind, "status": status,
                           "rt": case["rt"], "meta": case["meta"],
                           "statuses": statuses if len(statuses) > 1 else None,
                           "fault_classes": classes or None,
                           "innocent_retries": innocent or None,
                           "observations": len(obs) if len(obs) > 1 else None,
                           "confirmed": confirmed if len(obs) > 1 else None,
                           "sentinel_ok": can,
                           "expect_match": case["expect_match"],
                           "note": case["note"]}
                    fres.write(json.dumps(rec, sort_keys=True,
                                          separators=(",", ":")) + "\n")
                    fres.flush()
                    os.fsync(fres.fileno())
                    since_health += 1
                    if outcome == "hang":
                        arm_hangs += 1
                        run_hangs += 1
                    if since_health >= BASELINE_EVERY:
                        since_health = 0
                        if not health_check("%s@%d" % (arm["arm"], n), fres, health):
                            stop(); start()
                            if not health_check("%s@%d-restart" % (arm["arm"], n),
                                                fres, health):
                                cascade = ("cascade: baseline failed twice at %s "
                                           "case %d" % (arm["arm"], n))
                                aborted = cascade
                                cascades.append(cascade)
                                break
                    if arm_hangs >= HANG_STOP_ARM:
                        aborted = ("arm aborted after %d reproduced hangs at case "
                                   "%d/%d" % (arm_hangs, n + 1, len(arm["cases"])))
                        break
                    if run_hangs >= HANG_STOP_RUN:
                        aborted = "run abandoned after %d reproduced hangs" % run_hangs
                        break
                progress.append({"arm": arm["arm"], "cases_run": n + 1,
                                 "cases_total": len(arm["cases"]),
                                 "seconds": round(time.time() - t0, 2),
                                 "hangs": arm_hangs, "aborted": aborted})
                (raw / "01_progress.json").write_text(json.dumps(
                    {"arms": progress, "health_checks": health,
                     "cascades": cascades, "concurrency_start": conc_start},
                    indent=1) + "\n")
                print("  %-26s %4d/%-4d %7.2fs%s"
                      % (arm["arm"], n + 1, len(arm["cases"]), time.time() - t0,
                         "  ABORTED: " + aborted if aborted else ""), flush=True)
                if run_hangs >= HANG_STOP_RUN:
                    break
            if not cascade:
                health_check("run:end", fres, health)
    finally:
        stop()
    conc_end = gpu_neighbours()
    (raw / "01_progress.json").write_text(json.dumps(
        {"arms": progress, "health_checks": health, "cascades": cascades,
         "concurrency_start": conc_start, "concurrency_end": conc_end},
        indent=1) + "\n")
    print("DONE %s: %d cases planned" % (a.run_id, manifest["n_cases"]))


if __name__ == "__main__":
    main()
