#!/usr/bin/env python3
"""EXP-0157 sweep executor (G17P).

Runs every arm of `cases.ARMS` against the A18 Pro and APPENDS one JSON record
per case to `raw/<run_id>/sweep.jsonl`, flushing + fsync-ing after every record.
Nothing is buffered: a kill at any point loses at most the case in flight.

Structure is adapted from `EXP-0153-g17p-revalidation/harness/run.py` (same
project, same rules, same fault-adjudication) with three changes this
experiment needs:

  1. carriers that declare `accel` are driven through `runner_as.PersistRunnerAS`,
     which binds an MTLAccelerationStructure -- the testbed gap EXP-0146 hit;
  2. anchors are resolved by a RESYNC walk (`analysis/resync.py`) because the
     ray-query carriers are 8-25 kB and do not tokenize end-to-end, and every
     anchor then has to pass the two pre-registered LIVENESS controls before any
     field of it is swept;
  3. `--replay` re-runs a previous run's RESOLVED case list, so the second gated
     run compares like with like even though offsets are discovered on target.

Safety (FIELD-SWEEP-PROTOCOL section 7): per-request watchdog; InnocentVictim
failures retried and segregated; a `fault` verdict requires reproduction in at
least 2 of 3 non-innocent attempts; periodic unmutated-carrier health checks;
two reproduced hangs abort an arm, six abandon a carrier.
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
sys.path.insert(0, str(EXP / "analysis"))
import anchors as A           # noqa: E402
import carriers as C          # noqa: E402
import cases as CS            # noqa: E402
from resync import walk       # noqa: E402
from runner_as import PersistRunnerAS  # noqa: E402
from persistrun import PersistRunner   # noqa: E402

# POST-FREEZE carrier extension (recorded as a deviation in RESULTS.md).
if "bbox" in os.environ.get("EXTRA_CARRIERS", ""):
    import carriers_bbox
    carriers_bbox.register()

TOOLS = Path(os.environ.get("AGX_TOOLS", str(Path.home() / "agxre" / "tools")))
FAULT_RX = re.compile(r"kIOGPUCommandBufferCallbackError\w+")

HANG_STOP_ARM = 2
HANG_STOP_CARRIER = 6
REQ_TIMEOUT = 12.0
INNOCENT_RETRIES = 6
CONFIRM_ATTEMPTS = 3
BASELINE_EVERY = 120
CANARY_RETRIES = 3
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
    return e.strip()[:80]


def is_innocent(resp):
    fc = fault_class(resp) or ""
    return "InnocentVictim" in fc or "Discarded (victim" in (resp.get("error") or "")


def compile_carrier(name, bin_dir, out_dir):
    spec = C.CARRIERS[name]
    arch = Path(out_dir) / ("carrier_%s_%s.bin" % (name, spec["func"]))
    cmd = [str(Path(bin_dir) / "shdump"), "-o", str(arch), "--no-fast-math",
           str(EXP / spec["metal"]), "-f", spec["func"]]
    subprocess.run(cmd, check=True, capture_output=True, timeout=300)
    agxparse = str(TOOLS / "shdump" / "agxparse.py")
    off = int(subprocess.check_output(
        [sys.executable, "-B", agxparse, str(arch), "--locate", "_agc.main"],
        text=True, timeout=120).split()[0])
    hexstr = subprocess.check_output(
        [sys.executable, "-B", agxparse, str(arch), "--extract-hex"],
        text=True, timeout=120).strip()
    return str(arch), off, bytes.fromhex(hexstr)


def prepare(bin_dir, work, wanted):
    """Compile every needed carrier ON THIS TARGET, record its region, and
    resolve candidate anchors by a resync walk of OUR OWN bytes."""
    mains, report = {}, {}
    for name in wanted:
        arch, off, main = compile_carrier(name, bin_dir, work)
        toks = walk(main)
        mains[name] = (arch, off, main, toks)
        import isadb
        _, strict_left = isadb.disassemble(main)
        report[name] = {
            "archive": arch, "main_off": off, "main_len": len(main),
            "main_sha256": hashlib.sha256(main).hexdigest(),
            "strict_leftover_bytes": len(strict_left),
            "resync_tokens": len(toks),
            "resync_tokens_clean_predecessor": sum(1 for t in toks if not t["after_gap"]),
        }
    return mains, report


def resolve_anchors(mains, max_per):
    """(arm, carrier, mnemonic) -> [ {offset,length,bytes,after_gap} ], choosing
    tokens whose immediate predecessor decoded cleanly first."""
    out = {}
    for arm, carrier, mn, n in CS.ARMS:
        if carrier not in mains:
            continue
        toks = mains[carrier][3]
        hits = [t for t in toks if t["mnemonic"] == mn]
        hits.sort(key=lambda t: (t["after_gap"], t["offset"]))
        out[(arm, carrier, mn)] = [
            {"offset": t["offset"], "length": t["length"], "bytes": t["bytes"],
             "after_gap": t["after_gap"]} for t in hits[:max(n, max_per)]]
    return out


def classify(status, match, unwritten, nwords, sentinel, observed):
    if status == "HANG":
        return "hang"
    if status != "OK":
        return "fault"
    if match:
        return "ok"
    if unwritten >= nwords:
        return "not_written"
    if sentinel is False:
        return "not_written"
    first = []
    for k, v in observed.items():
        if k.startswith("first_"):
            first = v
            break
    for entry in first:
        if entry[1] in (0, 0.0):
            return "silent_zero"
    return "wrong_value"


def nwords(carrier):
    return sum(n // 4 for n in C.CARRIERS[carrier]["outs"].values())


class CarrierSession:
    def __init__(self, carrier, bin_dir, work, mains):
        self.carrier = carrier
        self.spec = C.CARRIERS[carrier]
        self.bin_dir = Path(bin_dir)
        self.work = Path(work)
        self.arch_src, self.main_off, self.main, _ = mains[carrier]
        self.base = Path(self.arch_src).read_bytes()
        self.ins = {}
        for idx, (fn, data) in self.spec["inputs"].items():
            p = self.work / fn
            p.write_bytes(data)
            self.ins[idx] = str(p)
        self.spdir = self.work / "sp"
        self.spdir.mkdir(exist_ok=True)
        self.seq = 0
        self.runner = None
        self.nw = nwords(carrier)

    def start(self):
        exe_as = str(self.bin_dir / "agxrun_persist_as")
        exe = str(self.bin_dir / "agxrun_persist")
        src = str(EXP / self.spec["metal"])
        if self.spec.get("accel") is not None:
            self.runner = PersistRunnerAS(
                source=src, function=self.spec["func"], fast_math=False,
                agxrun_persist=exe_as, accel=self.spec["accel"],
                accel_kind=self.spec.get("accel_kind", "primitive"))
        else:
            self.runner = PersistRunner(source=src, function=self.spec["func"],
                                        fast_math=False, agxrun_persist=exe)

    def stop(self):
        try:
            if self.runner:
                self.runner.close()
        except Exception:
            pass
        self.runner = None

    def submit(self, blob, timeout=REQ_TIMEOUT):
        self.seq += 1
        p = self.spdir / ("%s_%d.bin" % (self.carrier, self.seq))
        p.write_bytes(blob)
        try:
            return self.runner.request(archive=str(p), grid=self.spec["grid"],
                                       tg=self.spec["tg"], ins=self.ins,
                                       outs=self.spec["outs"], timeout=timeout)
        finally:
            try:
                os.unlink(str(p))
            except OSError:
                pass

    def issue(self, blob):
        statuses, classes, innocent = [], [], 0
        resp = self.submit(blob)
        while resp["status"] != "OK" and is_innocent(resp) and innocent < INNOCENT_RETRIES:
            classes.append(fault_class(resp))
            innocent += 1
            time.sleep(0.08 * innocent)
            resp = self.submit(blob)
        statuses.append(resp["status"])
        if resp["status"] != "OK":
            classes.append(fault_class(resp))
        best = resp
        if resp["status"] != "OK":
            for _ in range(CONFIRM_ATTEMPTS - 1):
                r2 = self.submit(blob)
                inn = 0
                while r2["status"] != "OK" and is_innocent(r2) and inn < INNOCENT_RETRIES:
                    classes.append(fault_class(r2))
                    inn += 1
                    time.sleep(0.08 * inn)
                    r2 = self.submit(blob)
                statuses.append(r2["status"])
                if r2["status"] != "OK":
                    classes.append(fault_class(r2))
                else:
                    best = r2
        nbad = sum(1 for s in statuses if s != "OK")
        return best, statuses, classes, innocent, nbad

    def blob_of(self, case):
        b = bytearray(self.base)
        if case.get("prog"):
            prog = bytes.fromhex(case["prog"])
            b[self.main_off:self.main_off + len(prog)] = prog
        for rel, hx in case.get("splice", []):
            by = bytes.fromhex(hx)
            b[self.main_off + rel:self.main_off + rel + len(by)] = by
        return bytes(b)

    def measure(self, case, blob):
        observed = {}
        for _ in range(CANARY_RETRIES):
            resp, statuses, classes, innocent, nbad = self.issue(blob)
            observed, match = C.summarize(self.carrier, resp["outs"],
                                          case.get("oracle"))
            if resp["status"] != "OK":
                match = False
            unw = C.unwritten_words(self.carrier, resp["outs"])
            sent = C.sentinel_ok(self.carrier, resp["outs"])
            observed["unwritten"] = unw
            observed["sentinel"] = sent
            oc = classify(resp["status"], match, unw, self.nw, sent, observed)
            if oc in ("fault", "hang") and nbad < 2:
                oc = "nondeterministic"
            if oc in ("fault", "hang"):
                return (oc, observed, False, resp["status"], statuses, classes, innocent)
            if oc != "not_written":
                return (oc, observed, bool(match), resp["status"], statuses,
                        classes, innocent)
            time.sleep(0.05)
        return ("not_written", observed, False, resp["status"], statuses,
                classes, innocent)


def emit(f, rec):
    f.write(json.dumps(rec, sort_keys=True, separators=(",", ":"), default=str) + "\n")
    f.flush()
    os.fsync(f.fileno())


def gpu_neighbours():
    try:
        out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,comm="], text=True,
                             capture_output=True, timeout=20).stdout
    except Exception as e:
        return {"error": type(e).__name__}
    mine, others = [], []
    me = os.getpid()
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        pid, ppid, comm = parts
        nm = Path(comm.strip()).name
        if nm.startswith(("agxrun", "agxrender", "shdump")):
            (mine if int(ppid) == me else others).append(nm)
    return {"own_runner_processes": sorted(mine),
            "other_gpu_runner_processes": sorted(others), "n_other": len(others)}


def env_report():
    def sh(*c):
        try:
            return subprocess.check_output(c, text=True, timeout=30).strip()
        except Exception as e:
            return "ERR:" + type(e).__name__
    return {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "hw_model": sh("sysctl", "-n", "hw.model"),
            "os_version": sh("sw_vers", "-productVersion"),
            "os_build": sh("sw_vers", "-buildVersion"),
            "python": sys.version.split()[0],
            "gpu": [l.strip() for l in sh("system_profiler", "SPDisplaysDataType").splitlines()
                    if "Chipset Model" in l or "Total Number of Cores" in l],
            "tool_sha256": {p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
                            for p in [str(TOOLS / "agx-isa" / "db.json"),
                                      str(TOOLS / "agx-isa" / "isadb.py"),
                                      str(TOOLS / "agxtest" / "persistrun.py")]},
            "kernel_sha256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest()
                              for f in sorted((EXP / "kernels").glob("*.metal"))},
            "harness_sha256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest()
                               for f in sorted((EXP / "harness").glob("*.*"))},
            "neighbours": gpu_neighbours(),
            "target": "G17P"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--bin-dir", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--arms", default=None, help="comma list of arm letters")
    ap.add_argument("--only-carrier", default=None)
    ap.add_argument("--carriers", default=None,
                    help="comma list; filters BOTH the carriers compiled and the "
                         "replayed groups. Used for a TARGETED second capture when "
                         "a full replay is not affordable.")
    ap.add_argument("--max-cases", type=int, default=0)
    ap.add_argument("--max-anchors", type=int, default=2,
                    help="how many candidate anchors per (carrier,instr) to LIVENESS-SCAN")
    ap.add_argument("--sweep-anchors", type=int, default=1,
                    help="how many LIVE anchors per (carrier,instr) to field-sweep")
    ap.add_argument("--replay", default=None, help="00_cases.json from a prior run")
    ap.add_argument("--revalidate", default=None, help="sweep.jsonl; re-run its non-ok cases")
    ap.add_argument("--revalidate-outcomes", default="fault,hang,nondeterministic",
                    help="which outcomes to re-run; 'all' means every non-ok case. "
                         "FIELD-SWEEP-PROTOCOL 7A: a fault/hang verdict must be "
                         "confirmed under the GPU LEASE, not merely by "
                         "majority-of-3 in an unlocked run.")
    ap.add_argument("--repeats", type=int, default=1,
                    help="run each selected case this many times (7A: 5 under the lease)")
    a = ap.parse_args()

    work = Path(a.work); work.mkdir(parents=True, exist_ok=True)
    raw = Path(a.raw); raw.mkdir(parents=True, exist_ok=True)
    (raw / "00_env.json").write_text(json.dumps(env_report(), indent=1, sort_keys=True) + "\n")

    armset = set((a.arms or "R,S,H").split(","))
    only = set(a.carriers.split(",")) if a.carriers else None
    wanted = sorted({c for (arm, c, mn, n) in CS.ARMS
                     if arm in armset and (not a.only_carrier or c == a.only_carrier)
                     and (only is None or c in only)})
    mains, build = prepare(a.bin_dir, work, wanted)
    (raw / "00_build.json").write_text(json.dumps(build, indent=1, sort_keys=True) + "\n")

    if a.replay:
        resolved = json.load(open(a.replay))
        resolved = [g for g in resolved if g["carrier"] in mains]
    else:
        anc = resolve_anchors(mains, max(a.max_anchors, 1))
        resolved = []
        for arm, carrier, mn, n in CS.ARMS:
            if arm not in armset or carrier not in mains:
                continue
            for k, an in enumerate(anc.get((arm, carrier, mn), [])):
                ib = bytes.fromhex(an["bytes"])
                resolved.append({
                    "arm": arm, "carrier": carrier, "instr": mn, "anchor_idx": k,
                    "anchor": an,
                    "liveness": CS.liveness_cases(mn, an["offset"], ib),
                    "sweep": CS.sweep_cases(mn, an["offset"], ib)})
        (raw / "00_cases.json").write_text(json.dumps(resolved, indent=1) + "\n")

    reval = None
    if a.revalidate:
        want = None if a.revalidate_outcomes == "all" else set(
            a.revalidate_outcomes.split(","))
        reval = set()
        with open(a.revalidate) as f:
            for line in f:
                r = json.loads(line)
                if str(r.get("field", "")).startswith("_"):
                    continue
                oc = r.get("outcome")
                if oc == "ok":
                    continue
                if want is not None and oc not in want:
                    continue
                reval.add((r["arm"], r["carrier"], r["instr"], r["anchor_idx"],
                           r["field"], r["value"]))
        print("revalidating %d cases (outcomes=%s) x%d repeats"
              % (len(reval), a.revalidate_outcomes, a.repeats), flush=True)

    manifest = {"run_id": a.run_id, "target": "G17P", "arms": sorted(armset),
                "carriers": wanted, "max_anchors": a.max_anchors,
                "n_groups": len(resolved),
                "n_cases": sum(len(g["liveness"]) + len(g["sweep"]) for g in resolved),
                "replay": a.replay, "revalidate": a.revalidate}
    (raw / "00_manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print("groups=%d cases=%d" % (manifest["n_groups"], manifest["n_cases"]), flush=True)

    fres = open(raw / "sweep.jsonl", "a")
    progress = []
    by_carrier = {}
    for g in resolved:
        by_carrier.setdefault(g["carrier"], []).append(g)

    for carrier, groups in by_carrier.items():
        sess = CarrierSession(carrier, a.bin_dir, work, mains)
        base_case = CS.baseline_case(carrier)
        # Starting an AS carrier means BUILDING the acceleration structure, and
        # on a busy device that build is repeatedly discarded as an innocent
        # victim of a sibling's fault. The runner already retries internally;
        # this retries the whole process a few times on top, with backoff, so a
        # contamination storm delays the run instead of voiding it.
        started, start_err = False, None
        for attempt in range(4):
            try:
                sess.start(); started = True; break
            except Exception as e:
                start_err = e
                sess.stop()
                time.sleep(5.0 * (attempt + 1))
        if not started:
            emit(fres, {"arm": "_ERROR", "carrier": carrier, "instr": "-",
                        "field": "_start", "value": 0, "anchor_idx": -1,
                        "outcome": "fault",
                        "note": "runner start failed 4x: %r" % start_err})
            continue
        carrier_hangs = 0
        since_health = 0
        try:
            def health(where):
                blob = sess.blob_of(base_case)
                oc, obs, m, st, sts, cls, inn = sess.measure(base_case, blob)
                emit(fres, {"arm": "_HEALTH", "carrier": carrier, "instr": "-",
                            "field": "_baseline", "value": 0, "anchor_idx": -1,
                            "observed": obs, "match": bool(m),
                            "outcome": "ok" if m else "cascade_suspected",
                            "status": st, "statuses": sts, "fault_classes": cls or None,
                            "expect_match": True, "note": "health @" + where})
                return bool(m)

            if not health(carrier + ":start"):
                sess.stop(); sess.start()
                if not health(carrier + ":restart"):
                    progress.append({"carrier": carrier, "aborted": "baseline failed twice"})
                    continue
            swept = {}
            for g in groups:
                arm_hangs = 0
                aborted = None
                t0 = time.time()
                live = None
                todo = [("L", c) for c in g["liveness"]]
                ran = 0
                for phase, case in todo:
                    key = (g["arm"], carrier, g["instr"], g["anchor_idx"],
                           case["field"], case["value"])
                    if reval is not None and key not in reval:
                        continue
                    blob = sess.blob_of(case)
                    oc, obs, m, st, sts, cls, inn = sess.measure(case, blob)
                    emit(fres, {"arm": g["arm"], "carrier": carrier, "instr": g["instr"],
                                "anchor_idx": g["anchor_idx"], "anchor": g["anchor"]["offset"],
                                "after_gap": g["anchor"]["after_gap"],
                                "field": case["field"], "value": case["value"],
                                "bytes": case["ibytes"], "observed": obs,
                                "match": bool(m), "outcome": oc, "status": st,
                                "statuses": sts if len(sts) > 1 else None,
                                "fault_classes": cls or None,
                                "innocent_retries": inn or None,
                                "expect_match": case["expect_match"],
                                "note": case["note"]})
                    ran += 1
                    since_health += 1
                    if oc == "hang":
                        arm_hangs += 1; carrier_hangs += 1
                    # `nondeterministic` is a statement about the MACHINE (a
                    # sibling's fault landing in our command buffer), not about
                    # this offset, so it never counts as evidence of liveness.
                    if oc in ("silent_zero", "wrong_value", "not_written",
                              "fault", "hang"):
                        live = True
                if live is None:
                    live = False
                emit(fres, {"arm": g["arm"], "carrier": carrier, "instr": g["instr"],
                            "anchor_idx": g["anchor_idx"], "anchor": g["anchor"]["offset"],
                            "after_gap": g["anchor"]["after_gap"],
                            "field": "_ANCHOR_VERDICT", "value": int(bool(live)),
                            "bytes": g["anchor"]["bytes"], "observed": {}, "match": None,
                            "outcome": "live" if live else "inert_or_unreached",
                            "status": "-", "expect_match": None,
                            "note": "LIVE iff L1 or L2 moved the output off baseline"})
                key_ci = (g["arm"], g["instr"])
                if not live and reval is None:
                    progress.append({"arm": g["arm"], "carrier": carrier,
                                     "instr": g["instr"], "anchor_idx": g["anchor_idx"],
                                     "cases_run": ran, "live": False})
                    print("  %-3s %-10s %-16s a%d  INERT (liveness controls reproduced "
                          "the baseline)" % (g["arm"], carrier, g["instr"],
                                             g["anchor_idx"]), flush=True)
                    continue
                if reval is None and swept.get(key_ci, 0) >= a.sweep_anchors:
                    progress.append({"arm": g["arm"], "carrier": carrier,
                                     "instr": g["instr"], "anchor_idx": g["anchor_idx"],
                                     "cases_run": ran, "live": True,
                                     "aborted": "live, but sweep-anchors budget already met"})
                    continue
                swept[key_ci] = swept.get(key_ci, 0) + 1
                cases = g["sweep"]
                if a.max_cases:
                    cases = cases[:a.max_cases]
                for i, case in enumerate(cases):
                    key = (g["arm"], carrier, g["instr"], g["anchor_idx"],
                           case["field"], case["value"])
                    if reval is not None and key not in reval:
                        continue
                    blob = sess.blob_of(case)
                    for rep in range(a.repeats):
                        oc, obs, m, st, sts, cls, inn = sess.measure(case, blob)
                        emit(fres, {"arm": g["arm"], "carrier": carrier, "instr": g["instr"],
                                    "anchor_idx": g["anchor_idx"], "anchor": g["anchor"]["offset"],
                                    "after_gap": g["anchor"]["after_gap"],
                                    "field": case["field"], "value": case["value"],
                                    "rep": rep,
                                    "bytes": case["ibytes"], "observed": obs,
                                    "match": bool(m), "outcome": oc, "status": st,
                                    "statuses": sts if len(sts) > 1 else None,
                                    "fault_classes": cls or None,
                                    "innocent_retries": inn or None,
                                    "expect_match": case["expect_match"],
                                    "note": case["note"]})
                        ran += 1
                        since_health += 1
                        if oc == "hang":
                            arm_hangs += 1; carrier_hangs += 1
                    if since_health >= BASELINE_EVERY:
                        since_health = 0
                        if not health("%s/%s@%d" % (carrier, g["instr"], i)):
                            sess.stop(); sess.start()
                            if not health("%s/%s@%d-restart" % (carrier, g["instr"], i)):
                                aborted = "cascade"
                                break
                    if arm_hangs >= HANG_STOP_ARM:
                        aborted = "arm aborted after %d reproduced hangs at case %d/%d" % (
                            arm_hangs, i + 1, len(cases))
                        break
                    if carrier_hangs >= HANG_STOP_CARRIER:
                        aborted = "carrier abandoned after %d hangs" % carrier_hangs
                        break
                progress.append({"arm": g["arm"], "carrier": carrier, "instr": g["instr"],
                                 "anchor_idx": g["anchor_idx"], "cases_run": ran,
                                 "cases_total": len(cases) + len(g["liveness"]),
                                 "seconds": round(time.time() - t0, 2),
                                 "hangs": arm_hangs, "live": bool(live), "aborted": aborted})
                (raw / "01_progress.json").write_text(json.dumps(progress, indent=1) + "\n")
                print("  %-3s %-10s %-16s a%d  %5d cases %7.2fs %s" % (
                    g["arm"], carrier, g["instr"], g["anchor_idx"], ran,
                    time.time() - t0, ("ABORTED: " + aborted) if aborted else
                    ("" if live else "INERT")), flush=True)
                if carrier_hangs >= HANG_STOP_CARRIER:
                    break
            health(carrier + ":end")
        finally:
            sess.stop()
    fres.close()
    (raw / "01_progress.json").write_text(json.dumps(progress, indent=1) + "\n")
    (raw / "02_neighbours_end.json").write_text(json.dumps(gpu_neighbours(), indent=1) + "\n")
    print("done", flush=True)


if __name__ == "__main__":
    main()
