#!/usr/bin/env python3
"""EXP-0153 sweep executor (G17P).

Runs every arm of `cases.build_all()` against the A18 Pro through
`tools/agxtest/agxrun_persist` (one live MTLDevice per carrier; a FRESH
MTLLibrary is loaded from each spliced archive, so every case's bytes really
execute) and APPENDS one JSON record per case to `raw/<run_id>/sweep.jsonl`,
flushing + fsync-ing after every record. Nothing is buffered to the end: a kill
at any point loses at most the case in flight.

Structure adapted from `EXP-0141-m4-emit-mem/harness/sweeprun.py` (same
project, same rules) with three changes required by the port:

  1. carrier `_agc.main` LENGTHS are DISCOVERED on the target, never asserted
     from the M4 value -- a different compiler produces a different region,
     and hard-coding 170/1536 would be an automatic stop on G17P;
  2. splice ANCHORS are located by tokenizing our own compiled carrier with
     tools/agx-isa at run time (`anchors.find`), so a moved instruction is a
     loud failure rather than a silent splice into the wrong place;
  3. `--revalidate` re-runs only the non-`ok` cases of a previous run, N times
     each, which is where the GPU lease is taken.

Safety (FIELD-SWEEP-PROTOCOL section 7): per-request watchdog; InnocentVictim
failures retried and segregated; a `fault` verdict requires reproduction in at
least 2 of 3 non-innocent attempts; periodic unmutated-carrier health checks;
after TWO reproduced hangs an arm is ABORTED, after HANG_STOP_CARRIER the
carrier is abandoned. Faults and hangs are recorded as results, never dropped.
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
sys.path.insert(0, str(HERE))
import isa_helpers as H  # noqa: E402  (also puts tools/agx-isa on sys.path)
import carriers as C  # noqa: E402
import cases as CS  # noqa: E402
import anchors as A  # noqa: E402

sys.path.insert(0, str(H.TOOLS / "agxtest"))
from persistrun import PersistRunner  # noqa: E402

FAULT_RX = re.compile(r"kIOGPUCommandBufferCallbackError\w+")

HANG_STOP_ARM = 2
HANG_STOP_CARRIER = 6
REQ_TIMEOUT = 10.0
INNOCENT_RETRIES = 6
CONFIRM_ATTEMPTS = 3
BASELINE_EVERY = 120
CANARY_RETRIES = 4
CONFIRM_ABNORMAL = 3


def fault_class(resp):
    """The OS fault-classification token, recorded alongside every non-OK
    status (FIELD-SWEEP-PROTOCOL 7.2). `...ErrorInnocentVictim` (and its
    `Discarded (victim of GPU error/recovery)` text) is evidence about the
    MACHINE -- another agent's or a previous case's contained fault landing in
    our command buffer -- not about the bytes under test."""
    e = resp.get("error") or ""
    if not e:
        return None
    m = FAULT_RX.search(e)
    if m:
        return m.group(0)
    if "Discarded (victim" in e:
        return "kIOGPUCommandBufferCallbackErrorInnocentVictim"
    return e.strip()[:80]


def is_innocent(resp):
    fc = fault_class(resp) or ""
    return "InnocentVictim" in fc or "Discarded (victim" in (resp.get("error") or "")


# ---------------------------------------------------------------------------
# build / locate
# ---------------------------------------------------------------------------
def compile_carrier(name, bin_dir, out_dir):
    spec = C.CARRIERS[name]
    arch = Path(out_dir) / ("carrier_%s_%s.bin" % (name, spec["func"]))
    cmd = [str(Path(bin_dir) / "shdump"), "-o", str(arch), "--no-fast-math",
           str(EXP / spec["metal"]), "-f", spec["func"]]
    subprocess.run(cmd, check=True, capture_output=True, timeout=180)
    agxparse = str(H.TOOLS / "shdump" / "agxparse.py")
    off = int(subprocess.check_output(
        [sys.executable, "-B", agxparse, str(arch), "--locate", "_agc.main"],
        text=True, timeout=60).split()[0])
    hexstr = subprocess.check_output(
        [sys.executable, "-B", agxparse, str(arch), "--extract-hex"],
        text=True, timeout=60).strip()
    return str(arch), off, bytes.fromhex(hexstr)


ANCHOR_SPEC = {                      # carrier -> (mnemonic, occurrence)
    "u64": ("iadd2", 0),
    "bfe": ("ibfe", 0),
    "shr": ("ibfe", 0),
}


def prepare(bin_dir, work):
    """Compile every carrier ON THIS TARGET, record its region, and resolve
    every splice anchor by tokenizing our own bytes. Returns (mains, anchors,
    report)."""
    mains, anchors, report = {}, {}, {}
    for name in ("synth", "uni", "dag", "bfe", "shr", "u64"):
        arch, off, main = compile_carrier(name, bin_dir, work)
        mains[name] = (arch, off, main)
        toks, leftover = A.tokenize(main)
        rec = {"archive": arch, "main_off": off, "main_len": len(main),
               "main_sha256": hashlib.sha256(main).hexdigest(),
               "tokens": [[o, m, l] for (o, m, l, f) in toks],
               "leftover_bytes": len(leftover),
               "leftover_hex": leftover.hex()}
        if name in ANCHOR_SPEC:
            mn, occ = ANCHOR_SPEC[name]
            aoff, alen, afields = A.find(main, mn, occ)
            ab = main[aoff:aoff + alen]
            A.check_field_setter(ab, mn)
            anchors[name] = (aoff, alen, ab)
            rec["anchor"] = {"mnemonic": mn, "occurrence": occ, "offset": aoff,
                             "length": alen, "bytes": ab.hex(),
                             "fields": afields}
        report[name] = rec
    return mains, anchors, report


# ---------------------------------------------------------------------------
# outcome classification
# ---------------------------------------------------------------------------
def classify(case, status, observed, match, unwritten, nwords):
    if status == "HANG":
        return "hang"
    if status != "OK":
        return "fault"
    if match:
        return "ok"
    if unwritten >= nwords:
        return "not_written"
    first = (observed.get("first_0") or observed.get("first_2") or [])
    for entry in first:
        if entry[0] == 0 and entry[1] in (0, 0.0):
            return "silent_zero"
    return "wrong_value"


def _nwords(carrier):
    return sum(n // 4 for n in C.CARRIERS[carrier]["outs"].values())


# ---------------------------------------------------------------------------
# execution
# ---------------------------------------------------------------------------
def run_carrier(carrier, arms, bin_dir, work, fres, mains, progress, health,
                only_cases=None, repeats=1):
    spec = C.CARRIERS[carrier]
    arch_src, main_off, main = mains[carrier]
    base = Path(arch_src).read_bytes()
    ins = {}
    for idx, (fn, data) in spec["inputs"].items():
        p = Path(work) / fn
        p.write_bytes(data)
        ins[idx] = str(p)
    spdir = Path(work) / "sp"
    spdir.mkdir(exist_ok=True)
    seq = [0]
    runner = [None]
    nw = _nwords(carrier)

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
        """One request on a UNIQUE archive path. EXP-0141's own pilot measured
        a ~7-8 % rate of SPURIOUS CMDBUF_ERROR on byte-identical known-good
        archives when one filename was reused across persistent-runner
        requests; a fresh inode per request drove that to 0/360."""
        seq[0] += 1
        p = spdir / ("%s_%d.bin" % (carrier, seq[0]))
        p.write_bytes(blob)
        try:
            return runner[0].request(archive=str(p), grid=spec["grid"],
                                     tg=spec["tg"], ins=ins, outs=spec["outs"],
                                     timeout=timeout)
        finally:
            try:
                os.unlink(str(p))
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

    def blob_of(case):
        b = bytearray(base)
        if case["kind"] == "synth":
            prog = bytes.fromhex(case["prog"])
            b[main_off:main_off + len(prog)] = prog
        else:
            for rel, hx in case["splice"]:
                by = bytes.fromhex(hx)
                b[main_off + rel:main_off + rel + len(by)] = by
        return bytes(b)

    def measure(case, blob):
        for _ in range(CANARY_RETRIES):
            resp, statuses, classes, innocent, nbad = issue(blob)
            observed, match = C.summarize(carrier, resp["outs"],
                                          case.get("oracle"), case.get("dtype"))
            if resp["status"] != "OK":
                match = False
            unwritten = C.unwritten_words(carrier, resp["outs"])
            observed["unwritten"] = unwritten
            oc = classify(case, resp["status"], observed, match, unwritten, nw)
            if oc in ("fault", "hang") and nbad < 2:
                oc = "nondeterministic"
            if oc in ("fault", "hang"):
                # A failed command buffer returns NO output, so retrying for the
                # sentinel would be a fault storm. `issue()` has already
                # reproduced the failure in >= 2 of 3 non-innocent attempts.
                return (oc, observed, False, resp["status"], statuses, classes,
                        innocent, False)
            if oc != "not_written":
                return (oc, observed, bool(match), resp["status"], statuses,
                        classes, innocent, True)
            time.sleep(0.05)
        return ("not_written", observed, False, resp["status"], statuses,
                classes, innocent, False)

    def emit(rec):
        fres.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")
        fres.flush()
        os.fsync(fres.fileno())

    def health_check(where):
        case = HEALTH[carrier]
        blob = blob_of(case)
        observed, match = {}, False
        for _ in range(CANARY_RETRIES):
            resp, statuses, classes, innocent, nbad = issue(blob)
            observed, match = C.summarize(carrier, resp["outs"],
                                          case.get("oracle"), case.get("dtype"))
            if resp["status"] != "OK":
                match = False
            observed["unwritten"] = C.unwritten_words(carrier, resp["outs"])
            if match:
                break
            time.sleep(0.05)
        emit({"arm": "_HEALTH", "i": len(health), "carrier": carrier,
              "instr": "-", "field": "_baseline_health", "value": 0,
              "bytes": "", "observed": observed, "oracle": case.get("oracle"),
              "match": bool(match), "outcome": "ok" if match else "cascade_suspected",
              "status": resp["status"], "statuses": statuses,
              "fault_classes": classes or None, "innocent_retries": innocent,
              "expect_match": True, "rep": 0,
              "note": "mid-run unmutated-carrier health check at " + where})
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
                return carrier_hangs, "carrier %s baseline failed at start, twice" % carrier
        for arm in arms:
            if cascade:
                break
            arm_hangs = 0
            aborted = None
            t0 = time.time()
            n = -1
            for n, case in enumerate(arm["cases"]):
                if only_cases is not None and (arm["arm"], n) not in only_cases:
                    continue
                blob = blob_of(case)
                for rep in range(repeats):
                    obs_list = [measure(case, blob)]
                    while (len(obs_list) < CONFIRM_ABNORMAL
                           and obs_list[-1][0] not in ("ok", "fault", "hang")):
                        obs_list.append(measure(case, blob))
                        if obs_list[-1][:3] == obs_list[-2][:3]:
                            break
                    keys = [(o[0], json.dumps(o[1], sort_keys=True, default=str))
                            for o in obs_list]
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
                    emit({"arm": arm["arm"], "i": n, "rep": rep,
                          "carrier": carrier, "instr": case["instr"],
                          "field": case["field"], "value": case["value"],
                          "bytes": case["ibytes"], "observed": observed,
                          "oracle": case.get("oracle"), "match": bool(match),
                          "outcome": outcome, "status": status,
                          "rt": case.get("rt"),
                          "statuses": statuses if len(statuses) > 1 else None,
                          "fault_classes": classes or None,
                          "innocent_retries": innocent or None,
                          "observations": len(obs_list) if len(obs_list) > 1 else None,
                          "confirmed": confirmed if len(obs_list) > 1 else None,
                          "expect_match": case["expect_match"],
                          "note": case["note"]})
                    since_health += 1
                    if outcome == "hang":
                        arm_hangs += 1
                        carrier_hangs += 1
                if since_health >= BASELINE_EVERY:
                    since_health = 0
                    if not health_check("%s/%s@%d" % (carrier, arm["arm"], n)):
                        stop(); start()
                        if not health_check("%s/%s@%d-restart" % (carrier, arm["arm"], n)):
                            cascade = ("cascade: %s baseline failed twice at %s case %d"
                                       % (carrier, arm["arm"], n))
                            aborted = cascade
                            break
                if arm_hangs >= HANG_STOP_ARM:
                    aborted = ("arm aborted after %d reproduced hangs at case %d/%d"
                               % (arm_hangs, n + 1, len(arm["cases"])))
                    break
                if carrier_hangs >= HANG_STOP_CARRIER:
                    aborted = "carrier abandoned after %d reproduced hangs" % carrier_hangs
                    break
            progress.append({"arm": arm["arm"], "carrier": carrier,
                             "cases_run": n + 1, "cases_total": len(arm["cases"]),
                             "seconds": round(time.time() - t0, 2),
                             "hangs": arm_hangs, "aborted": aborted})
            print("  %-22s %4d/%-4d %7.2fs%s" % (arm["arm"], n + 1,
                  len(arm["cases"]), time.time() - t0,
                  "  ABORTED: " + aborted if aborted else ""), flush=True)
            if carrier_hangs >= HANG_STOP_CARRIER:
                break
        if not cascade:
            health_check("%s:end" % carrier)
    finally:
        stop()
    return carrier_hangs, cascade


HEALTH = {}


def gpu_neighbours():
    """FIELD-SWEEP-PROTOCOL 7.4: record how much OTHER GPU work was running."""
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


def env_report():
    def sh(*c):
        try:
            return subprocess.check_output(c, text=True, timeout=20).strip()
        except Exception as e:
            return "ERR:" + type(e).__name__
    return {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "hw_model": sh("sysctl", "-n", "hw.model"),
            "os_version": sh("sw_vers", "-productVersion"),
            "os_build": sh("sw_vers", "-buildVersion"),
            "python": sys.version.split()[0],
            "clang": sh("clang", "--version").splitlines()[0] if sh("clang", "--version") else "",
            "gpu": [l.strip() for l in sh("system_profiler", "SPDisplaysDataType").splitlines()
                    if "Chipset Model" in l or "Total Number of Cores" in l],
            "tool_sha256": {p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
                            for p in [str(H.TOOLS / "agx-isa" / "db.json"),
                                      str(H.TOOLS / "agx-isa" / "isadb.py"),
                                      str(H.TOOLS / "agxtest" / "persistrun.py")]},
            "kernel_sha256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest()
                              for f in sorted((EXP / "kernels").glob("*.metal"))},
            "harness_sha256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest()
                               for f in sorted((EXP / "harness").glob("*.py"))},
            "target": "G17P"}


ORDER = ("synth", "uni", "dag", "bfe", "shr", "u64")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--bin-dir", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--only-carrier", default=None)
    ap.add_argument("--arms-regex", default=None)
    ap.add_argument("--max-cases", type=int, default=0,
                    help="smoke only: cap the cases per arm")
    ap.add_argument("--revalidate", default=None,
                    help="path to a previous sweep.jsonl; re-run only its "
                         "non-ok cases")
    ap.add_argument("--repeats", type=int, default=1)
    a = ap.parse_args()
    work = Path(a.work); work.mkdir(parents=True, exist_ok=True)
    raw = Path(a.raw); raw.mkdir(parents=True, exist_ok=True)

    (raw / "00_env.json").write_text(json.dumps(env_report(), indent=1, sort_keys=True) + "\n")

    mains, anchors, report = prepare(a.bin_dir, work)
    (raw / "00_build.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    mainlens = dict((k, len(v[2])) for k, v in mains.items())
    arms = CS.build_all(mainlens, anchors)

    # the health-check case for each carrier is that carrier's own _baseline
    for arm in arms:
        if arm["carrier"] not in HEALTH:
            for c in arm["cases"]:
                if c["field"] == "_baseline":
                    HEALTH[arm["carrier"]] = c
                    break
    missing = [c for c in ORDER if c not in HEALTH]
    if missing:
        raise SystemExit("no _baseline health case for carriers %r" % missing)

    if a.arms_regex:
        rx = re.compile(a.arms_regex)
        arms = [x for x in arms if rx.search(x["arm"])]
    if a.max_cases:
        for x in arms:
            x["cases"] = x["cases"][:a.max_cases]

    only_cases = None
    if a.revalidate:
        only_cases = set()
        with open(a.revalidate) as f:
            for line in f:
                r = json.loads(line)
                if r["arm"] == "_HEALTH":
                    continue
                if r["outcome"] != "ok":
                    only_cases.add((r["arm"], r["i"]))
        print("revalidating %d distinct non-ok cases" % len(only_cases), flush=True)

    by_carrier = {}
    for arm in arms:
        by_carrier.setdefault(arm["carrier"], []).append(arm)

    manifest = {"run_id": a.run_id, "target": "G17P",
                "mainlens": mainlens,
                "anchors": dict((k, {"offset": v[0], "length": v[1],
                                     "bytes": v[2].hex()})
                                for k, v in anchors.items()),
                "arms": [{"arm": x["arm"], "carrier": x["carrier"],
                          "instr": x["instr"], "field": x["field"],
                          "n_cases": len(x["cases"]), "doc": x["doc"]}
                         for x in arms],
                "n_cases": sum(len(x["cases"]) for x in arms),
                "revalidate_source": a.revalidate, "repeats": a.repeats}
    (raw / "00_manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")

    progress, health, cascades = [], [], []
    order = [c for c in ORDER if c in by_carrier and (a.only_carrier in (None, c))]
    conc_start = gpu_neighbours()
    with open(str(raw / "sweep.jsonl"), "a") as fres:
        for cname in order:
            print("carrier %s (%d arms)" % (cname, len(by_carrier[cname])), flush=True)
            _, cascade = run_carrier(cname, by_carrier[cname], a.bin_dir, work,
                                     fres, mains, progress, health,
                                     only_cases=only_cases, repeats=a.repeats)
            if cascade:
                cascades.append(cascade)
                print("  CASCADE: " + cascade, flush=True)
            (raw / "01_progress.json").write_text(json.dumps(
                {"arms": progress, "health_checks": health, "cascades": cascades,
                 "concurrency_start": conc_start,
                 "concurrency_end": gpu_neighbours()}, indent=1) + "\n")
    print("DONE %s: %d cases planned" % (a.run_id, manifest["n_cases"]))


if __name__ == "__main__":
    main()
