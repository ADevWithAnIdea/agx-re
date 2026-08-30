#!/usr/bin/env python3
"""EXP-0200 target-2 sweep driver (runs ON THE NEO, under ~/agxre/EXP-0200).

  python3 run200.py --run-id g17p_YYYYMMDD_t2runNN --arms harness/arms200.json
  python3 run200.py --run-id prefreeze/holeprobe01 --probe-holes    # calibration

One JSON object per case is appended to `raw/<run_id>/sweep.jsonl` and
flush+fsync'd immediately -- never buffered. The host has crashed mid-run
before; a kill must cost at most one case.

FROZEN BEHAVIOURS (PRE_REGISTRATION.md section 8):

* **NO ABORT PATH.** No per-arm or per-field hang budget. FIELD-SWEEP-PROTOCOL
  3(c): a budget cannot characterise a CONTIGUOUS hazard, it guarantees the
  region is never mapped. Every fill of every arm is dispatched.
* **A malformed response is a MEASUREMENT FAILURE, not a hang** (3d), through
  the pinned upstreamed saferunner with one reader thread per child.
* **Poisoned read-back, integrity sentinel, OS fault-classification string** on
  every case. Here the poison is the ruler's ONLY observable: `out[0]` still
  holding `0xDEADBEEF` while `out[1]` holds 7.5 is the signature of *the
  program ran and halted at the stop we planted*.
* **The tokenized mnemonic of the WRITTEN bytes is recorded on every case**, so
  a result that is really a different instruction is visible in the raw.
* **Never conclude `fault` from a single observation**: every non-OK case is
  re-run to majority-of-3, `InnocentVictim` retried first.

CLEAN-ROOM: OWN-SHADER + HW-PROBE. Every byte dispatched is the compiled form of
our own MSL, overwritten with byte values we chose. No Apple binary is
disassembled.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "harness"))
sys.path.insert(0, str(HERE / "t1" / "harness"))

import carriers200 as C          # noqa: E402
import locate200 as L            # noqa: E402
import words200 as W             # noqa: E402
import saferunner187 as SR       # noqa: E402  (EXP-0187's wrapper, used VERBATIM)

PINNED = L.PINNED
SafeRunner, SafeRunnerAS = SR.make_classes(str(HERE / "t1" / "pinned"))

REQ_TIMEOUT = 8.0
REQ_TIMEOUT_RT = 10.0
CONFIRM_ATTEMPTS = 3
INNOCENT_RETRIES = 3
CANARY_RETRIES = 3
BASELINE_EVERY = 120
BIN = HERE / "work" / "bin"
WORK = HERE / "work"


def fault_class(resp):
    e = resp.get("error") or ""
    for k in ("InnocentVictim", "ErrorHang", "ErrorTimeout", "ErrorPageFault",
              "ErrorInvalidResource", "ErrorAccessViolation", "ErrorInnocent"):
        if k in e:
            return k
    return e[:160]


def is_innocent(resp):
    return "InnocentVictim" in (resp.get("error") or "")


class CarrierRunner:
    def __init__(self, name):
        self.name = name
        self.spec = C.CARRIERS[name]
        self.seq = 0
        self.spdir = WORK / "splice"
        self.spdir.mkdir(parents=True, exist_ok=True)
        indir = WORK / "inputs"
        indir.mkdir(parents=True, exist_ok=True)
        self.ins = {}
        for idx, (fn, blob) in C.out_inputs(name).items():
            p = indir / fn
            p.write_bytes(blob)
            self.ins[idx] = str(p)
        self.timeout = REQ_TIMEOUT_RT if self.spec["accel"] is not None else REQ_TIMEOUT
        arch, off, main = L.compile_carrier(
            BIN, HERE / self.spec["metal"], self.spec["func"], WORK / "arch")
        self.archive = arch
        self.main_off = off
        self.main = main
        self.main_sha = hashlib.sha256(main).hexdigest()
        self.base = Path(arch).read_bytes()
        exe = str(BIN / "agxrun_persist_as")
        self.runner = SafeRunnerAS(
            source=str(HERE / self.spec["metal"]), function=self.spec["func"],
            fast_math=False, agxrun_persist=exe,
            accel=self.spec["accel"], accel_kind=self.spec["accel_kind"] or "primitive")
        self.device = self.runner.device

    def close(self):
        try:
            self.runner.close()
        except Exception:                                       # noqa: BLE001
            pass

    def mutated_main(self, off, fill):
        m = bytearray(self.main)
        if off is not None:
            m[off:off + len(fill)] = fill
        return bytes(m)

    def blob(self, off, fill):
        b = bytearray(self.base)
        if off is not None:
            s = self.main_off + off
            b[s:s + len(fill)] = fill
        return bytes(b)

    def submit(self, blob):
        self.seq += 1
        p = self.spdir / ("%s_%d.bin" % (self.name, self.seq))
        p.write_bytes(blob)
        try:
            return self.runner.request(
                archive=str(p), grid=self.spec["grid"], tg=self.spec["tg"],
                ins=self.ins, outs={0: 4 * self.spec["nwords"]},
                timeout=self.timeout)
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
                while (r2["status"] != "OK" and is_innocent(r2)
                       and inn < INNOCENT_RETRIES):
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

    def measure(self, blob):
        observed, match, resp = {}, False, {"status": "NONE"}
        statuses, classes, innocent = [], [], 0
        for _ in range(CANARY_RETRIES):
            resp, statuses, classes, innocent, nbad = self.issue(blob)
            if resp["status"] == "HANG":
                return ("hang", {"status": "HANG"}, False, "HANG",
                        statuses, classes, innocent)
            if resp["status"] == "MALFORMED":
                return ("measurement_failure",
                        {"status": "MALFORMED", "raw": resp.get("raw")}, False,
                        "MALFORMED", statuses, classes, innocent)
            blob_out = resp["outs"].get(0, b"")
            if not blob_out:
                return ("fault" if nbad >= 2 else "nondeterministic",
                        {"status": resp["status"]}, False, resp["status"],
                        statuses, classes, innocent)
            observed, words = C.summarize(self.name, blob_out)
            observed["status"] = resp["status"]
            observed["sentinel_ok"] = C.sentinel_ok(self.name, words)
            observed["tail_ok"] = C.tail_ok(self.name, words)
            observed["unwritten"] = C.unwritten(self.name, words)
            observed["gputime_ns"] = resp.get("gputime_ns")
            if resp["status"] != "OK":
                return ("fault" if nbad >= 2 else "nondeterministic", observed,
                        False, resp["status"], statuses, classes, innocent)
            # OK + nothing written at all (sentinel included) is an INVALID RUN,
            # not a result: EXP-0160 saw 25 such dispatches with no victim
            # string anywhere.
            if not observed["sentinel_ok"] and \
                    len(observed["unwritten"]) == len(self.spec["val_words"]):
                time.sleep(0.05)
                continue
            match = C.match_oracle(self.name, blob_out)
            if match:
                oc = "ok"
            elif len(observed["unwritten"]) == len(self.spec["val_words"]):
                # THE RULER'S POSITIVE SIGNAL: the sentinel proves the program
                # ran; the untouched poison proves the result store was never
                # reached. Only reachable because the buffer is poisoned.
                oc = "not_written"
            elif all(v == 0 for v in observed["vals_u32"]):
                oc = "silent_zero"
            else:
                oc = "wrong_value"
            if not observed["sentinel_ok"]:
                oc = "invalid_run"
                time.sleep(0.05)
                continue
            return (oc, observed, bool(match), resp["status"], statuses,
                    classes, innocent)
        return ("invalid_run", observed, False, resp.get("status"), statuses,
                classes, innocent)


def emit(f, rec):
    f.write(json.dumps(rec, sort_keys=True, separators=(",", ":"), default=str) + "\n")
    f.flush()
    os.fsync(f.fileno())


def env_report(run_dir, arms_path, run_id):
    def sh(*c):
        try:
            return subprocess.check_output(c, text=True, timeout=30).strip()
        except Exception as e:                                  # noqa: BLE001
            return "ERR %s" % e
    rep = {
        "run_id": run_id,
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host": sh("hostname"), "os": sh("sw_vers", "-productVersion"),
        "build": sh("sw_vers", "-buildVersion"),
        "cpu": sh("sysctl", "-n", "machdep.cpu.brand_string"),
        "python": sys.version.split()[0],
        "pinned_db_sha256": hashlib.sha256((PINNED / "db.json").read_bytes()).hexdigest(),
        "pinned_isadb_sha256": hashlib.sha256((PINNED / "isadb.py").read_bytes()).hexdigest(),
        "arms_sha256": (hashlib.sha256(Path(arms_path).read_bytes()).hexdigest()
                        if arms_path and Path(arms_path).exists() else None),
        "concurrent_gpu_procs": sh(
            "bash", "-lc",
            "ps -Ao pid,comm | grep -E 'agxrun|rendersweep|gfrun|shdump' "
            "| grep -v grep | head -40"),
    }
    (run_dir / "env.json").write_text(json.dumps(rep, indent=1))
    return rep


def case_record(cr, a, fill, res, extra):
    oc, obs, m, st, sts, cls, inn = res
    mm = cr.mutated_main(a["off"], fill)
    rec = {"carrier": a["carrier"], "arm": a["arm"], "instr": extra["instr"],
           "field": "_instruction", "value": extra["value"],
           "fill_id": extra["fid"], "bytes": fill.hex(),
           "hole_off": a["off"], "hole_len": a["len"],
           "token": L.token_at(mm, a["off"]),
           "observed": obs, "oracle": {"predict": extra["predict"],
                                       "carrier_oracle": cr.spec["oracle"]},
           "predict": extra["predict"], "match": m, "outcome": oc, "status": st,
           "statuses": sts, "fault_classes": cls, "innocent_retries": inn,
           "role": extra["role"], "note": extra["note"], "ts": time.time()}
    return rec


def probe_holes(run_dir, sweep):
    """PRE-FREEZE calibration (raw/prefreeze/...). NO VERDICT MAY CITE IT.

    For every 8-byte ruler-hole candidate in the first 75 % of each carrier,
    dispatch ONLY the reachability control (`stop` at +0) and the unmutated
    baseline. A hole is usable iff the baseline is `ok` at the carrier oracle
    AND the stop fill comes back `not_written` with the sentinel intact -- i.e.
    the hole is executed, and it is executed BEFORE the result store."""
    for name in sorted(C.CARRIERS):
        try:
            cr = CarrierRunner(name)
        except Exception as e:                                  # noqa: BLE001
            emit(sweep, {"carrier": name, "outcome": "carrier_start_failed",
                         "note": str(e)[:400], "ts": time.time()})
            continue
        bounds, leftover = L.walk_boundaries(cr.main)
        emit(sweep, {"carrier": name, "outcome": "carrier_ready",
                     "note": json.dumps({"device": cr.device,
                                         "main_len": len(cr.main),
                                         "main_sha256": cr.main_sha,
                                         "n_tokens": len(bounds),
                                         "leftover_hex": leftover})})
        base = cr.measure(cr.blob(None, b""))
        emit(sweep, {"carrier": name, "arm": "carrier_open", "instr": "-",
                     "field": "_baseline", "value": -1, "outcome": base[0],
                     "observed": base[1], "status": base[3], "role": "baseline",
                     "ts": time.time()})
        runs = L.find_runs(bounds, len(cr.main), 8, 0.02, 0.75)
        seen = set()
        for h in runs:
            if h["off"] in seen:
                continue
            seen.add(h["off"])
            a = {"carrier": name, "arm": "%s@h8_%d" % (name, h["off"]),
                 "off": h["off"], "len": 8}
            fill = bytes.fromhex(W.ruler_fills(8, [], [])[0]["hex"])
            res = cr.measure(cr.blob(h["off"], fill))
            rec = case_record(cr, a, fill, res,
                              {"instr": "stop", "value": h["off"],
                               "fid": "C_reach", "predict": "not_written",
                               "role": "control_reach", "note": json.dumps(h)})
            emit(sweep, rec)
        cr.close()
        time.sleep(0.2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--arms", default=str(HERE / "harness" / "arms200.json"))
    ap.add_argument("--probe-holes", action="store_true")
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    run_dir = HERE / "raw" / args.run_id
    if run_dir.exists():
        sys.stderr.write("REFUSING: run id %s already exists. Run ids are never "
                         "reused; a partial run is retained, never topped up.\n"
                         % args.run_id)
        return 2
    run_dir.mkdir(parents=True)
    env_report(run_dir, None if args.probe_holes else args.arms, args.run_id)
    sweep = open(run_dir / "sweep.jsonl", "a")

    if args.probe_holes:
        probe_holes(run_dir, sweep)
        sweep.close()
        print("hole probe complete ->", run_dir)
        return 0

    arms = json.loads(Path(args.arms).read_text())["arms"]
    if args.only:
        keep = set(args.only.split(","))
        arms = [a for a in arms if a["carrier"] in keep]
    by_carrier = {}
    for a in arms:
        by_carrier.setdefault(a["carrier"], []).append(a)

    ncase, t0 = 0, time.time()
    for carrier, carms in by_carrier.items():
        try:
            cr = CarrierRunner(carrier)
        except Exception as e:                                  # noqa: BLE001
            emit(sweep, {"carrier": carrier, "outcome": "carrier_start_failed",
                         "note": str(e)[:400], "ts": time.time()})
            continue
        emit(sweep, {"carrier": carrier, "outcome": "carrier_ready",
                     "note": json.dumps({"device": cr.device,
                                         "main_len": len(cr.main),
                                         "main_sha256": cr.main_sha,
                                         "main_off": cr.main_off,
                                         "archive_sha256":
                                             hashlib.sha256(cr.base).hexdigest()})})

        def baseline(tag):
            res = cr.measure(cr.blob(None, b""))
            emit(sweep, {"carrier": carrier, "arm": tag, "instr": "-",
                         "field": "_baseline", "value": -1, "bytes": "",
                         "observed": res[1], "oracle": cr.spec["oracle"],
                         "match": res[2], "outcome": res[0], "status": res[3],
                         "statuses": res[4], "fault_classes": res[5],
                         "innocent_retries": res[6], "role": "baseline",
                         "note": tag, "ts": time.time()})
            return res

        baseline("carrier_open")
        for a in carms:
            baseline(a["arm"] + ":open")
            for n, f in enumerate(a["fills"]):
                fill = bytes.fromhex(f["hex"])
                if len(fill) != a["len"]:
                    emit(sweep, {"carrier": carrier, "arm": a["arm"],
                                 "outcome": "measurement_failure",
                                 "note": "fill length %d != hole length %d"
                                         % (len(fill), a["len"]),
                                 "ts": time.time()})
                    continue
                res = cr.measure(cr.blob(a["off"], fill))
                emit(sweep, case_record(cr, a, fill, res, f))
                ncase += 1
                if n and n % BASELINE_EVERY == 0:
                    baseline(a["arm"] + ":mid%d" % n)
            baseline(a["arm"] + ":close")
            print("[%6.1fs] %-10s %-30s %d fills"
                  % (time.time() - t0, carrier, a["arm"], len(a["fills"])),
                  flush=True)
        cr.close()
        time.sleep(0.3)

    sweep.close()
    print("cases=%d elapsed=%.1fs -> %s" % (ncase, time.time() - t0, run_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
